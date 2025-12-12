# AlphaSniper (BSC Edition)

이 프로젝트는 텔레그램 **NewListingsFeed** 채널을 실시간으로 모니터링하다가 **Binance Wallet** 링크(BSC)가 포함된 메시지를 발견하면, 즉시 **GMGN 봇**에게 매수 명령을 보내는 자동 매매(스나이핑) 봇입니다.

## 주요 기능

- **실시간 모니터링**: 텔레그램 개인 계정(User API)을 사용하여 채널 메시지를 딜레이 없이 감지합니다.
- **Binance Wallet CA 추출**: `https://www.binance.com/en/binancewallet/.../bsc` 형식의 URL에서 Contract Address(CA)를 자동으로 추출합니다.
- **GMGN 봇 연동**: 추출된 CA로 즉시 `/buy [CA] [Amount]` 명령을 GMGN 스나이퍼 봇에게 전송합니다.
- **자동 재시도**: 일시적인 전송 실패 시 자동으로 재시도하여 매수 성공률을 높입니다.

## 설치 방법

1. **프로젝트 클론 및 이동**
   ```bash
   git clone [레포지토리 주소]
   cd alphasniper
   ```

2. **필수 라이브러리 설치**
   Python 3.8 이상이 필요합니다.
   ```bash
   pip install -r requirements.txt
   ```

## 설정 방법

`.env` 파일을 생성하고(기존 `.env` 수정) 아래 내용을 채워주세요.

```env
# 1. 텔레그램 API 정보 (https://my.telegram.org/apps 에서 발급)
API_ID=1234567
API_HASH=abcdefg1234567...

# 2. 세션 이름 (자유롭게 지정)
SESSION_NAME=alpha_sniper

# 3. 감시할 채널 (NewListingsFeed)
SOURCE_BOT_ID=@NewListingsFeed

# 4. 매수 명령을 보낼 스나이퍼 봇
TARGET_BOT_ID=@GMGN_bsc_bot

# 5. 매수 금액 (BNB 단위)
GMGN_BUY_AMOUNT=0.1

# 6. 본인 전화번호 (국가번호 포함, 최초 로그인 시 필요)
PHONE_NUMBER=+821012345678
```

## 사용 방법

1. 터미널에서 봇 실행:
   ```bash
   python main.py
   ```
2. **최초 실행 시**: 텔레그램 인증 코드를 입력해야 할 수 있습니다. (터미널에 입력)
3. **실행 중**: 프로그램이 켜져 있는 동안 채널을 감시합니다. 중단하려면 `Ctrl+C`를 누르세요.

## 주의사항

- **DYOR / NFA**: 이 봇은 매매를 보조하는 도구일 뿐입니다. 모든 투자의 책임은 사용자 본인에게 있습니다.
- **텔레그램 계정**: 봇이 아닌 일반 사용자 계정(User API)을 사용하므로, 과도한 메시지 전송(스팸) 시 계정이 제한될 수 있습니다. (이 봇은 감지 시에만 메시지를 보내므로 비교적 안전합니다.)
- **채널 구독**: 봇을 실행하는 계정은 반드시 `@NewListingsFeed` 채널에 **참여(Join)** 상태여야 합니다.

## 라이선스

MIT License
