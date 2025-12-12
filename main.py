import os
import re
import logging
import asyncio
import signal
from dotenv import load_dotenv, set_key
from telethon import TelegramClient, events

# 로깅 설정
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.INFO)

# --- Interactive Setup Wizard ---
ENV_PATH = ".env"

def ask_input(prompt, default=None):
    """사용자 입력을 요청합니다. 기본값이 있으면 함께 표시합니다."""
    if default:
        user_input = input(f"{prompt} (기본값: {default}): ").strip()
        return user_input if user_input else default
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if user_input:
                return user_input
            print("값을 입력해야 합니다.")

def run_setup_wizard():
    """환경 변수 설정을 위한 대화형 마법사"""
    print("\n" + "="*40)
    print("  AlphaSniper 초기 설정 마법사")
    print("="*40 + "\n")
    print("설정 파일(.env)이 없거나 필수 값이 부족하여 설정을 시작합니다.")
    print("Telegram API 정보가 필요합니다. (https://my.telegram.org/apps 에서 확인 가능)\n")

    # 기존 값 로드 (있다면)
    load_dotenv(ENV_PATH)

    api_id = ask_input("1. API ID (숫자)", os.getenv("API_ID"))
    api_hash = ask_input("2. API HASH (문자열)", os.getenv("API_HASH"))
    phone_number = ask_input("3. 내 전화번호 (예: +821012345678)", os.getenv("PHONE_NUMBER"))
    
    print("\n--- 봇 설정 ---")
    source_bot = ask_input("4. 감시할 채널 ID/Username (여러 개는 콤마로 구분)", os.getenv("SOURCE_BOT_ID", "@NewListingsFeed"))
    target_bot = ask_input("5. 매수 명령 보낼 봇 ID/Username", os.getenv("TARGET_BOT_ID", "@GMGN_bsc_bot"))
    buy_amount = ask_input("6. 매수 금액 (BNB)", os.getenv("GMGN_BUY_AMOUNT", "0.1"))

    # .env 파일 저장
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# AlphaSniper Configuration\n")
        f.write(f"API_ID={api_id}\n")
        f.write(f"API_HASH={api_hash}\n")
        f.write(f"PHONE_NUMBER={phone_number}\n")
        f.write(f"SESSION_NAME=alpha_sniper\n")
        f.write(f"SOURCE_BOT_ID={source_bot}\n")
        f.write(f"TARGET_BOT_ID={target_bot}\n")
        f.write(f"GMGN_BUY_AMOUNT={buy_amount}\n")
    
    print(f"\n✅ 설정이 '{ENV_PATH}' 파일에 저장되었습니다!\n")
    return True

# .env 파일 로드 전 검사
if not os.path.exists(ENV_PATH):
    run_setup_wizard()
load_dotenv(ENV_PATH)

# 필수 값 확인 및 재실행 유도
required_vars = ["API_ID", "API_HASH", "SOURCE_BOT_ID", "TARGET_BOT_ID"]
if not all(os.getenv(v) for v in required_vars):
    print("❌ 필수 환경 변수가 누락되었습니다.")
    run_setup_wizard()
    load_dotenv(ENV_PATH) # 다시 로드

# --- 설정 상수 ---
# 매수량 설정 (기본값 0.1 BNB)
GMGN_BUY_AMOUNT = float(os.getenv("GMGN_BUY_AMOUNT", "0.1")) 

# 재시도 설정
MAX_RETRIES = 3 # 메시지 전송 최대 재시도 횟수

# Binance Wallet URL 검증 및 CA 추출 정규식
# 예: https://www.binance.com/en/binancewallet/0x97693439ea2f0ecdeb9135881e49f354656a911c/bsc
# Binance Wallet URL 검증 및 CA 추출 정규식
# 예: https://www.binance.com/en/binancewallet/0x97693439ea2f0ecdeb9135881e49f354656a911c/bsc
BINANCE_URL_REGEX = r"https://www\.binance\.com/en/binancewallet/(0x[a-fA-F0-9]{40,})/bsc"

# Newsbothub 포맷 정규식
# 예: source: 0x97693439ea2f0ecdeb9135881e49f354656a911c (bsc)
NEWSBOTHUB_SOURCE_REGEX = r"source:\s*(0x[a-fA-F0-9]{40,})\s*\(bsc\)"

# --- 환경 변수 가져오기 ---
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_name = os.getenv("SESSION_NAME", "alpha_sniper")
source_bot_id_str = os.getenv("SOURCE_BOT_ID") # 모니터링할 채널/봇 (콤마로 구분 가능)
target_bot_id_str = os.getenv("TARGET_BOT_ID") # 매수 명령을 보낼 봇 (예: @GMGN_bsc_bot)
phone_number = os.getenv("PHONE_NUMBER")

# 필수 환경 변수 확인 (위에서 했지만 안전장치)
if not all([api_id, api_hash, source_bot_id_str, target_bot_id_str]):
    raise ValueError("필수 환경 변수(API_ID, API_HASH, SOURCE_BOT_ID, TARGET_BOT_ID)가 .env 파일에 설정되지 않았습니다.")

# ID 변환 (User ID 또는 Username)
def parse_entity_id(entity_id_str):
    try:
        return int(entity_id_str)
    except ValueError:
        return entity_id_str

# 다중 소스 ID 처리
source_bot_ids = []
if "," in source_bot_id_str:
    for s_id in source_bot_id_str.split(","):
        source_bot_ids.append(parse_entity_id(s_id.strip()))
else:
    source_bot_ids.append(parse_entity_id(source_bot_id_str))

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

# --- 중복 처리 방지 셋 ---
processed_cas = set()

# --- 이벤트 핸들러 ---
# --- 이벤트 핸들러 ---
@client.on(events.NewMessage(chats=source_bot_ids))
async def handler(event):
    """
    NewListingsFeed 또는 Newsbothub로부터 새 메시지를 받았을 때 실행되는 핸들러
    1. Binance Wallet URL (NewListingsFeed 스타일)
    2. 'Binance alpha' 키워드 + 'source: ... (bsc)' (Newsbothub 스타일)
    위 패턴을 찾아 CA를 추출하고 매수 명령을 전송합니다.
    """
    message_text = event.message.text
    sender_id = event.sender_id
    
    # logging.info(f"메시지 수신 ({sender_id}):\n{message_text}") # 디버그용 로그
    
    extracted_ca = None

    # 1. Binance Wallet URL 매칭 확인 (우선순위 1)
    url_match = re.search(BINANCE_URL_REGEX, message_text)
    if url_match:
        extracted_ca = url_match.group(1)
        logging.info(f"패턴1(Binance URL) 발견! 추출된 CA: {extracted_ca}")

    # 2. Newsbothub 스타일 확인 (우선순위 2 - URL 매칭 실패 시)
    if not extracted_ca:
        # 'Binance alpha' 키워드가 있는지 확인 (대소문자 무시)
        if "binance alpha" in message_text.lower():
            source_match = re.search(NEWSBOTHUB_SOURCE_REGEX, message_text, re.IGNORECASE)
            if source_match:
                extracted_ca = source_match.group(1)
                logging.info(f"패턴2(Newsbothub/Binance alpha) 발견! 추출된 CA: {extracted_ca}")

    if extracted_ca:
        # 중복 방지 체크
        if extracted_ca in processed_cas:
            logging.info(f"이미 처리된 CA입니다. 건너뜁니다: {extracted_ca}")
            return
            
        # 매수 명령 구성 (/buy [CA] [Amount])
        command_to_send = f"/buy {extracted_ca} {GMGN_BUY_AMOUNT}"
        
        logging.info(f"매수 명령 전송 시도: {command_to_send}")
        if await send_message_with_retry(target_bot_id, command_to_send, "BUY 명령"):
            processed_cas.add(extracted_ca)
    else:
        # logging.info("유효한 CA 패턴을 찾지 못했습니다.")
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
    logging.info(f"모니터링 대상: {', '.join(map(str, source_bot_ids))}")
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