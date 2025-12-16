import os
import re
import logging
import asyncio
import signal
import json
import ssl
from dotenv import load_dotenv, set_key
from telethon import TelegramClient, events
import websockets

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
    
    print("\n--- 자동 매도 설정 ---")
    auto_sell_delay = ask_input("7. 자동 매도 대기 시간 (분)", os.getenv("AUTO_SELL_DELAY_MINUTES", "15"))
    auto_sell_percent = ask_input("8. 자동 매도 비율 (%)", os.getenv("AUTO_SELL_PERCENT", "100"))
    
    print("\n--- NLF WebSocket 설정 (선택) ---")
    nlf_enabled = ask_input("9. NLF WebSocket 사용 (true/false)", os.getenv("NLF_ENABLED", "false"))
    nlf_api_key = ""
    if nlf_enabled.lower() == "true":
        nlf_api_key = ask_input("10. NLF API 키 (t.me/NLF_websocket_bot에서 발급)", os.getenv("NLF_API_KEY", ""))

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
        f.write(f"AUTO_SELL_DELAY_MINUTES={auto_sell_delay}\n")
        f.write(f"AUTO_SELL_PERCENT={auto_sell_percent}\n")
        f.write(f"NLF_ENABLED={nlf_enabled}\n")
        if nlf_api_key:
            f.write(f"NLF_API_KEY={nlf_api_key}\n")
    
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

# 자동 매도 설정
AUTO_SELL_DELAY_MINUTES = float(os.getenv("AUTO_SELL_DELAY_MINUTES", "15")) # 기본 15분
AUTO_SELL_DELAY_SECONDS = int(AUTO_SELL_DELAY_MINUTES * 60)
AUTO_SELL_PERCENT = float(os.getenv("AUTO_SELL_PERCENT", "100")) # 기본 100%

# NLF WebSocket 설정
NLF_API_KEY = os.getenv("NLF_API_KEY", "")  # NLF WebSocket API 키
NLF_ENABLED = os.getenv("NLF_ENABLED", "false").lower() == "true"  # WebSocket 활성화 여부
NLF_WS_URL = "wss://tokyo.newlistings.pro/v1/new-listings"  # NLF WebSocket URL

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

# --- 자동 매도 스케줄링 함수 ---
async def schedule_auto_sell(ca: str, delay: int):
    """지정된 시간 후 자동으로 매도 명령을 전송합니다."""
    try:
        logging.info(f"자동 매도 예약됨: {ca} ({delay}초 후)")
        await asyncio.sleep(delay)
        
        sell_command = f"/sell {ca} {AUTO_SELL_PERCENT}%"
        logging.info(f"자동 매도 실행: {sell_command}")
        await send_message_with_retry(target_bot_id, sell_command, "자동 SELL 명령")
    except asyncio.CancelledError:
        logging.info(f"자동 매도 취소됨: {ca}")
    except Exception as e:
        logging.error(f"자동 매도 실패 ({ca}): {e}")

# --- NLF WebSocket 핸들러 ---
async def handle_nlf_websocket():
    """NLF WebSocket에 연결하여 실시간 리스팅 정보를 수신합니다."""
    if not NLF_ENABLED:
        logging.info("NLF WebSocket이 비활성화되어 있습니다.")
        return
    
    if not NLF_API_KEY:
        logging.warning("NLF_API_KEY가 설정되지 않았습니다. WebSocket 연결을 건너뜁니다.")
        return
    
    retry_delay = 5
    while True:
        try:
            logging.info(f"NLF WebSocket 연결 중: {NLF_WS_URL}")
            # SSL 인증서 검증 비활성화
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # API 키를 헤더에 포함하여 연결 (NLF API 형식)
            headers = {"authorization": f"Bearer {NLF_API_KEY}"}
            
            async with websockets.connect(NLF_WS_URL, ssl=ssl_context, additional_headers=headers) as websocket:
                logging.info("NLF WebSocket 연결 성공, 메시지 수신 대기 중...")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Binance Alpha 필터링
                        if (data.get("exchange") == "binance" and 
                            data.get("type") == "alpha"):
                            
                            # detections 배열에서 BSC 체인 찾기
                            detections = data.get("detections", [])
                            for detection in detections:
                                onchain = detection.get("onchain", {})
                                chain = onchain.get("chain")
                                ca = onchain.get("contract")
                                
                                if chain == "bsc" and ca:
                                    logging.info(f"NLF WebSocket에서 Binance Alpha BSC 발견: {ca}")
                                    
                                    # 중복 방지 체크
                                    if ca in processed_cas:
                                        logging.info(f"이미 처리된 CA입니다 (WebSocket). 건너뜁니다: {ca}")
                                        continue
                                    
                                    # 매수 명령 전송
                                    command_to_send = f"/buy {ca} {GMGN_BUY_AMOUNT}"
                                    logging.info(f"매수 명령 전송 시도 (WebSocket): {command_to_send}")
                                    
                                    if await send_message_with_retry(target_bot_id, command_to_send, "BUY 명령 (WebSocket)"):
                                        processed_cas.add(ca)
                                        # 자동 매도 예약
                                        asyncio.create_task(schedule_auto_sell(ca, AUTO_SELL_DELAY_SECONDS))
                        
                    except json.JSONDecodeError:
                        logging.error(f"WebSocket 메시지 파싱 실패: {message}")
                    except Exception as e:
                        logging.error(f"WebSocket 메시지 처리 중 오류: {e}")
                        
        except websockets.exceptions.WebSocketException as e:
            logging.error(f"NLF WebSocket 연결 오류: {e}")
        except Exception as e:
            logging.error(f"NLF WebSocket 예상치 못한 오류: {e}")
        
        logging.info(f"{retry_delay}초 후 재연결 시도...")
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 60)  # 최대 60초까지 증가

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
        # 'live on Binance alpha' 키워드가 있는지 확인 (대소문자 무시)
        if "live on Binance alpha" in message_text.lower():
            source_match = re.search(NEWSBOTHUB_SOURCE_REGEX, message_text, re.IGNORECASE)
            if source_match:
                extracted_ca = source_match.group(1)
                logging.info(f"패턴2(Newsbothub/live on Binance alpha) 발견! 추출된 CA: {extracted_ca}")

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
            # 자동 매도 예약
            asyncio.create_task(schedule_auto_sell(extracted_ca, AUTO_SELL_DELAY_SECONDS))
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
    
    # NLF WebSocket 시작
    if NLF_ENABLED and NLF_API_KEY:
        logging.info(f"NLF WebSocket 활성화: {NLF_WS_URL}")
        asyncio.create_task(handle_nlf_websocket())
    else:
        logging.info("NLF WebSocket 비활성화 (텔레그램만 사용)")
    
    logging.info("종료하려면 Ctrl+C를 누르세요...")

    await client.disconnected

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logging.critical(f"예상치 못한 오류: {e}", exc_info=True)