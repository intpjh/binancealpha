"""
Test script for auto-sell feature
Uses a 30-second delay instead of 15 minutes for quick testing
"""
import asyncio
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.INFO)

async def mock_send_message(target, message, desc):
    """Mock message sending function"""
    logging.info(f"[MOCK] Sending to {target}: {message}")
    await asyncio.sleep(0.5)  # Simulate network delay
    return True

async def schedule_auto_sell(ca: str, delay: int):
    """지정된 시간 후 자동으로 매도 명령을 전송합니다."""
    try:
        logging.info(f"자동 매도 예약됨: {ca} ({delay}초 후)")
        await asyncio.sleep(delay)
        
        sell_command = f"/sell {ca} 100%"
        logging.info(f"자동 매도 실행: {sell_command}")
        await mock_send_message("@GMGN_bsc_bot", sell_command, "자동 SELL 명령")
    except asyncio.CancelledError:
        logging.info(f"자동 매도 취소됨: {ca}")
    except Exception as e:
        logging.error(f"자동 매도 실패 ({ca}): {e}")

async def test_auto_sell():
    """Test the auto-sell feature"""
    test_ca = "0x1234567890123456789012345678901234567890"
    test_delay = 30  # 30 seconds for testing
    
    logging.info(f"테스트 시작: {test_ca}")
    
    # Simulate buy
    await mock_send_message("@GMGN_bsc_bot", f"/buy {test_ca} 0.1", "BUY 명령")
    
    # Schedule auto-sell
    asyncio.create_task(schedule_auto_sell(test_ca, test_delay))
    
    # Wait for auto-sell to complete (with some buffer)
    await asyncio.sleep(test_delay + 5)
    
    logging.info("테스트 완료")

if __name__ == "__main__":
    asyncio.run(test_auto_sell())
