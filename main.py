import os
import re
import logging
import asyncio
import signal
from dotenv import load_dotenv
from telethon import TelegramClient, events

# 로깅 설정
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.INFO)

# .env 파일에서 환경 변수 로드
load_dotenv()

# --- 설정 상수 ---
# 매수량 설정 (기본값 0.1 BNB)
GMGN_BUY_AMOUNT = float(os.getenv("GMGN_BUY_AMOUNT", "0.1")) 

# 재시도 설정
MAX_RETRIES = 3 # 메시지 전송 최대 재시도 횟수

# Binance Wallet URL 검증 및 CA 추출 정규식
# 예: https://www.binance.com/en/binancewallet/0x97693439ea2f0ecdeb9135881e49f354656a911c/bsc
BINANCE_URL_REGEX = r"https://www\.binance\.com/en/binancewallet/(0x[a-fA-F0-9]{40,})/bsc"

# --- 환경 변수 가져오기 ---
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_name = os.getenv("SESSION_NAME", "new_listings_monitor")
source_bot_id_str = os.getenv("SOURCE_BOT_ID") # 모니터링할 채널/봇 (예: @NewListingsFeed)
target_bot_id_str = os.getenv("TARGET_BOT_ID") # 매수 명령을 보낼 봇 (예: @GMGN_bsc_bot)
phone_number = os.getenv("PHONE_NUMBER")

# 필수 환경 변수 확인
if not all([api_id, api_hash, source_bot_id_str, target_bot_id_str]):
    raise ValueError("필수 환경 변수(API_ID, API_HASH, SOURCE_BOT_ID, TARGET_BOT_ID)가 .env 파일에 설정되지 않았습니다.")

# ID 변환 (User ID 또는 Username)
def parse_entity_id(entity_id_str):
    try:
        return int(entity_id_str)
    except ValueError:
        return entity_id_str

source_bot_id = parse_entity_id(source_bot_id_str)
target_bot_id = parse_entity_id(target_bot_id_str)

# 텔레그램 클라이언트 생성
client = TelegramClient(session_name, int(api_id), api_hash)

# --- 메시지 전송 재시도 함수 ---
async def send_message_with_retry(target, message, command_desc, reply_to=None):
    """지정된 대상에게 재시도 로직을 포함하여 메시지를 전송합니다."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if reply_to:
                await client.send_message(target, message, reply_to=reply_to)
            else:
                await client.send_message(target, message)
            logging.info(f"봇 ('{target}')에게 {command_desc} 명령 성공: '{message}'")
            return True
        except Exception as e:
            logging.error(f"{command_desc} 전송 실패 (시도 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1) # 잠시 대기
    return False

# --- 종료 처리 함수 ---
async def shutdown(sig, loop):
    logging.info(f"신호 {sig.name} 수신됨. 종료 시작...")
    if client.is_connected():
        await client.disconnect()
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

# --- 이벤트 핸들러 ---
@client.on(events.NewMessage(chats=source_bot_id))
async def handler(event):
    """
    NewListingsFeed로부터 새 메시지를 받았을 때 실행되는 핸들러
    Binance Wallet URL을 찾아 CA를 추출하고 매수 명령을 전송합니다.
    """
    message_text = event.message.text
    sender_id = event.sender_id
    
    # logging.info(f"메시지 수신 ({sender_id}):\n{message_text}") # 디버그용 로그

    # URL 매칭 확인
    match = re.search(BINANCE_URL_REGEX, message_text)
    
    if match:
        bsc_ca = match.group(1)
        logging.info(f"Binance Wallet URL 발견! 추출된 CA: {bsc_ca}")
        
        # 매수 명령 구성 (/buy [CA] [Amount])
        # 필요시 'bsc' 등을 뒤에 붙여야 하는지 GMGN 봇 사용법 확인 필요 (보통 /buy [CA] [Amount] 형식이 일반적)
        command_to_send = f"/buy {bsc_ca} {GMGN_BUY_AMOUNT}"
        
        logging.info(f"매수 명령 전송 시도: {command_to_send}")
        await send_message_with_retry(target_bot_id, command_to_send, "BUY 명령")
    else:
        # logging.info("Binance Wallet URL을 포함하지 않은 메시지입니다.")
        pass

async def main():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))

    logging.info("텔레그램 클라이언트 시작 중...")
    if not phone_number:
        await client.start()
    else:
        await client.start(phone=phone_number)

    logging.info("텔레그램 클라이언트 시작됨.")
    logging.info(f"모니터링 대상: {source_bot_id}")
    logging.info(f"매수 명령 대상: {target_bot_id}")
    logging.info(f"매수 금액: {GMGN_BUY_AMOUNT} BNB")
    logging.info("종료하려면 Ctrl+C를 누르세요...")

    await client.disconnected

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logging.critical(f"예상치 못한 오류: {e}", exc_info=True)