# requirements.txt
yfinance>=0.2.18
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
seaborn>=0.12.0
requests>=2.31.0
schedule>=1.2.0

# setup.py
from setuptools import setup, find_packages

setup(
name="volatility-bollinger-trading",
version="1.0.0",
description="변동성 폭파 볼린저 밴드 트레이딩 시스템",
author="Your Name",
packages=find_packages(),
install_requires=[
"yfinance>=0.2.18",
"pandas>=2.0.0",
"numpy>=1.24.0",
"matplotlib>=3.7.0",
"seaborn>=0.12.0",
"requests>=2.31.0",
"schedule>=1.2.0"
],
python_requires=">=3.8",
entry_points={
"console_scripts": [
"volatility-trading=main:main",
],
},
)

# README.md
# 변동성 폭파 볼린저 밴드 트레이딩 시스템

변동성 압축 후 폭파를 노리는 볼린저 밴드 기반 자동 트레이딩 시스템입니다.

## 🚀 주요 기능

### 1. 변동성 폭파 전략
- 볼린저 밴드폭이 최근 50일 중 하위 20% 이하일 때 변동성 압축 감지
- RSI > 70 + 변동성 압축 시 매수 신호
- 분할 익절: 50% → 나머지 50%

### 2. 백테스트 모듈 (`backtest_strategy.py`)
- 미국 시총 50위 종목 자동 분석
- 상세한 성과 지표 (수익률, 승률, 손익비, 최대낙폭 등)
- 시각화 차트 생성
- CSV 결과 저장

### 3. 실시간 모니터링 (`realtime_monitor.py`)
- 실시간 신호 감지 및 알림
- 텔레그램 자동 알림
- 중복 알림 방지 (쿨다운 시스템)
- 로깅 시스템

## 📦 설치 방법

### 1. 필수 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 2. 파일 구조
```
trading_system/
├── main.py                    # 메인 실행 파일
├── backtest_strategy.py       # 백테스트 모듈
├── realtime_monitor.py        # 실시간 모니터링 모듈
├── requirements.txt           # 필수 라이브러리
└── README.md                  # 이 파일
```

## 🔧 사용 방법

### 기본 실행
```bash
# 백테스트만 실행
python main.py --mode backtest

# 실시간 모니터링만 실행  
python main.py --mode monitor

# 백테스트 후 모니터링 (기본값)
python main.py --mode both
```

### 텔레그램 알림 설정

1. **봇 생성**: @BotFather에서 새 봇 생성
2. **토큰 획득**: 봇 토큰 복사
3. **채팅 ID 확인**: @userinfobot에서 chat_id 확인
4. **환경변수 설정**:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token_here"
   export TELEGRAM_CHAT_ID="your_chat_id_here"
   ```

### 개별 모듈 사용

#### 백테스트만 실행
```python
from backtest_strategy import VolatilityBollingerBacktest

backtest = VolatilityBollingerBacktest()
results = backtest.run_multi_stock_backtest("2022-01-01", "2024-01-01")
print(results)
```

#### 실시간 모니터링만 실행
```python
from realtime_monitor import RealTimeVolatilityMonitor

monitor = RealTimeVolatilityMonitor(
    telegram_bot_token="your_token",
    telegram_chat_id="your_chat_id"
)
monitor.start_monitoring(scan_interval=300)  # 5분 간격
```

## 📊 매매 전략 상세

### 매수 조건
- RSI > 70 (과매수 구간)
- 변동성 압축 상태 (밴드폭 < 최근 50일 중 20% 하위)

### 매도 조건
- **50% 익절**: 볼린저밴드 80% 이상 위치 OR 중앙선 근처
- **나머지 매도**: 볼린저밴드 하단 (10% 이하) 터치

### 기술적 지표
- 볼린저 밴드: 20일, 2σ
- RSI: 14일
- 변동성 지표: 50일 롤링 윈도우

## 📈 백테스트 결과 예시

```
Symbol  Total_Return(%)  Win_Rate(%)  Total_Trades  Profit_Factor  Max_Drawdown(%)
AAPL           15.23         68.5           24          2.1            8.4
MSFT           12.67         71.2           19          1.9            6.2
NVDA           28.91         64.3           31          2.8           15.1
```

## ⚠️ 주의사항

1. **투자 위험**: 이 시스템은 교육 목적으로 제작되었습니다
2. **실전 적용**: 충분한 검증 후 소액으로 시작하세요
3. **시장 변동성**: 시장 상황에 따라 전략 효과가 달라질 수 있습니다
4. **데이터 지연**: Yahoo Finance 데이터는 15-20분 지연될 수 있습니다
5. **API 제한**: 과도한 요청시 일시적 차단 가능

## 🛠️ 설정 커스터마이징

### 백테스트 설정 변경
```python
# backtest_strategy.py에서 수정
class VolatilityBollingerBacktest:
    def __init__(self):
        self.bb_period = 20              # 볼린저 밴드 기간
        self.bb_std_multiplier = 2.0     # 표준편차 배수
        self.rsi_period = 14             # RSI 기간
        self.rsi_overbought = 70         # RSI 과매수 임계값
        self.volatility_lookback = 50    # 변동성 확인 기간
        self.volatility_threshold = 0.2  # 변동성 압축 임계값
```

### 모니터링 설정 변경
```python
# realtime_monitor.py에서 수정
class RealTimeVolatilityMonitor:
    def __init__(self):
        self.watchlist = ['AAPL', 'MSFT', ...]  # 감시 종목
        self.alert_cooldown = 3600               # 알림 쿨다운 (초)
```

## 📱 텔레그램 알림 예시

### 매수 신호
```
🚀 매수 신호 발생!

종목: AAPL
현재가: $150.25
RSI: 72.3
BB 위치: 0.15
변동성 압축: 활성
시간: 2024-01-15 14:30:00

⚡ 변동성 폭파 예상 구간입니다!
```

### 익절 신호
```
💡 50% 익절 신호!

종목: AAPL
현재가: $158.75
BB 위치: 0.85
시간: 2024-01-16 10:15:00

📈 목표 수익구간에 도달했습니다.
```

## 🔍 문제 해결

### 1. 모듈 import 오류
```bash
# 파일이 같은 디렉토리에 있는지 확인
ls -la *.py

# Python 경로 확인
python -c "import sys; print(sys.path)"
```

### 2. 데이터 다운로드 실패
```python
# yfinance 업데이트
pip install --upgrade yfinance

# 네트워크 연결 확인
import yfinance as yf
stock = yf.Ticker("AAPL")
print(stock.history(period="5d"))
```

### 3. 텔레그램 알림 실패
```python
# 봇 토큰과 채팅 ID 확인
monitor.test_telegram_connection()

# 수동으로 테스트
import requests
url = f"https://api.telegram.org/bot{TOKEN}/getMe"
print(requests.get(url).json())
```

### 4. 메모리 부족
```python
# 백테스트 종목 수 줄이기
results = backtest.run_multi_stock_backtest(
    start_date, end_date, max_stocks=10  # 기본 20에서 10으로
)
```

## 📊 성과 지표 설명

- **Total_Return(%)**: 총 수익률 (초기 자본 대비)
- **Win_Rate(%)**: 승률 (수익 거래 / 전체 거래)
- **Profit_Factor**: 손익비 (평균 수익 / 평균 손실의 절댓값)
- **Max_Drawdown(%)**: 최대 낙폭 (고점 대비 최대 하락률)
- **Avg_Profit/Loss(%)**: 평균 수익/손실률

## 🔄 버전 히스토리

### v1.0.0 (2024-01-01)
- 초기 릴리즈
- 백테스트 모듈 구현
- 실시간 모니터링 모듈 구현
- 텔레그램 알림 기능
- 미국 시총 50위 종목 지원

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## ⚖️ 면책조항

본 소프트웨어는 교육 및 연구 목적으로만 제공됩니다. 실제 투자에 사용하여 발생하는 손실에 대해 개발자는 책임지지 않습니다. 투자는 본인의 책임 하에 신중하게 결정하시기 바랍니다.

## 📞 지원

- 문제 신고: GitHub Issues
- 기능 요청: GitHub Discussions
- 이메일: your.email@example.com

---

**Happy Trading! 🚀📈**
