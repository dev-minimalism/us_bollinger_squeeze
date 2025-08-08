# backtest_strategy.py
"""
변동성 폭파 볼린저 밴드 백테스트 전용 모듈 (개선 버전)

주요 개선사항:
- 리포트 저장 문제 해결
- 연도별 수익률 분석 추가
- 백테스트 기간 총 수익률 계산 개선
- 상세한 성과 지표 계산 및 시각화
- CSV 결과 저장 및 차트 생성
"""

import os
import platform
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')


# ===================================================================================
# 한글 폰트 설정
# ===================================================================================

def setup_korean_font():
  """한글 폰트 설정 (개선된 버전)"""
  try:
    import matplotlib.font_manager as fm

    system = platform.system()

    # 운영체제별 한글 폰트 설정
    if system == "Windows":
      font_candidates = [
        'C:/Windows/Fonts/malgun.ttf',  # 맑은 고딕
        'C:/Windows/Fonts/gulim.ttc',   # 굴림
        'C:/Windows/Fonts/batang.ttc'   # 바탕
      ]
      font_names = ['Malgun Gothic', 'Gulim', 'Batang', 'Arial Unicode MS']

    elif system == "Darwin":  # macOS
      font_candidates = [
        '/Library/Fonts/AppleSDGothicNeo.ttc',
        '/System/Library/Fonts/AppleGothic.ttf',
        '/Library/Fonts/NanumGothic.ttf'
      ]
      font_names = ['Apple SD Gothic Neo', 'AppleGothic', 'NanumGothic', 'Arial Unicode MS']

    else:  # Linux
      font_candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
        '/usr/share/fonts/TTF/NanumGothic.ttf'
      ]
      font_names = ['NanumGothic', 'DejaVu Sans', 'Liberation Sans']

    # 1. 파일 경로로 폰트 찾기
    font_found = False
    for font_path in font_candidates:
      if os.path.exists(font_path):
        try:
          # 폰트 파일을 matplotlib에 등록
          if hasattr(fm.fontManager, 'addfont'):
            fm.fontManager.addfont(font_path)
          prop = fm.FontProperties(fname=font_path)
          plt.rcParams['font.family'] = prop.get_name()
          font_found = True
          print(f"✅ 한글 폰트 설정: {font_path}")
          break
        except Exception as e:
          continue

    # 2. 시스템 설치 폰트에서 찾기
    if not font_found:
      available_fonts = [f.name for f in fm.fontManager.ttflist]
      for font_name in font_names:
        if font_name in available_fonts:
          try:
            plt.rcParams['font.family'] = font_name
            font_found = True
            print(f"✅ 한글 폰트 설정: {font_name}")
            break
          except Exception as e:
            continue

    # 3. 기본 대체 폰트 설정
    if not font_found:
      if system == "Windows":
        plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans', 'Arial']
      elif system == "Darwin":
        plt.rcParams['font.family'] = ['Arial Unicode MS', 'Helvetica', 'DejaVu Sans']
      else:
        plt.rcParams['font.family'] = ['DejaVu Sans', 'Liberation Sans', 'Arial']

      print("⚠️ 한글 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")

    # 마이너스 기호 깨짐 방지
    plt.rcParams['axes.unicode_minus'] = False

    # 폰트 캐시 갱신 (안전하게)
    try:
      if hasattr(fm, '_rebuild'):
        fm._rebuild()
      elif hasattr(fm.fontManager, 'findfont'):
        # 폰트 매니저 재초기화
        fm.fontManager.__init__()
    except Exception as e:
      print(f"⚠️ 폰트 캐시 갱신 건너뜀: {e}")

    return font_found

  except Exception as e:
    print(f"⚠️ 폰트 설정 중 오류: {e}")
    plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    return False


# 폰트 초기화
setup_korean_font()


# ===================================================================================
# 메인 백테스트 클래스
# ===================================================================================

class VolatilityBollingerBacktest:
  """변동성 폭파 볼린저 밴드 백테스트 클래스 (개선 버전)"""

  def __init__(self, initial_capital: float = 10000, strategy_mode: str = "conservative"):
    """초기화 (종목 리스트 검증 포함)"""

    # 미국 시총 50위 종목 (2024년 기준 업데이트)
    self.top50_stocks = [
      # 기술주
      'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM',
      # 금융
      'JPM', 'V', 'MA', 'BAC', 'WFC', 'GS', 'MS', 'C', 'AXP', 'BLK',
      # 헬스케어
      'UNH', 'JNJ', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'LLY',
      # 소비재
      'HD', 'PG', 'KO', 'PEP', 'WMT', 'COST', 'MCD', 'NKE', 'SBUX', 'TGT',
      # 에너지/산업
      'XOM', 'CVX', 'COP', 'SLB', 'CAT', 'BA', 'GE', 'HON', 'UPS', 'RTX'
    ]

    # 백테스트 설정
    self.initial_capital = initial_capital
    self.strategy_mode = strategy_mode
    self._setup_parameters(strategy_mode)

    # 출력 디렉토리 설정 및 생성
    self._setup_output_directories()

    print(f"💰 초기 자금: ${self.initial_capital:,.2f}")
    print(f"📊 전략 모드: {strategy_mode.upper()}")
    print(f"📋 분석 대상: {len(self.top50_stocks)}개 종목")

  def _setup_output_directories(self):
    """출력 디렉토리 설정 및 생성 (개선된 버전)"""
    # 현재 스크립트의 절대 경로 기준으로 출력 디렉토리 설정
    base_dir = os.path.dirname(os.path.abspath(__file__))

    self.output_base_dir = os.path.join(base_dir, 'output_files')
    self.results_dir = os.path.join(self.output_base_dir, 'results')
    self.charts_dir = os.path.join(self.output_base_dir, 'charts')
    self.reports_dir = os.path.join(self.output_base_dir, 'reports')

    # 디렉토리 생성 (개선된 오류 처리)
    directories_created = []
    for directory in [self.output_base_dir, self.results_dir, self.charts_dir, self.reports_dir]:
      try:
        os.makedirs(directory, exist_ok=True)
        directories_created.append(directory)
        print(f"📁 디렉토리 준비: {os.path.relpath(directory)}")
      except PermissionError:
        print(f"⚠️ 권한 오류 ({directory}): 현재 디렉토리 사용")
        if directory == self.results_dir:
          self.results_dir = base_dir
        elif directory == self.charts_dir:
          self.charts_dir = base_dir
        elif directory == self.reports_dir:
          self.reports_dir = base_dir
      except Exception as e:
        print(f"⚠️ 디렉토리 생성 오류 ({directory}): {e}")
        if directory == self.results_dir:
          self.results_dir = base_dir
        elif directory == self.charts_dir:
          self.charts_dir = base_dir
        elif directory == self.reports_dir:
          self.reports_dir = base_dir

    # 디렉토리 접근 권한 테스트
    self._test_directory_permissions()

  def _test_directory_permissions(self):
    """디렉토리 쓰기 권한 테스트"""
    test_dirs = {
      'results': self.results_dir,
      'charts': self.charts_dir,
      'reports': self.reports_dir
    }

    for name, path in test_dirs.items():
      try:
        test_file = os.path.join(path, 'test_write.tmp')
        with open(test_file, 'w', encoding='utf-8') as f:
          f.write('test')
        os.remove(test_file)
        print(f"✅ {name} 디렉토리 쓰기 권한 확인")
      except Exception as e:
        print(f"⚠️ {name} 디렉토리 쓰기 권한 없음: {e}")
        # 현재 디렉토리로 폴백
        setattr(self, f'{name}_dir', os.getcwd())

  def _setup_parameters(self, strategy_mode: str):
    """전략 매개변수 설정 (볼린저 스퀴즈 최적화)"""
    self.bb_period = 20
    self.bb_std_multiplier = 2.0
    self.rsi_period = 14
    self.volatility_lookback = 20
    self.volatility_threshold = 0.2

    if strategy_mode == "aggressive":
      self.rsi_upper = 80
      self.rsi_lower = 45
      self.volume_threshold = 1.1
      self.bb_sell_threshold = 0.8
      self.bb_sell_all_threshold = 0.2
      print("🔥 공격적 전략: 빠른 브레이크아웃 감지")

    elif strategy_mode == "balanced":
      self.rsi_upper = 75
      self.rsi_lower = 50
      self.volume_threshold = 1.2
      self.bb_sell_threshold = 0.85
      self.bb_sell_all_threshold = 0.15
      print("⚖️ 균형 전략: 안정적 브레이크아웃 확인")

    else:  # conservative
      self.rsi_upper = 70
      self.rsi_lower = 55
      self.volume_threshold = 1.3
      self.bb_sell_threshold = 0.9
      self.bb_sell_all_threshold = 0.1
      print("🛡️ 보수적 전략: 강한 브레이크아웃만 포착")

  # ===================================================================================
  # 기술적 지표 계산
  # ===================================================================================

  def calculate_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
    """기술적 지표 계산 (수정된 볼린저 스퀴즈 전략)"""
    if len(data) < max(self.bb_period, self.rsi_period, self.volatility_lookback):
      return data

    # 볼린저 밴드
    data['SMA'] = data['Close'].rolling(window=self.bb_period).mean()
    data['STD'] = data['Close'].rolling(window=self.bb_period).std()
    data['Upper_Band'] = data['SMA'] + (data['STD'] * self.bb_std_multiplier)
    data['Lower_Band'] = data['SMA'] - (data['STD'] * self.bb_std_multiplier)

    # 밴드폭 (변동성 지표)
    data['Band_Width'] = (data['Upper_Band'] - data['Lower_Band']) / data['SMA']

    # 변동성 압축 신호 (수정됨)
    data['BB_Squeeze'] = data['Band_Width'] < data['Band_Width'].rolling(20).min() * 1.1
    data['Volatility_Squeeze'] = data['BB_Squeeze']  # 호환성을 위해 추가

    # 볼린저 밴드 위치 (0~1)
    data['BB_Position'] = (data['Close'] - data['Lower_Band']) / (
        data['Upper_Band'] - data['Lower_Band'])

    # RSI
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # 가격 모멘텀 (스퀴즈 브레이크아웃 감지)
    data['Price_Change'] = data['Close'].pct_change()
    data['Volume_MA'] = data['Volume'].rolling(20).mean() if 'Volume' in data.columns else 1
    data['Volume_Ratio'] = data['Volume'] / data['Volume_MA'] if 'Volume' in data.columns else 1

    # 수정된 매매 신호
    data['Buy_Signal'] = (
        data['BB_Squeeze'] &
        (data['Close'] > data['Upper_Band']) &
        (data['Volume_Ratio'] > self.volume_threshold) &
        (data['RSI'] > self.rsi_lower) & (data['RSI'] < self.rsi_upper)
    )

    # 50% 익절: BB 상단 근처
    data['Sell_50_Signal'] = data['BB_Position'] >= self.bb_sell_threshold

    # 전량 매도: BB 하단 근처 또는 손절
    data['Sell_All_Signal'] = (data['BB_Position'] <= self.bb_sell_all_threshold) | (data['RSI'] < 30)

    return data

  # ===================================================================================
  # 백테스트 실행
  # ===================================================================================

  def run_single_backtest(self, symbol: str, start_date: str, end_date: str) -> Optional[Dict]:
    """단일 종목 백테스트 (개선된 버전)"""
    try:
      stock = yf.Ticker(symbol)
      data = stock.history(start=start_date, end=end_date, auto_adjust=True, prepost=True)

      # 데이터 검증
      if data.empty:
        print(f"❌ {symbol}: 데이터 없음", end="")
        return None

      if len(data) < self.volatility_lookback:
        print(f"❌ {symbol}: 데이터 부족 ({len(data)}일 < {self.volatility_lookback}일)", end="")
        return None

      if data['Close'].isna().sum() > len(data) * 0.1:
        print(f"❌ {symbol}: 데이터 품질 불량", end="")
        return None

      avg_price = data['Close'].mean()
      if avg_price < 1 or avg_price > 10000:
        print(f"❌ {symbol}: 비정상 가격 (평균: ${avg_price:.2f})", end="")
        return None

      # 기술적 지표 계산
      data = self.calculate_technical_indicators(data)

      if data['RSI'].isna().all() or data['SMA'].isna().all():
        print(f"❌ {symbol}: 지표 계산 실패", end="")
        return None

      # 백테스트 실행
      result = self._execute_backtest(data, symbol, start_date, end_date)
      result['data'] = data

      return result

    except Exception as e:
      error_msg = str(e)
      if "No data found" in error_msg:
        print(f"❌ {symbol}: 데이터 없음", end="")
      elif "Invalid ticker" in error_msg:
        print(f"❌ {symbol}: 잘못된 티커", end="")
      elif "timeout" in error_msg.lower():
        print(f"❌ {symbol}: 타임아웃", end="")
      else:
        print(f"❌ {symbol}: {error_msg[:20]}...", end="")
      return None

  def _execute_backtest(self, data: pd.DataFrame, symbol: str, start_date: str, end_date: str) -> Dict:
    """백테스트 로직 실행"""
    position = 0
    cash = self.initial_capital
    shares = 0
    trades = []
    equity_curve = []

    for i in range(len(data)):
      current_price = data.iloc[i]['Close']
      current_date = data.index[i]

      # 매수 신호
      if data.iloc[i]['Buy_Signal'] and position == 0:
        shares = cash / current_price
        position = 2

        trades.append({
          'date': current_date,
          'action': 'BUY',
          'price': current_price,
          'shares': shares,
          'value': cash
        })

      # 50% 익절
      elif data.iloc[i]['Sell_50_Signal'] and position == 2:
        sell_shares = shares * 0.5
        cash += sell_shares * current_price
        shares -= sell_shares
        position = 1

        trades.append({
          'date': current_date,
          'action': 'SELL_50%',
          'price': current_price,
          'shares': sell_shares,
          'value': sell_shares * current_price
        })

      # 전량 매도
      elif data.iloc[i]['Sell_All_Signal'] and position > 0:
        cash += shares * current_price

        trades.append({
          'date': current_date,
          'action': 'SELL_ALL',
          'price': current_price,
          'shares': shares,
          'value': shares * current_price
        })

        shares = 0
        position = 0

      # 자산가치 기록
      portfolio_value = cash + (shares * current_price)
      equity_curve.append({
        'date': current_date,
        'portfolio_value': portfolio_value,
        'cash': cash,
        'stock_value': shares * current_price
      })

    # 마지막 포지션 청산
    if shares > 0:
      cash += shares * data.iloc[-1]['Close']

    # 성과 지표 계산
    metrics = self._calculate_metrics(trades, equity_curve, cash, start_date, end_date)

    return {
      'symbol': symbol,
      'trades': trades,
      'equity_curve': equity_curve,
      'final_cash': cash,
      **metrics
    }

  def _calculate_metrics(self, trades: List[Dict], equity_curve: List[Dict],
      final_cash: float, start_date: str, end_date: str) -> Dict:
    """성과 지표 계산 (연도별 분석 추가)"""
    # 기본 수익률
    total_return = (final_cash - self.initial_capital) / self.initial_capital * 100

    # 거래 분석
    completed_trades = self._analyze_trades(trades)

    # 통계 계산
    total_trades = len(completed_trades)
    winning_trades = sum(1 for t in completed_trades if t['is_winning'])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    # 수익/손실 분석
    profits = [t['profit_pct'] for t in completed_trades if t['is_winning']]
    losses = [t['profit_pct'] for t in completed_trades if not t['is_winning']]

    avg_profit = np.mean(profits) if profits else 0
    avg_loss = np.mean(losses) if losses else 0
    profit_factor = abs(avg_profit / avg_loss) if avg_loss != 0 else float('inf')

    # 최대 낙폭
    max_drawdown = self._calculate_max_drawdown(equity_curve)

    # 테스트 기간
    test_period_days = self._calculate_test_period_days(start_date, end_date)

    # 연도별 수익률 계산 (추가)
    yearly_returns = self._calculate_yearly_returns(equity_curve, start_date, end_date)

    # 연율화 수익률 계산 (추가)
    annualized_return = self._calculate_annualized_return(final_cash, test_period_days)

    return {
      'total_return': total_return,
      'annualized_return': annualized_return,
      'yearly_returns': yearly_returns,
      'win_rate': win_rate,
      'total_trades': total_trades,
      'winning_trades': winning_trades,
      'avg_profit': avg_profit,
      'avg_loss': avg_loss,
      'profit_factor': profit_factor,
      'max_drawdown': max_drawdown,
      'final_value': final_cash,
      'completed_trades': completed_trades,
      'test_period_days': test_period_days
    }

  def _calculate_yearly_returns(self, equity_curve: List[Dict], start_date: str, end_date: str) -> Dict:
    """연도별 수익률 계산"""
    if not equity_curve:
      return {}

    # equity_curve를 DataFrame으로 변환
    df = pd.DataFrame(equity_curve)
    df['year'] = df['date'].dt.year

    yearly_returns = {}

    # 각 연도별 처리
    for year in sorted(df['year'].unique()):
      year_data = df[df['year'] == year].copy()

      if len(year_data) < 2:
        continue

      # 연도 시작값과 끝값
      start_value = year_data.iloc[0]['portfolio_value']
      end_value = year_data.iloc[-1]['portfolio_value']

      # 연도별 수익률 계산
      if start_value > 0:
        year_return = (end_value - start_value) / start_value * 100
      else:
        year_return = 0

      yearly_returns[int(year)] = {
        'return': year_return,
        'start_value': start_value,
        'end_value': end_value,
        'trading_days': len(year_data)
      }

    return yearly_returns

  def _calculate_annualized_return(self, final_cash: float, test_period_days: int) -> float:
    """연율화 수익률 계산"""
    if test_period_days <= 0:
      return 0

    total_return_ratio = final_cash / self.initial_capital
    years = test_period_days / 365.25

    if years > 0 and total_return_ratio > 0:
      annualized_return = (total_return_ratio ** (1 / years) - 1) * 100
    else:
      annualized_return = 0

    return annualized_return

  def _analyze_trades(self, trades: List[Dict]) -> List[Dict]:
    """거래 분석"""
    completed_trades = []
    buy_trade = None

    for trade in trades:
      if trade['action'] == 'BUY':
        buy_trade = trade
      elif buy_trade and trade['action'] in ['SELL_50%', 'SELL_ALL']:
        profit_pct = (trade['price'] - buy_trade['price']) / buy_trade['price'] * 100

        completed_trades.append({
          'entry_date': buy_trade['date'],
          'exit_date': trade['date'],
          'entry_price': buy_trade['price'],
          'exit_price': trade['price'],
          'profit_pct': profit_pct,
          'is_winning': profit_pct > 0
        })

        if trade['action'] == 'SELL_ALL':
          buy_trade = None

    return completed_trades

  def _calculate_max_drawdown(self, equity_curve: List[Dict]) -> float:
    """최대 낙폭 계산"""
    if not equity_curve:
      return 0

    portfolio_values = [eq['portfolio_value'] for eq in equity_curve]
    peak = portfolio_values[0]
    max_drawdown = 0

    for value in portfolio_values:
      if value > peak:
        peak = value
      drawdown = (peak - value) / peak * 100
      if drawdown > max_drawdown:
        max_drawdown = drawdown

    return max_drawdown

  def _calculate_test_period_days(self, start_date: str, end_date: str) -> int:
    """테스트 기간 일수 계산"""
    try:
      start = datetime.strptime(start_date, '%Y-%m-%d')
      end = datetime.strptime(end_date, '%Y-%m-%d')
      return (end - start).days
    except:
      return 0

  # ===================================================================================
  # 다중 종목 백테스트
  # ===================================================================================

  def run_multi_stock_backtest(self, start_date: str, end_date: str, max_stocks: int = 20) -> pd.DataFrame:
    """다중 종목 백테스트 (개선된 버전)"""
    results = []
    stocks_to_test = self.top50_stocks[:max_stocks]
    failed_stocks = []

    print(f"🔍 {len(stocks_to_test)}개 종목 백테스트 시작...")
    print(f"📅 기간: {start_date} ~ {end_date}")
    print(f"⚠️  중단하려면 Ctrl+C를 누르세요")
    print("-" * 80)

    try:
      for i, symbol in enumerate(stocks_to_test):
        print(f"진행: {i + 1:2d}/{len(stocks_to_test)} - {symbol:5s}", end=" ... ")

        retry_count = 0
        max_retries = 3
        success = False

        while retry_count < max_retries and not success:
          try:
            result = self.run_single_backtest(symbol, start_date, end_date)
            if result:
              results.append(result)
              print(f"완료 (수익률: {result['total_return']:6.2f}%)")
              success = True
            else:
              print(f"데이터 부족", end="")
              if retry_count < max_retries - 1:
                print(f" - 재시도 {retry_count + 1}/{max_retries}", end="")
                time.sleep(1)
              retry_count += 1

          except KeyboardInterrupt:
            print(f"\n⏹️  백테스트가 중단되었습니다.")
            raise
          except Exception as e:
            print(f"오류: {str(e)[:30]}...", end="")
            if retry_count < max_retries - 1:
              print(f" - 재시도 {retry_count + 1}/{max_retries}", end="")
              time.sleep(1)
            retry_count += 1

        if not success:
          failed_stocks.append(symbol)
          print(" - 최종 실패")

        if i < len(stocks_to_test) - 1:
          time.sleep(0.1)

        if (i + 1) % 10 == 0:
          success_count = len(results)
          print(f"\n📊 중간 요약: {success_count}/{i+1} 성공 ({success_count/(i+1)*100:.1f}%)")
          print("-" * 80)

    except KeyboardInterrupt:
      print(f"\n⏹️  다중 종목 백테스트가 중단되었습니다.")

    # 최종 결과 요약
    print(f"\n" + "=" * 80)
    print(f"📊 백테스트 완료 요약")
    print(f"=" * 80)
    print(f"✅ 성공: {len(results)}개 종목")
    print(f"❌ 실패: {len(failed_stocks)}개 종목")
    print(f"📈 성공률: {len(results)/len(stocks_to_test)*100:.1f}%")

    if failed_stocks:
      print(f"\n❌ 실패한 종목들:")
      for i, symbol in enumerate(failed_stocks):
        print(f"   {i+1}. {symbol}")

    if not results:
      print("\n❌ 분석 가능한 종목이 없습니다.")
      return pd.DataFrame()

    # DataFrame 변환
    df_results = pd.DataFrame([
      {
        'Symbol': r['symbol'],
        'Initial_Capital($)': f"${self.initial_capital:,.0f}",
        'Final_Value($)': f"${r['final_value']:,.0f}",
        'Profit($)': f"${r['final_value'] - self.initial_capital:,.0f}",
        'Total_Return(%)': round(r['total_return'], 2),
        'Annualized_Return(%)': round(r['annualized_return'], 2),
        'Win_Rate(%)': round(r['win_rate'], 2),
        'Total_Trades': r['total_trades'],
        'Winning_Trades': r['winning_trades'],
        'Avg_Profit(%)': round(r['avg_profit'], 2),
        'Avg_Loss(%)': round(r['avg_loss'], 2),
        'Profit_Factor': round(r['profit_factor'], 2),
        'Max_Drawdown(%)': round(r['max_drawdown'], 2),
        'Test_Days': r.get('test_period_days', 0)
      }
      for r in results
    ])

    return df_results.sort_values('Total_Return(%)', ascending=False)

  # ===================================================================================
  # 종합 분석
  # ===================================================================================

  def run_comprehensive_analysis(self, start_date: str, end_date: str,
      max_stocks: int = 20,
      detailed_analysis: str = "top5", save_charts: bool = True) -> Dict:
    """종합 분석 실행"""
    print("=" * 80)
    print("🚀 변동성 폭파 볼린저 밴드 종합 분석")
    print("=" * 80)

    # 1. 다중 종목 백테스트
    results_df = self.run_multi_stock_backtest(start_date, end_date, max_stocks)

    if results_df.empty:
      return {}

    # 2. 요약 통계 출력
    self._print_summary_statistics(results_df, start_date, end_date)

    # 3. 리스크 분석
    self._print_risk_analysis(results_df)

    # 4. 결과 저장
    self.save_results_to_csv(results_df)

    # 5. 투자 리포트 생성 (개선된 버전)
    self._save_investment_report(results_df, start_date, end_date)

    # 6. 상세 분석
    detailed_results = []
    if detailed_analysis != "none":
      symbols_to_analyze = self._select_analysis_symbols(results_df, detailed_analysis)
      if symbols_to_analyze:
        print(f"\n📊 상세 분석 시작: {len(symbols_to_analyze)}개 종목")
        detailed_results = self._run_detailed_analysis(symbols_to_analyze,
                                                       start_date, end_date,
                                                       save_charts)

    return {
      'summary_results': results_df,
      'detailed_results': detailed_results,
      'statistics': self._calculate_summary_stats(results_df)
    }

  def _select_analysis_symbols(self, results_df: pd.DataFrame, mode: str) -> List[str]:
    """분석할 종목 선택"""
    if mode == "top3":
      return results_df.head(3)['Symbol'].tolist()
    elif mode == "top5":
      return results_df.head(5)['Symbol'].tolist()
    elif mode == "positive":
      return results_df[results_df['Total_Return(%)'] > 0]['Symbol'].tolist()
    elif mode == "all":
      return results_df['Symbol'].tolist()
    else:
      return []

  def _run_detailed_analysis(self, symbols: List[str], start_date: str,
      end_date: str, save_charts: bool = True) -> List[Dict]:
    """상세 분석 실행"""
    detailed_results = []

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if save_charts:
      print(f"📁 차트 저장 디렉토리: {os.path.relpath(self.charts_dir)}/")

    for i, symbol in enumerate(symbols):
      print(f"\n📈 상세 분석 {i + 1}/{len(symbols)}: {symbol}")
      print("-" * 50)

      try:
        result = self.run_single_backtest(symbol, start_date, end_date)
        if result:
          if save_charts:
            filename = f"{symbol}_analysis_{timestamp}.png"
            self._create_analysis_chart(result, save_path=filename)
          else:
            self._create_analysis_chart(result, show_chart=True)

          self._print_detailed_results(result)
          detailed_results.append(result)
        else:
          print(f"❌ {symbol} 분석 실패")

      except Exception as e:
        print(f"❌ {symbol} 분석 중 오류: {e}")

    if save_charts and detailed_results:
      print(f"\n📊 총 {len(detailed_results)}개 차트가 {os.path.relpath(self.charts_dir)}/ 디렉토리에 저장되었습니다.")

    return detailed_results

  # ===================================================================================
  # 시각화
  # ===================================================================================

  def _create_analysis_chart(self, result: Dict, save_path: str = None, show_chart: bool = False):
    """분석 차트 생성"""
    data = result['data']
    trades = result['trades']
    equity_curve = result['equity_curve']
    symbol = result['symbol']

    fig, axes = plt.subplots(4, 1, figsize=(15, 12))
    fig.suptitle(f'{symbol} - 변동성 폭파 볼린저 밴드 전략 분석', fontsize=16, fontweight='bold')

    # 1. 주가 & 볼린저 밴드
    ax1 = axes[0]
    ax1.plot(data.index, data['Close'], 'k-', linewidth=1.5, label='종가')
    ax1.plot(data.index, data['Upper_Band'], 'r--', alpha=0.7, label='상단밴드')
    ax1.plot(data.index, data['SMA'], 'b-', alpha=0.7, label='중간밴드')
    ax1.plot(data.index, data['Lower_Band'], 'g--', alpha=0.7, label='하단밴드')
    ax1.fill_between(data.index, data['Upper_Band'], data['Lower_Band'],
                     alpha=0.1, color='gray')

    # 매매 신호 표시
    buy_signals = [t for t in trades if t['action'] == 'BUY']
    sell_50_signals = [t for t in trades if t['action'] == 'SELL_50%']
    sell_all_signals = [t for t in trades if t['action'] == 'SELL_ALL']

    if buy_signals:
      dates = [t['date'] for t in buy_signals]
      prices = [t['price'] for t in buy_signals]
      ax1.scatter(dates, prices, color='green', marker='^', s=100, zorder=5, label='매수')

    if sell_50_signals:
      dates = [t['date'] for t in sell_50_signals]
      prices = [t['price'] for t in sell_50_signals]
      ax1.scatter(dates, prices, color='orange', marker='v', s=100, zorder=5, label='50% 매도')

    if sell_all_signals:
      dates = [t['date'] for t in sell_all_signals]
      prices = [t['price'] for t in sell_all_signals]
      ax1.scatter(dates, prices, color='red', marker='v', s=100, zorder=5, label='전량매도')

    ax1.set_title('주가 & 볼린저밴드 & 매매신호', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. RSI
    ax2 = axes[1]
    ax2.plot(data.index, data['RSI'], 'purple', linewidth=1.5, label='RSI')
    ax2.axhline(y=70, color='r', linestyle='--', alpha=0.7, label='과매수 (70)')
    ax2.axhline(y=30, color='g', linestyle='--', alpha=0.7, label='과매도 (30)')
    ax2.fill_between(data.index, 70, 100, alpha=0.2, color='red')
    ax2.fill_between(data.index, 0, 30, alpha=0.2, color='green')
    ax2.set_title('RSI (상대강도지수)', fontsize=12)
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. 변동성 지표
    ax3 = axes[2]
    ax3.plot(data.index, data['Band_Width'], 'brown', linewidth=1.5, label='밴드폭')
    squeeze_data = data[data['Volatility_Squeeze']]
    if not squeeze_data.empty:
      ax3.scatter(squeeze_data.index, squeeze_data['Band_Width'], color='red',
                  s=20, alpha=0.7, label='변동성 압축')
    ax3.set_title('변동성 지표 (밴드폭 & 압축구간)', fontsize=12)
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. 자산 곡선
    ax4 = axes[3]
    if equity_curve:
      dates = [eq['date'] for eq in equity_curve]
      values = [eq['portfolio_value'] for eq in equity_curve]
      ax4.plot(dates, values, 'darkgreen', linewidth=2, label='포트폴리오 가치')
      ax4.axhline(y=self.initial_capital, color='gray', linestyle='--',
                  alpha=0.7, label='초기자본')

      final_return = ((values[-1] - self.initial_capital) / self.initial_capital) * 100
      final_profit = values[-1] - self.initial_capital

      info_text = f'총 수익률: {final_return:.2f}%\n총 수익금: ${final_profit:,.0f}'
      ax4.text(0.02, 0.85, info_text, transform=ax4.transAxes, fontsize=11,
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    ax4.set_title('포트폴리오 자산 곡선', fontsize=12)
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # X축 레이블 회전
    for ax in axes:
      ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()

    # 저장 또는 출력
    if save_path:
      try:
        if not os.path.isabs(save_path):
          save_path = os.path.join(self.charts_dir, save_path)

        chart_dir = os.path.dirname(save_path)
        os.makedirs(chart_dir, exist_ok=True)

        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"📊 차트 저장: {os.path.relpath(save_path)}")
      except Exception as e:
        print(f"❌ 차트 저장 실패: {e}")
        try:
          filename = os.path.basename(save_path)
          fallback_path = os.path.join(self.charts_dir, filename)
          plt.savefig(fallback_path, dpi=200, bbox_inches='tight')
          plt.close()
          print(f"📊 차트 저장 (대안 경로): {os.path.relpath(fallback_path)}")
        except Exception as e2:
          print(f"❌ 대안 차트 저장도 실패: {e2}")
          plt.close()
    elif show_chart:
      plt.show()
    else:
      plt.close()

  # ===================================================================================
  # 결과 출력 및 저장
  # ===================================================================================

  def _print_summary_statistics(self, results_df: pd.DataFrame, start_date: str, end_date: str):
    """요약 통계 출력 (연도별 분석 추가)"""
    print(f"\n📊 백테스트 결과 요약:")
    print("-" * 140)
    print(results_df.to_string(index=False))

    print(f"\n📈 전체 통계:")
    print("-" * 70)

    total_stocks = len(results_df)
    profitable_stocks = len(results_df[results_df['Total_Return(%)'] > 0])
    avg_return = results_df['Total_Return(%)'].mean()
    avg_annualized_return = results_df['Annualized_Return(%)'].mean()
    avg_win_rate = results_df['Win_Rate(%)'].mean()
    avg_drawdown = results_df['Max_Drawdown(%)'].mean()

    # 수익금 통계
    profits = []
    for profit_str in results_df['Profit($)']:
      profit_val = float(profit_str.replace('$', '').replace(',', ''))
      profits.append(profit_val)

      avg_profit = np.mean(profits) if profits else 0

      best = results_df.iloc[0]
      worst = results_df.iloc[-1]

      # 백테스트 기간 계산
    try:
      start_dt = datetime.strptime(start_date, '%Y-%m-%d')
      end_dt = datetime.strptime(end_date, '%Y-%m-%d')
      test_period_years = (end_dt - start_dt).days / 365.25
    except:
      test_period_years = 0

    print(f"💰 초기 자금:          ${self.initial_capital:>10,.2f}")
    print(f"📅 백테스트 기간:      {start_date} ~ {end_date} ({test_period_years:.1f}년)")
    print(f"📊 분석 종목 수:       {total_stocks:>10d}개")
    print(f"✅ 수익 종목 수:       {profitable_stocks:>10d}개 ({profitable_stocks / total_stocks * 100:.1f}%)")
    print(f"📈 평균 총 수익률:     {avg_return:>10.2f}%")
    print(f"📊 평균 연율화 수익률: {avg_annualized_return:>10.2f}%")
    print(f"💲 평균 수익금:       ${avg_profit:>10,.2f}")
    print(f"🎯 평균 승률:         {avg_win_rate:>10.2f}%")
    print(f"📉 평균 최대낙폭:     {avg_drawdown:>10.2f}%")
    print(f"🏆 최고 수익:         {best['Symbol']} ({best['Total_Return(%)']:6.2f}%)")
    print(f"📉 최저 수익:         {worst['Symbol']} ({worst['Total_Return(%)']:6.2f}%)")

    # 포트폴리오 시뮬레이션
    portfolio_return = avg_return
    portfolio_profit = (portfolio_return / 100) * self.initial_capital

    print(f"\n💼 포트폴리오 시뮬레이션 (동일 비중 투자):")
    print(f"   예상 총 수익률:     {portfolio_return:>10.2f}%")
    print(f"   예상 연율화 수익률: {avg_annualized_return:>10.2f}%")
    print(f"   예상 수익금:       ${portfolio_profit:>10,.2f}")
    print(f"   예상 최종자산:     ${self.initial_capital + portfolio_profit:>10,.2f}")

  def _print_detailed_results(self, result: Dict):
    """상세 결과 출력 (연도별 분석 추가)"""
    symbol = result['symbol']
    final_value = result['final_value']
    total_profit = final_value - self.initial_capital

    print(f"\n{'=' * 70}")
    print(f"📊 {symbol} 백테스트 상세 결과")
    print(f"{'=' * 70}")
    print(f"💰 초기 자금:        ${self.initial_capital:>10,.2f}")
    print(f"💵 최종 자산:        ${final_value:>10,.2f}")
    print(f"💲 총 수익금:        ${total_profit:>10,.2f}")
    print(f"📈 총 수익률:        {result['total_return']:>10.2f}%")
    print(f"📊 연율화 수익률:    {result['annualized_return']:>10.2f}%")
    print(f"🎯 승률:            {result['win_rate']:>10.2f}%")
    print(f"🔢 총 거래 횟수:     {result['total_trades']:>10d}회")
    print(f"✅ 수익 거래:        {result['winning_trades']:>10d}회")
    print(f"📊 평균 수익:        {result['avg_profit']:>10.2f}%")
    print(f"📉 평균 손실:        {result['avg_loss']:>10.2f}%")
    print(f"⚖️ 손익비:          {result['profit_factor']:>10.2f}")
    print(f"📉 최대 낙폭:        {result['max_drawdown']:>10.2f}%")

    # 연도별 수익률 표시
    yearly_returns = result.get('yearly_returns', {})
    if yearly_returns:
      print(f"\n📅 연도별 수익률:")
      print("-" * 50)
      for year in sorted(yearly_returns.keys()):
        year_data = yearly_returns[year]
        print(f"   {year}년: {year_data['return']:>8.2f}% "
              f"(${year_data['start_value']:>8,.0f} → ${year_data['end_value']:>8,.0f})")

    # 테스트 기간
    if result.get('test_period_days', 0) > 0:
      test_days = result['test_period_days']
      print(f"\n📅 테스트 기간:      {test_days:>10d}일 ({test_days/365.25:.1f}년)")

    # 성과 평가
    if result['total_return'] > 20:
      evaluation = "🌟 우수"
    elif result['total_return'] > 10:
      evaluation = "✅ 양호"
    elif result['total_return'] > 0:
      evaluation = "📈 수익"
    else:
      evaluation = "📉 손실"
    print(f"🏆 성과 평가:        {evaluation:>10s}")

    # 거래 내역 (최근 5개)
    trades = result['completed_trades'][:5]
    if trades:
      print(f"\n📋 최근 거래 내역 (최대 5개):")
      print("-" * 70)
      for i, trade in enumerate(trades):
        status = "✅ 수익" if trade['is_winning'] else "❌ 손실"
        profit_amount = (trade['profit_pct'] / 100) * self.initial_capital * 0.5
        print(f"{i + 1}. {trade['entry_date'].strftime('%Y-%m-%d')} → "
              f"{trade['exit_date'].strftime('%Y-%m-%d')}: "
              f"{trade['profit_pct']:6.2f}% (${profit_amount:,.0f}) {status}")

    print(f"{'=' * 70}")

  def _print_risk_analysis(self, results_df: pd.DataFrame):
    """리스크 분석 결과 출력"""
    if results_df.empty:
      return

    returns = results_df['Total_Return(%)'].values

    # 기본 통계
    mean_return = np.mean(returns)
    std_return = np.std(returns)

    # 리스크 지표
    sharpe_ratio = mean_return / std_return if std_return > 0 else 0
    var_95 = np.percentile(returns, 5)
    max_loss = np.min(returns)
    success_rate = len(returns[returns > 0]) / len(returns) * 100

    # 리스크 등급
    if std_return <= 10:
      risk_grade = "🟢 낮음"
    elif std_return <= 20:
      risk_grade = "🟡 보통"
    else:
      risk_grade = "🔴 높음"

    print(f"\n📊 리스크 분석:")
    print("-" * 50)
    print(f"📈 평균 수익률:    {mean_return:8.2f}%")
    print(f"📊 변동성:        {std_return:8.2f}%")
    print(f"⚖️ 샤프 비율:     {sharpe_ratio:8.2f}")
    print(f"⚠️ 95% VaR:      {var_95:8.2f}%")
    print(f"💥 최대 손실:     {max_loss:8.2f}%")
    print(f"🎯 성공 확률:     {success_rate:8.1f}%")
    print(f"🚦 리스크 등급:   {risk_grade}")

    # 투자 가이드
    print(f"\n💡 투자 가이드:")
    if sharpe_ratio > 1.0:
      print("   ✅ 우수한 위험 대비 수익률")
    elif sharpe_ratio > 0.5:
      print("   ⚖️ 적정한 위험 대비 수익률")
    else:
      print("   ⚠️ 리스크 대비 수익률 낮음")

    if success_rate > 70:
      print("   🎯 높은 성공 확률")
    elif success_rate > 50:
      print("   📊 보통 성공 확률")
    else:
      print("   ⚠️ 낮은 성공 확률")

  def _save_investment_report(self, results_df: pd.DataFrame, start_date: str, end_date: str):
    """투자 리포트 저장 (한글 버전 - 문제 해결됨)"""
    if results_df.empty:
      print("❌ 저장할 리포트 데이터가 없습니다.")
      return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'investment_report_{timestamp}.txt'

    print(f"📋 리포트 생성 중... (파일명: {filename})")

    # 기본 통계 계산
    total_stocks = len(results_df)
    profitable_stocks = len(results_df[results_df['Total_Return(%)'] > 0])
    avg_return = results_df['Total_Return(%)'].mean()
    avg_annualized_return = results_df['Annualized_Return(%)'].mean()

    # 백테스트 기간 계산
    try:
      start_dt = datetime.strptime(start_date, '%Y-%m-%d')
      end_dt = datetime.strptime(end_date, '%Y-%m-%d')
      test_period_years = (end_dt - start_dt).days / 365.25
      test_period_days = (end_dt - start_dt).days
    except:
      test_period_years = 0
      test_period_days = 0

    # 성과 분석
    excellent_stocks = len(results_df[results_df['Total_Return(%)'] >= 20])
    good_stocks = len(results_df[(results_df['Total_Return(%)'] >= 10) &
                                 (results_df['Total_Return(%)'] < 20)])

    # 포트폴리오 추천
    top_3 = results_df.head(3)
    safe_picks = results_df[(results_df['Total_Return(%)'] > 0) &
                            (results_df['Max_Drawdown(%)'] <= 10)].head(3)

    # 리포트 작성 (한글 버전)
    report = f"""📊 투자 분석 리포트
{'=' * 80}
📅 분석 기간: {start_date} ~ {end_date} ({test_period_years:.1f}년, {test_period_days}일)
💰 초기 자금: ${self.initial_capital:,.2f}
⚙️ 전략 모드: {self.strategy_mode.upper()}
🕐 리포트 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 백테스트 기간 전체 성과:
{'=' * 50}
   • 백테스트 총 기간: {test_period_years:.1f}년 ({test_period_days}일)
   • 평균 총 수익률: {avg_return:.2f}%
   • 평균 연율화 수익률: {avg_annualized_return:.2f}%
   • 포트폴리오 예상 총 수익: ${(avg_return/100) * self.initial_capital:,.2f}
   • 포트폴리오 예상 최종 자산: ${self.initial_capital + (avg_return/100) * self.initial_capital:,.2f}

📊 종목별 성과 요약:
{'=' * 50}
   • 분석 종목: {total_stocks}개
   • 수익 종목: {profitable_stocks}개 ({profitable_stocks / total_stocks * 100:.1f}%)
   • 손실 종목: {total_stocks - profitable_stocks}개 ({(total_stocks - profitable_stocks) / total_stocks * 100:.1f}%)
   
🏆 성과 등급별 분포:
{'=' * 50}
   • 우수 (20%+): {excellent_stocks}개
   • 양호 (10-20%): {good_stocks}개
   • 수익 (0-10%): {profitable_stocks - excellent_stocks - good_stocks}개
   • 손실 (0%미만): {total_stocks - profitable_stocks}개

🎯 투자 추천:
{'=' * 50}"""

    # 공격적 포트폴리오
    if not top_3.empty:
      report += "\n\n   📈 공격적 포트폴리오 (수익률 우선):\n"
      total_aggressive_profit = 0
      for i, (_, row) in enumerate(top_3.iterrows()):
        profit_amount = (row['Total_Return(%)'] / 100) * self.initial_capital / 3
        total_aggressive_profit += profit_amount
        annualized_str = f"(연율화: {row['Annualized_Return(%)']}%)"
        report += f"      {i + 1}. {row['Symbol']}: {row['Total_Return(%)']}% {annualized_str}\n"
        report += f"         예상 수익: ${profit_amount:,.0f} (투자금: ${self.initial_capital/3:,.0f})\n"

      report += f"\n   💰 공격적 포트폴리오 총 예상 수익: ${total_aggressive_profit:,.0f}\n"
      report += f"   💵 공격적 포트폴리오 예상 최종 자산: ${self.initial_capital + total_aggressive_profit:,.0f}\n"

    # 안정적 포트폴리오
    if not safe_picks.empty:
      report += "\n   🛡️ 안정적 포트폴리오 (리스크 최소화):\n"
      total_conservative_profit = 0
      for i, (_, row) in enumerate(safe_picks.iterrows()):
        profit_amount = (row['Total_Return(%)'] / 100) * self.initial_capital / len(safe_picks)
        total_conservative_profit += profit_amount
        report += f"      {i + 1}. {row['Symbol']}: {row['Total_Return(%)']}% "
        report += f"(낙폭: {row['Max_Drawdown(%)']}%, 연율화: {row['Annualized_Return(%)']}%)\n"
        report += f"         예상 수익: ${profit_amount:,.0f}\n"

      report += f"\n   💰 안정적 포트폴리오 총 예상 수익: ${total_conservative_profit:,.0f}\n"
      report += f"   💵 안정적 포트폴리오 예상 최종 자산: ${self.initial_capital + total_conservative_profit:,.0f}\n"

    # 투자 전략 추천
    if avg_return > 15:
      strategy_advice = "💪 강세장 전략: 적극적 투자 추천"
      strategy_detail = "높은 수익률을 보이는 종목들이 많아 공격적 투자가 유리할 것으로 예상됩니다."
    elif avg_return > 5:
      strategy_advice = "⚖️ 균형 전략: 분산 투자 추천"
      strategy_detail = "적정 수익률과 리스크를 보이므로 분산 투자를 통한 안정적 수익 추구가 바람직합니다."
    else:
      strategy_advice = "🛡️ 보수적 전략: 신중한 투자 필요"
      strategy_detail = "전반적인 수익률이 낮으므로 리스크 관리에 중점을 둔 보수적 접근이 필요합니다."

    report += f"\n💡 추천 투자 전략: {strategy_advice}\n"
    report += f"   상세: {strategy_detail}\n"

    # 리스크 분석
    returns = results_df['Total_Return(%)'].values
    std_return = np.std(returns)
    var_95 = np.percentile(returns, 5)
    max_loss = np.min(returns)

    report += f"\n📊 리스크 분석:\n"
    report += f"{'=' * 50}\n"
    report += f"   • 수익률 변동성: {std_return:.2f}%\n"
    report += f"   • 95% VaR (최악 5% 시나리오): {var_95:.2f}%\n"
    report += f"   • 최대 손실 종목: {max_loss:.2f}%\n"
    report += f"   • 성공 확률: {profitable_stocks/total_stocks*100:.1f}%\n"

    # 주의사항
    report += f"""
⚠️ 투자 주의사항:
{'=' * 50}
   • 과거 성과는 미래 수익을 보장하지 않습니다
   • 분산 투자를 통해 리스크를 관리하세요
   • 손실 허용 범위 내에서 투자하세요
   • 정기적인 포트폴리오 리밸런싱을 고려하세요
   • 시장 상황 변화에 따른 전략 조정이 필요할 수 있습니다

📊 사용된 전략 파라미터:
{'=' * 50}
   • 볼린저 밴드: {self.bb_period}일, {self.bb_std_multiplier}σ
   • RSI 기준: {self.rsi_lower}~{self.rsi_upper}
   • 거래량 임계값: {self.volume_threshold}배
   • 익절 기준: BB Position {self.bb_sell_threshold}
   • 손절 기준: BB Position {self.bb_sell_all_threshold}

📈 백테스트 결과 상세:
{'=' * 50}"""

    # 상위 10개 종목 상세 결과
    if len(results_df) > 0:
      report += f"\n\n   🏆 상위 10개 종목 성과:\n"
      top_10 = results_df.head(10)
      for i, (_, row) in enumerate(top_10.iterrows()):
        report += f"      {i+1:2d}. {row['Symbol']:5s}: "
        report += f"{row['Total_Return(%)']:6.2f}% "
        report += f"(연율화: {row['Annualized_Return(%)']:6.2f}%, "
        report += f"승률: {row['Win_Rate(%)']:5.1f}%, "
        report += f"낙폭: {row['Max_Drawdown(%)']:5.1f}%)\n"

    report += f"""

💡 추가 분석 권장사항:
{'=' * 50}
   • 상세 차트 분석을 통한 매매 시점 검토
   • 섹터별 분산 투자 고려
   • 거시경제 지표와의 상관관계 분석
   • 실시간 알림 시스템 구축 검토

📞 추가 정보:
{'=' * 50}
   더 상세한 분석이 필요하시면 상세 모드를 실행하거나
   개별 종목 차트 분석을 참조하세요.

{'=' * 80}
리포트 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
분석 도구: 변동성 폭파 볼린저 밴드 백테스트 시스템
{'=' * 80}
"""

    # 여러 저장 방법 시도
    save_paths = [
      os.path.join(self.reports_dir, filename),  # 원래 경로
      os.path.join(os.getcwd(), filename),       # 현재 디렉토리
      filename  # 상대 경로
    ]

    for i, save_path in enumerate(save_paths):
      try:
        print(f"🔄 저장 시도 {i+1}/3: {save_path}")

        # 디렉토리가 필요한 경우 생성
        if os.path.dirname(save_path):
          os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 파일 저장
        with open(save_path, 'w', encoding='utf-8', newline='\n') as f:
          f.write(report)

        # 저장 확인
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
          file_size = os.path.getsize(save_path)
          abs_path = os.path.abspath(save_path)
          print(f"✅ 리포트 저장 성공!")
          print(f"📋 파일 경로: {abs_path}")
          print(f"📄 파일 크기: {file_size:,} bytes")
          return filename
        else:
          print(f"❌ 파일이 생성되지 않았거나 크기가 0입니다.")

      except PermissionError as e:
        print(f"⚠️ 권한 오류: {e}")
        continue
      except Exception as e:
        print(f"❌ 저장 실패: {e}")
        continue

    # 모든 저장 방법 실패시 콘솔 출력
    print("\n" + "="*80)
    print("❌ 모든 저장 방법 실패 - 리포트 내용을 콘솔에 출력합니다:")
    print("="*80)
    print(report)
    print("="*80)

    # 마지막으로 간단한 텍스트 파일로 저장 시도
    try:
      simple_filename = f"report_{timestamp}.txt"
      with open(simple_filename, 'w', encoding='utf-8') as f:
        f.write("📊 투자 리포트\n")
        f.write("="*50 + "\n")
        f.write(f"📅 기간: {start_date} ~ {end_date}\n")
        f.write(f"📈 평균 수익률: {avg_return:.2f}%\n")
        f.write(f"📊 분석 종목: {total_stocks}개\n")
        f.write(f"✅ 수익 종목: {profitable_stocks}개\n")
        f.write("="*50 + "\n")
      print(f"📋 간단 리포트 저장: {simple_filename}")
      return simple_filename
    except:
      print("❌ 간단 리포트 저장도 실패")
      return None

  def _calculate_summary_stats(self, results_df: pd.DataFrame) -> Dict:
    """요약 통계 계산"""
    if results_df.empty:
      return {}

    return {
      'total_stocks': len(results_df),
      'profitable_stocks': len(results_df[results_df['Total_Return(%)'] > 0]),
      'average_return': results_df['Total_Return(%)'].mean(),
      'average_annualized_return': results_df['Annualized_Return(%)'].mean(),
      'median_return': results_df['Total_Return(%)'].median(),
      'best_stock': results_df.iloc[0]['Symbol'] if len(results_df) > 0 else 'N/A',
      'best_return': results_df.iloc[0]['Total_Return(%)'] if len(results_df) > 0 else 0,
      'worst_stock': results_df.iloc[-1]['Symbol'] if len(results_df) > 0 else 'N/A',
      'worst_return': results_df.iloc[-1]['Total_Return(%)'] if len(results_df) > 0 else 0,
      'volatility': results_df['Total_Return(%)'].std()
    }

  def save_results_to_csv(self, results_df: pd.DataFrame, filename: str = None):
    """결과를 CSV로 저장 (개선된 버전)"""
    if results_df.empty:
      print("❌ 저장할 결과가 없습니다.")
      return None

    if filename is None:
      timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
      filename = f'backtest_results_{timestamp}.csv'

    # 파일 경로 설정
    output_path = os.path.join(self.results_dir, filename)

    try:
      # 디렉토리 존재 확인
      os.makedirs(os.path.dirname(output_path), exist_ok=True)

      # CSV 저장
      results_df.to_csv(output_path, index=False, encoding='utf-8')
      print(f"💾 백테스트 결과 저장: {os.path.relpath(output_path)}")

      # 파일 크기 확인
      file_size = os.path.getsize(output_path)
      print(f"📄 CSV 크기: {file_size:,} bytes")

      return filename

    except PermissionError:
      print(f"⚠️ 권한 오류: CSV 저장 실패")
      # 현재 디렉토리에 저장 시도
      try:
        current_dir_path = os.path.join(os.getcwd(), filename)
        results_df.to_csv(current_dir_path, index=False, encoding='utf-8')
        print(f"💾 백테스트 결과 저장 (현재 디렉토리): {filename}")
        return filename
      except Exception as e2:
        print(f"❌ 현재 디렉토리 저장도 실패: {e2}")
        return None

    except Exception as e:
      print(f"❌ CSV 저장 실패: {e}")
      # 대안 경로로 재시도
      try:
        alt_filename = f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        alt_path = os.path.join(os.getcwd(), alt_filename)
        results_df.to_csv(alt_path, index=False, encoding='utf-8')
        print(f"💾 백테스트 결과 저장 (대안 경로): {alt_filename}")
        return alt_filename
      except Exception as e2:
        print(f"❌ 대안 저장도 실패: {e2}")
        return None


# ===================================================================================
# 메인 실행 함수
# ===================================================================================

def main():
  """메인 실행 함수"""
  print("🚀 변동성 폭파 볼린저 밴드 백테스트 (개선 버전)")
  print("=" * 60)

  # 초기 자금 설정
  print("💰 초기 자금 설정:")
  try:
    capital_input = input("초기 자금을 입력하세요 ($, 엔터시 기본값 10000): ").strip()
    if capital_input:
      capital = float(capital_input)
    else:
      capital = 10000
    backtest = VolatilityBollingerBacktest(initial_capital=capital)
  except ValueError:
    print("잘못된 입력입니다. 기본값 $10,000을 사용합니다.")
    backtest = VolatilityBollingerBacktest(initial_capital=10000)

  # 전략 모드 설정
  print("\n📊 전략 모드 선택:")
  print("1. 보수적 (conservative) - 확실한 신호만")
  print("2. 균형적 (balanced) - 표준 설정")
  print("3. 공격적 (aggressive) - 빠른 진입")

  try:
    mode_choice = input("전략 모드를 선택하세요 (1-3, 엔터시 기본값 1): ").strip()
    if mode_choice == "2":
      strategy_mode = "balanced"
    elif mode_choice == "3":
      strategy_mode = "aggressive"
    else:
      strategy_mode = "conservative"
  except:
    strategy_mode = "conservative"

  # 새로운 백테스트 객체 생성 (전략 모드 적용)
  backtest = VolatilityBollingerBacktest(initial_capital=capital, strategy_mode=strategy_mode)

  # 백테스트 기간 설정
  print(f"\n📅 분석 기간 설정:")
  try:
    start_input = input("시작 날짜 (YYYY-MM-DD, 엔터시 2021-01-01): ").strip()
    end_input = input("종료 날짜 (YYYY-MM-DD, 엔터시 2025-07-31): ").strip()

    start_date = start_input if start_input else "2021-01-01"
    end_date = end_input if end_input else "2025-07-31"

    # 날짜 형식 검증
    datetime.strptime(start_date, '%Y-%m-%d')
    datetime.strptime(end_date, '%Y-%m-%d')

  except ValueError:
    print("잘못된 날짜 형식입니다. 기본 기간을 사용합니다.")
    start_date = "2021-01-01"
    end_date = "2025-07-31"

  print(f"📅 분석 기간: {start_date} ~ {end_date}")

  # 분석할 종목 수 설정
  try:
    max_stocks_input = input("\n분석할 종목 수 (1-50, 엔터시 20): ").strip()
    max_stocks = int(max_stocks_input) if max_stocks_input else 20
    max_stocks = max(1, min(50, max_stocks))  # 1-50 범위로 제한
  except ValueError:
    max_stocks = 20

  print(f"📊 분석 종목 수: {max_stocks}개")

  # 상세 분석 설정
  print(f"\n📈 상세 분석 옵션:")
  print("1. 상위 3개 종목")
  print("2. 상위 5개 종목")
  print("3. 수익 종목만")
  print("4. 분석 안함")

  try:
    detail_choice = input("상세 분석 옵션을 선택하세요 (1-4, 엔터시 2): ").strip()
    if detail_choice == "1":
      detailed_analysis = "top3"
    elif detail_choice == "3":
      detailed_analysis = "positive"
    elif detail_choice == "4":
      detailed_analysis = "none"
    else:
      detailed_analysis = "top5"
  except:
    detailed_analysis = "top5"

  print(f"🎯 상세 분석: {detailed_analysis}")

  # 종합 분석 실행
  print(f"\n🚀 종합 분석 시작...")
  results = backtest.run_comprehensive_analysis(
      start_date=start_date,
      end_date=end_date,
      max_stocks=max_stocks,
      detailed_analysis=detailed_analysis,
      save_charts=True
  )

  if results:
    print(f"\n✅ 분석 완료!")

    # 투자 권장사항
    summary_results = results.get('summary_results')
    if summary_results is not None and not summary_results.empty:
      top_performers = summary_results.head(3)
      print(f"\n🏆 투자 추천 종목 (상위 3개):")
      for i, (_, row) in enumerate(top_performers.iterrows()):
        annualized_str = f"(연율화: {row['Annualized_Return(%)']}%)"
        print(f"{i + 1}. {row['Symbol']}: {row['Total_Return(%)']}% {annualized_str}")

      # 포트폴리오 시뮬레이션
      avg_return = summary_results['Total_Return(%)'].mean()
      expected_profit = (avg_return / 100) * capital
      print(f"\n💼 포트폴리오 시뮬레이션:")
      print(f"   예상 총 수익률: {avg_return:.2f}%")
      print(f"   예상 수익금: ${expected_profit:,.2f}")
      print(f"   예상 최종 자산: ${capital + expected_profit:,.2f}")

    else:
      print(f"\n❌ 유효한 분석 결과가 없습니다.")

  else:
    print(f"\n❌ 분석 실패")

  print(f"\n📁 출력 파일들은 다음 위치에 저장되었습니다:")
  print(f"   📊 결과 CSV: {backtest.results_dir}")
  print(f"   📈 차트: {backtest.charts_dir}")
  print(f"   📋 리포트: {backtest.reports_dir}")


if __name__ == "__main__":
  main()
