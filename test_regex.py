import re

# 정규식 정의 (main.py와 동일)
BINANCE_URL_REGEX = r"https://www\.binance\.com/en/binancewallet/(0x[a-fA-F0-9]{40,})/bsc"
NEWSBOTHUB_SOURCE_REGEX = r"source:\s*(0x[a-fA-F0-9]{40,})\s*\(bsc\)"

def test_message(name, message):
    print(f"--- Test Case: {name} ---")
    extracted_ca = None
    
    # 1. Binance Wallet URL 매칭 확인
    url_match = re.search(BINANCE_URL_REGEX, message)
    if url_match:
        extracted_ca = url_match.group(1)
        print(f"✅ Pattern 1 (URL) Matched: {extracted_ca}")
    
    # 2. Newsbothub 스타일 확인
    if not extracted_ca:
        if "binance alpha" in message.lower():
            source_match = re.search(NEWSBOTHUB_SOURCE_REGEX, message, re.IGNORECASE)
            if source_match:
                extracted_ca = source_match.group(1)
                print(f"✅ Pattern 2 (Newsbothub) Matched: {extracted_ca}")
            else:
                print("❌ 'Binance alpha' found but Regex failed.")
        else:
            print("ℹ️ 'Binance alpha' not found in message.")

    if not extracted_ca:
         print("❌ No CA extracted.")
    print("")

if __name__ == "__main__":
    # Case 1: Original Sample
    msg1 = """
Binance EN: $RAVE live on Binance alpha
币安重要公告: $RAVE 在 Binance alpha 上上线 


$RAVE 
————————————
2025-12-12 20:00:07
source: 0x97693439ea2f0ecdeb9135881e49f354656a911c (bsc)
"""
    test_message("Newsbothub Sample", msg1)

    # Case 2: Standard URL
    msg2 = "Here is the link: https://www.binance.com/en/binancewallet/0x1234567890123456789012345678901234567890/bsc check it out"
    test_message("Standard URL", msg2)

    # Case 3: False Positive (No keyword)
    msg3 = "source: 0x97693439ea2f0ecdeb9135881e49f354656a911c (bsc)"
    test_message("No Keyword 'Binance alpha'", msg3) # Should fail or succeed depending on logic (Current logic: requires keyword)
