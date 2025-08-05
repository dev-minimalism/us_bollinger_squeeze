# realtime_monitor.py
"""
실시간 변동성 폭파 볼린저 밴드 모니터링 시스템
- Heartbeat 기능 (1시간마다 상태 알림)
- 한국 시간 기준 미국 장시간 정확 체크
- 자동 재시작 및 오류 복구
- 텔레그램 알림 시스템
"""

import asyncio
import logging
import os
import re
import threading
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import pytz
import requests
import yfinance as yf
from telegram.ext import Application, CommandHandler

warnings.filterwarnings('ignore')


class RealTimeVolatilityMonitor:
  def __init__(self, telegram_bot_token: str = None,
      telegram_chat_id: str = None):
    """
    실시간 변동성 폭파 볼린저 밴드 모니터링 시스템 (Heartbeat 기능 포함)

    Parameters:
    telegram_bot_token: 텔레그램 봇 토큰
    telegram_chat_id: 텔레그램 채팅 ID
    """
    self.telegram_bot_token = telegram_bot_token
    self.telegram_chat_id = telegram_chat_id

    # 모니터링 대상 종목 (미국 시총 50위 전체)
    self.watchlist = [
      'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'AVGO',
      'LLY',
      'JPM', 'UNH', 'XOM', 'V', 'PG', 'JNJ', 'MA', 'HD', 'CVX', 'MRK',
      'ABBV', 'KO', 'ADBE', 'PEP', 'COST', 'WMT', 'BAC', 'CRM', 'TMO', 'NFLX',
      'ACN', 'LIN', 'MCD', 'ABT', 'CSCO', 'AMD', 'PM', 'TXN', 'DHR', 'DIS',
      'INTC', 'VZ', 'WFC', 'COP', 'BMY', 'NOW', 'CAT', 'NEE', 'UPS', 'RTX'
    ]

    # 기술적 지표 설정
    self.bb_period = 20
    self.bb_std_multiplier = 2.0
    self.rsi_period = 14
    self.rsi_overbought = 70
    self.volatility_lookback = 50
    self.volatility_threshold = 0.2

    # 알림 설정
    self.last_alerts = {}  # 중복 알림 방지
    self.alert_cooldown = 3600  # 1시간 쿨다운

    # Heartbeat 설정
    self.heartbeat_interval = 3600  # 1시간 (초)
    self.last_heartbeat = datetime.now()
    self.heartbeat_thread = None
    self.scan_count = 0
    self.total_signals_sent = 0
    self.last_signal_time = None
    self.start_time = None

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
          logging.FileHandler('trading_monitor.log'),
          logging.StreamHandler()
        ]
    )
    self.logger = logging.getLogger(__name__)

    # 모니터링 상태
    self.is_monitoring = False
    self.monitor_thread = None

    # Telegram bot application
    self.telegram_app = None
    self.telegram_running = False
    if self.telegram_bot_token:
      try:
        self.telegram_app = Application.builder().token(
            self.telegram_bot_token).build()
        self.telegram_app.add_handler(
            CommandHandler("start", self.start_command))
        self.telegram_app.add_handler(
            CommandHandler("ticker", self.ticker_command))
        self.telegram_app.add_handler(
            CommandHandler("status", self.status_command))  # 새로 추가
        self.logger.info("✅ Telegram bot handlers added successfully")
      except Exception as e:
        self.logger.error(f"❌ Telegram bot initialization failed: {e}")
        self.telegram_app = None

  async def start_command(self, update, context):
    """Handle /start command."""
    try:
      welcome_message = (
        "🤖 <b>Volatility Bollinger Bot</b>\n\n"
        "📊 Available Commands:\n"
        "• /ticker &lt;symbol&gt; - Analyze a stock (e.g., /ticker AAPL)\n"
        "• /status - Show monitoring status\n"
        "• /start - Show this help message\n\n"
        f"🔍 Monitoring Status: {'🟢 Running' if self.is_monitoring else '🔴 Stopped'}\n"
        f"📈 Watching {len(self.watchlist)} stocks\n"
        f"📱 Total alerts sent: {self.total_signals_sent}\n\n"
        "💡 <b>Example:</b> /ticker AAPL or /ticker aapl"
      )

      await update.message.reply_text(welcome_message, parse_mode='HTML')
      self.logger.info(
          f"Sent welcome message to user {update.effective_user.id}")
    except Exception as e:
      self.logger.error(f"Error in start_command: {e}")
      await update.message.reply_text(
          "Sorry, an error occurred. Please try again.")

  async def ticker_command(self, update, context):
    """Handle /ticker command to analyze a specific stock (case-insensitive)."""
    try:
      self.logger.info(
          f"Received ticker command from user {update.effective_user.id}: {context.args}")

      if not context.args:
        await update.message.reply_text(
            "❌ Please provide a ticker symbol.\n\n"
            "💡 <b>Usage:</b> /ticker &lt;symbol&gt;\n"
            "📊 <b>Examples:</b>\n"
            "• /ticker AAPL\n"
            "• /ticker tsla\n"
            "• /ticker GOOGL",
            parse_mode='HTML'
        )
        return

      ticker = context.args[0].upper().strip()
      self.logger.info(f"Processing analysis for ticker: {ticker}")

      # 진행 상황 알림
      progress_message = await update.message.reply_text(
          f"🔍 <b>Analyzing {ticker}...</b>\n⏳ Please wait...",
          parse_mode='HTML'
      )

      # 데이터 가져오기 및 분석
      signals = self.check_signals(ticker)

      if not signals:
        await progress_message.edit_text(
            f"❌ <b>No data available for {ticker}</b>\n\n"
            "💡 Please check if the ticker symbol is correct.\n"
            "📊 Try popular tickers like: AAPL, MSFT, GOOGL, AMZN, TSLA",
            parse_mode='HTML'
        )
        return

      # 분석 결과 메시지 생성
      message = self.format_analysis_message(signals)

      # 메시지 업데이트
      await progress_message.edit_text(message, parse_mode='HTML')

      self.logger.info(f"✅ Sent analysis for {ticker} via Telegram command")

    except Exception as e:
      self.logger.error(f"❌ Error analyzing ticker in command: {e}")
      try:
        await update.message.reply_text(
            f"❌ <b>Error analyzing ticker</b>\n\n"
            f"Error: {str(e)}\n\n"
            "💡 Please try again or check if the ticker symbol is correct.",
            parse_mode='HTML'
        )
      except:
        pass

  async def status_command(self, update, context):
    """Handle /status command to show monitoring status."""
    try:
      current_time = datetime.now()
      uptime = current_time - self.start_time if self.start_time else timedelta(
          0)
      uptime_str = str(uptime).split('.')[0]

      market_info = self.get_market_time_info()

      if market_info.get('is_market_open'):
        market_status = "🟢 Market Open"
        if market_info.get('time_to_close'):
          market_status += f" (closes in {market_info['time_to_close']})"
      elif market_info.get('is_weekend'):
        market_status = "🔴 Weekend"
      elif market_info.get('is_holiday'):
        market_status = "🔴 Holiday"
      else:
        market_status = "🔴 Market Closed"
        if market_info.get('next_open_korea'):
          market_status += f"\nNext open: {market_info['next_open_korea']}"

      last_signal_str = "None"
      if self.last_signal_time:
        time_diff = current_time - self.last_signal_time
        if time_diff.days > 0:
          last_signal_str = f"{time_diff.days}d ago"
        elif time_diff.seconds > 3600:
          last_signal_str = f"{time_diff.seconds // 3600}h ago"
        elif time_diff.seconds > 60:
          last_signal_str = f"{time_diff.seconds // 60}m ago"
        else:
          last_signal_str = "< 1m ago"

      status_message = f"""📊 <b>Monitoring Status</b>

🔄 Status: {'🟢 Running' if self.is_monitoring else '🔴 Stopped'}
⏱️ Uptime: {uptime_str}
🇰🇷 Korea Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
🇺🇸 US Time: {market_info.get('us_time', 'N/A')}

{market_status}

📈 <b>Statistics:</b>
   🔍 Total Scans: {self.scan_count}
   📱 Alerts Sent: {self.total_signals_sent}
   📊 Watching: {len(self.watchlist)} stocks
   ⏰ Scan Interval: 5 minutes
   🎯 Last Signal: {last_signal_str}

💡 <b>Commands:</b>
   /ticker &lt;symbol&gt; - Analyze stock
   /status - Show this status
   /start - Help message"""

      await update.message.reply_text(status_message, parse_mode='HTML')
      self.logger.info(f"Sent status to user {update.effective_user.id}")

    except Exception as e:
      self.logger.error(f"Error in status_command: {e}")
      await update.message.reply_text(
          "❌ Error getting status. Please try again.")

  def format_analysis_message(self, signals: Dict) -> str:
    """Format analysis message for Telegram command (개선된 버전)."""
    try:
      symbol = signals['symbol']
      price = signals['price']
      rsi = signals['rsi']
      bb_pos = signals['bb_position']
      volatility_squeeze = signals['volatility_squeeze']
      timestamp = signals['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
      buy_signal = signals['buy_signal']
      sell_50_signal = signals['sell_50_signal']
      sell_all_signal = signals['sell_all_signal']

      # RSI 상태 이모지
      if rsi >= 70:
        rsi_status = "🔥 Overbought"
      elif rsi <= 30:
        rsi_status = "❄️ Oversold"
      else:
        rsi_status = "⚖️ Neutral"

      # BB 위치 상태
      if bb_pos >= 0.8:
        bb_status = "🔴 Upper Band"
      elif bb_pos <= 0.2:
        bb_status = "🟢 Lower Band"
      else:
        bb_status = "🟡 Middle"

      # 신호 요약
      signals_list = []
      if buy_signal:
        signals_list.append("🚀 BUY")
      if sell_50_signal:
        signals_list.append("💡 SELL 50%")
      if sell_all_signal:
        signals_list.append("🔴 SELL ALL")

      signals_text = " | ".join(
          signals_list) if signals_list else "📊 No Signals"

      message = (
        f"📈 <b>Analysis: {symbol}</b>\n\n"
        f"💰 <b>Price:</b> ${price:.2f}\n"
        f"📊 <b>RSI:</b> {rsi:.1f} ({rsi_status})\n"
        f"📍 <b>BB Position:</b> {bb_pos:.2f} ({bb_status})\n"
        f"🔥 <b>Volatility Squeeze:</b> {'✅ Active' if volatility_squeeze else '❌ Inactive'}\n\n"
        f"🎯 <b>Signals:</b> {signals_text}\n\n"
        f"⏰ <b>Analysis Time:</b> {timestamp}\n\n"
        f"💡 <b>Strategy Notes:</b>\n"
        f"• Buy when RSI > 70 + Volatility Squeeze\n"
        f"• Take 50% profit at BB upper region\n"
        f"• Exit remaining at BB lower region"
      )

      return message

    except Exception as e:
      self.logger.error(f"Error formatting analysis message: {e}")
      return f"❌ Error formatting analysis for {signals.get('symbol', 'unknown')}"

  def send_telegram_alert(self, message: str, parse_mode: str = 'HTML'):
    """텔레그램 알림 전송"""
    if not self.telegram_bot_token or not self.telegram_chat_id:
      self.logger.info(
          f"Telegram Alert (not sent, no token/chat_id): {message}")
      return False

    # Sanitize message to prevent invalid HTML tags
    message = re.sub(r'<symbol>', '<b>', message, flags=re.IGNORECASE)
    message = re.sub(r'</symbol>', '</b>', message, flags=re.IGNORECASE)
    self.logger.debug(f"Sending Telegram message: {message}")

    url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
    payload = {
      'chat_id': self.telegram_chat_id,
      'text': message,
      'parse_mode': parse_mode
    }

    try:
      response = requests.post(url, data=payload, timeout=10)
      if response.status_code == 200:
        self.logger.info("텔레그램 알림 전송 성공")
        return True
      else:
        self.logger.error(f"텔레그램 전송 실패: {response.text}")
        return False
    except Exception as e:
      self.logger.error(f"텔레그램 전송 오류: {e}")
      return False

  def send_heartbeat(self):
    """Heartbeat 메시지 전송 (시간 정보 개선)"""
    if not self.telegram_bot_token:
      return

    current_time = datetime.now()
    uptime = current_time - self.start_time if self.start_time else timedelta(0)
    uptime_str = str(uptime).split('.')[0]

    market_info = self.get_market_time_info()

    if market_info.get('is_market_open'):
      market_status = "🟢 장중"
      if market_info.get('time_to_close'):
        market_status += f" (마감까지 {market_info['time_to_close']})"
    elif market_info.get('is_weekend'):
      market_status = "🔴 주말"
    elif market_info.get('is_holiday'):
      market_status = "🔴 공휴일"
    else:
      market_status = "🔴 장마감"
      if market_info.get('next_open_korea'):
        market_status += f"\n   다음 개장: {market_info['next_open_korea']}"

    last_signal_str = "없음"
    if self.last_signal_time:
      time_diff = current_time - self.last_signal_time
      if time_diff.days > 0:
        last_signal_str = f"{time_diff.days}일 전"
      elif time_diff.seconds > 3600:
        last_signal_str = f"{time_diff.seconds // 3600}시간 전"
      elif time_diff.seconds > 60:
        last_signal_str = f"{time_diff.seconds // 60}분 전"
      else:
        last_signal_str = "1분 이내"

    hour = current_time.hour
    if 6 <= hour < 12:
      time_emoji = "🌅"
    elif 12 <= hour < 18:
      time_emoji = "☀️"
    elif 18 <= hour < 22:
      time_emoji = "🌆"
    else:
      time_emoji = "🌙"

    heartbeat_message = f"""{time_emoji} <b>Heartbeat - 시스템 정상 가동</b>

🇰🇷 한국 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
🇺🇸 미국 시간: {market_info.get('us_time', 'N/A')}
⏱️ 가동 시간: {uptime_str}

{market_status}

📊 <b>통계 정보:</b>
   🔍 총 스캔: {self.scan_count}회
   📱 알림 발송: {self.total_signals_sent}개
   📈 감시 종목: {len(self.watchlist)}개
   ⏰ 스캔 간격: 5분

🎯 <b>최근 활동:</b>
   마지막 신호: {last_signal_str}
   알림 기록: {len(self.last_alerts)}개

✅ <b>상태:</b> 모든 시스템 정상 작동 중
🔄 다음 Heartbeat: 1시간 후"""

    if self.send_telegram_alert(heartbeat_message):
      self.logger.info(f"💓 Heartbeat 전송 완료 - 가동시간: {uptime_str}")
      self.last_heartbeat = current_time
    else:
      self.logger.error("💔 Heartbeat 전송 실패")

  def start_heartbeat(self):
    """Heartbeat 스레드 시작"""
    if self.heartbeat_thread and self.heartbeat_thread.is_alive():
      return

    self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop,
                                             daemon=True)
    self.heartbeat_thread.start()
    self.logger.info(f"💓 Heartbeat 스레드 시작 - {self.heartbeat_interval}초 간격")

  def _heartbeat_loop(self):
    """Heartbeat 루프"""
    while self.is_monitoring:
      try:
        time.sleep(self.heartbeat_interval)

        if self.is_monitoring:
          self.send_heartbeat()

      except Exception as e:
        self.logger.error(f"💔 Heartbeat 루프 오류: {e}")
        time.sleep(60)

  def _is_market_hours(self) -> bool:
    """미국 주식 시장 시간 확인 (한국 시간 기준)"""
    try:
      korea_tz = pytz.timezone('Asia/Seoul')
      us_eastern_tz = pytz.timezone('US/Eastern')

      korea_now = datetime.now(korea_tz)
      us_now = korea_now.astimezone(us_eastern_tz)

      if us_now.weekday() >= 5:
        return False

      if self._is_us_holiday(us_now):
        return False

      market_open = us_now.replace(hour=9, minute=30, second=0, microsecond=0)
      market_close = us_now.replace(hour=16, minute=0, second=0, microsecond=0)

      is_open = market_open <= us_now <= market_close

      if not hasattr(self, '_time_debug_count'):
        self._time_debug_count = 0

      if self._time_debug_count < 3:
        self.logger.info(
            f"⏰ 시간 체크 - 한국: {korea_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        self.logger.info(
            f"⏰ 시간 체크 - 미국: {us_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        self.logger.info(f"⏰ 장 상태: {'🟢 개장' if is_open else '🔴 마감'}")
        self._time_debug_count += 1

      return is_open

    except Exception as e:
      self.logger.warning(f"시간 확인 오류: {e} - 기본값 True 반환")
      return True

  def _is_us_holiday(self, us_date: datetime) -> bool:
    """미국 주요 공휴일 체크 (간단 버전)"""
    try:
      year = us_date.year
      month = us_date.month
      day = us_date.day

      holidays = [
        (1, 1),  # 신정
        (7, 4),  # 독립기념일
        (12, 25),  # 크리스마스
      ]

      if (month, day) in holidays:
        return True

      if month == 11 and us_date.weekday() == 3:
        first_day = us_date.replace(day=1)
        first_thursday = 1 + (3 - first_day.weekday()) % 7
        fourth_thursday = first_thursday + 21
        if day == fourth_thursday:
          return True

      return False

    except Exception as e:
      self.logger.warning(f"공휴일 확인 오류: {e}")
      return False

  def get_market_time_info(self) -> Dict:
    """시장 시간 정보 조회"""
    try:
      korea_tz = pytz.timezone('Asia/Seoul')
      us_eastern_tz = pytz.timezone('US/Eastern')

      korea_now = datetime.now(korea_tz)
      us_now = korea_now.astimezone(us_eastern_tz)

      next_open = self._get_next_market_open(us_now)
      next_open_korea = next_open.astimezone(korea_tz) if next_open else None

      time_to_close = None
      if self._is_market_hours():
        market_close = us_now.replace(hour=16, minute=0, second=0,
                                      microsecond=0)
        time_to_close = market_close - us_now

      return {
        'korea_time': korea_now.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'us_time': us_now.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'is_market_open': self._is_market_hours(),
        'is_weekend': us_now.weekday() >= 5,
        'is_holiday': self._is_us_holiday(us_now),
        'next_open_us': next_open.strftime(
            '%Y-%m-%d %H:%M %Z') if next_open else None,
        'next_open_korea': next_open_korea.strftime(
            '%Y-%m-%d %H:%M %Z') if next_open_korea else None,
        'time_to_close': str(time_to_close).split('.')[
          0] if time_to_close else None
      }

    except Exception as e:
      self.logger.error(f"시장 시간 정보 조회 오류: {e}")
      return {}

  def _get_next_market_open(self, current_us_time: datetime) -> datetime:
    """다음 장 개장 시간 계산"""
    try:
      today_open = current_us_time.replace(hour=9, minute=30, second=0,
                                           microsecond=0)

      if current_us_time < today_open and current_us_time.weekday() < 5:
        if not self._is_us_holiday(current_us_time):
          return today_open

      next_day = current_us_time + timedelta(days=1)

      for i in range(7):
        check_date = next_day + timedelta(days=i)
        if check_date.weekday() < 5 and not self._is_us_holiday(check_date):
          return check_date.replace(hour=9, minute=30, second=0, microsecond=0)

      return None

    except Exception as e:
      self.logger.error(f"다음 개장 시간 계산 오류: {e}")
      return None

  def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
    """기술적 지표 계산"""
    if len(data) < max(self.bb_period, self.rsi_period,
                       self.volatility_lookback):
      return data

    data['SMA'] = data['Close'].rolling(window=self.bb_period).mean()
    data['STD'] = data['Close'].rolling(window=self.bb_period).std()
    data['Upper_Band'] = data['SMA'] + (data['STD'] * self.bb_std_multiplier)
    data['Lower_Band'] = data['SMA'] - (data['STD'] * self.bb_std_multiplier)

    data['Band_Width'] = (data['Upper_Band'] - data['Lower_Band']) / data['SMA']
    data['Volatility_Squeeze'] = data['Band_Width'] < data[
      'Band_Width'].rolling(self.volatility_lookback).quantile(
        self.volatility_threshold)

    data['BB_Position'] = (data['Close'] - data['Lower_Band']) / (
        data['Upper_Band'] - data['Lower_Band'])

    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    data['Buy_Signal'] = (data['RSI'] > self.rsi_overbought) & (
      data['Volatility_Squeeze'])
    data['Sell_50_Signal'] = (data['BB_Position'] >= 0.8) | (
        abs(data['BB_Position'] - 0.5) <= 0.1)
    data['Sell_All_Signal'] = data['BB_Position'] <= 0.1

    return data

  def get_stock_data(self, symbol: str, period: str = "100d") -> Optional[
    pd.DataFrame]:
    """주식 데이터 가져오기"""
    try:
      stock = yf.Ticker(symbol)
      data = stock.history(period=period)

      if data.empty:
        self.logger.warning(
            f"No data found for {symbol}, retrying with period='1y'")
        data = stock.history(period="1y")
      if data.empty:
        self.logger.warning(f"No data found for {symbol}")
        return None

      return data

    except Exception as e:
      self.logger.error(f"Error fetching data for {symbol}: {e}")
      return None

  def check_signals(self, symbol: str) -> Dict:
    """신호 확인 (개선된 에러 처리)"""
    try:
      data = self.get_stock_data(symbol)
      if data is None or len(data) < self.volatility_lookback:
        self.logger.warning(f"Insufficient data for {symbol}")
        return {}

      data = self.calculate_indicators(data)
      if data is None or data.empty:
        self.logger.warning(f"Failed to calculate indicators for {symbol}")
        return {}

      latest = data.iloc[-1]

      # NaN 값 체크
      if pd.isna(latest['RSI']) or pd.isna(latest['BB_Position']):
        self.logger.warning(f"NaN values in indicators for {symbol}")
        return {}

      signals = {
        'symbol': symbol,
        'price': float(latest['Close']),
        'rsi': float(latest['RSI']),
        'bb_position': float(latest['BB_Position']),
        'band_width': float(latest['Band_Width']),
        'volatility_squeeze': bool(latest['Volatility_Squeeze']),
        'buy_signal': bool(latest['Buy_Signal']),
        'sell_50_signal': bool(latest['Sell_50_Signal']),
        'sell_all_signal': bool(latest['Sell_All_Signal']),
        'timestamp': latest.name
      }

      return signals

    except Exception as e:
      self.logger.error(f"Error checking signals for {symbol}: {e}")
      return {}

  def should_send_alert(self, symbol: str, signal_type: str) -> bool:
    """알림 쿨다운 확인"""
    key = f"{symbol}_{signal_type}"
    current_time = time.time()

    if key in self.last_alerts:
      if current_time - self.last_alerts[key] < self.alert_cooldown:
        return False

    self.last_alerts[key] = current_time
    return True

  def format_alert_message(self, signals: Dict, signal_type: str) -> str:
    """알림 메시지 포맷팅"""
    symbol = signals['symbol']
    price = signals['price']
    rsi = signals['rsi']
    bb_pos = signals['bb_position']
    timestamp = signals['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

    if signal_type == 'buy':
      message = f"""🚀 <b>매수 신호 발생!</b>
            
종목: <b>{symbol}</b>
현재가: <b>${price:.2f}</b>
RSI: <b>{rsi:.1f}</b>
BB 위치: <b>{bb_pos:.2f}</b>
변동성 압축: <b>활성</b>
시간: {timestamp}

⚡ 변동성 폭파 예상 구간입니다!"""

    elif signal_type == 'sell_50':
      message = f"""💡 <b>50% 익절 신호!</b>
            
종목: <b>{symbol}</b>
현재가: <b>${price:.2f}</b>
BB 위치: <b>{bb_pos:.2f}</b>
시간: {timestamp}

📈 목표 수익구간에 도달했습니다."""

    elif signal_type == 'sell_all':
      message = f"""🔴 <b>전량 매도 신호!</b>
            
종목: <b>{symbol}</b>
현재가: <b>${price:.2f}</b>
BB 위치: <b>{bb_pos:.2f}</b>
시간: {timestamp}

⚠️ 손절 또는 나머지 익절 시점입니다."""

    else:
      message = f"알 수 없는 신호 타입: {signal_type}"

    return message

  def process_signals(self, signals: Dict) -> bool:
    """신호 처리 및 알림"""
    if not signals:
      return False

    symbol = signals['symbol']
    alert_sent = False

    if signals['buy_signal'] and self.should_send_alert(symbol, 'buy'):
      message = self.format_alert_message(signals, 'buy')
      if self.send_telegram_alert(message):
        self.logger.info(f"🚀 매수 신호 알림 전송: {symbol}")
        self.total_signals_sent += 1
        self.last_signal_time = datetime.now()
        alert_sent = True

    if signals['sell_50_signal'] and self.should_send_alert(symbol, 'sell_50'):
      message = self.format_alert_message(signals, 'sell_50')
      if self.send_telegram_alert(message):
        self.logger.info(f"💡 50% 매도 신호 알림 전송: {symbol}")
        self.total_signals_sent += 1
        self.last_signal_time = datetime.now()
        alert_sent = True

    if signals['sell_all_signal'] and self.should_send_alert(symbol,
                                                             'sell_all'):
      message = self.format_alert_message(signals, 'sell_all')
      if self.send_telegram_alert(message):
        self.logger.info(f"🔴 전량 매도 신호 알림 전송: {symbol}")
        self.total_signals_sent += 1
        self.last_signal_time = datetime.now()
        alert_sent = True

    return alert_sent

  def scan_single_stock(self, symbol: str):
    """단일 종목 스캔"""
    try:
      signals = self.check_signals(symbol)
      if signals:
        self.process_signals(signals)

        if any([signals.get('buy_signal'), signals.get('sell_50_signal'),
                signals.get('sell_all_signal')]):
          self.logger.info(
              f"{symbol}: Price=${signals['price']:.2f}, RSI={signals['rsi']:.1f}, BB_Pos={signals['bb_position']:.2f}")

    except Exception as e:
      self.logger.error(f"Error scanning {symbol}: {e}")

  def scan_all_stocks(self):
    """전체 종목 스캔"""
    self.logger.info("Starting market scan...")

    for symbol in self.watchlist:
      self.scan_single_stock(symbol)
      time.sleep(0.2)

    self.logger.info("Market scan completed")

  def _scan_all_stocks_auto(self) -> int:
    """전체 종목 자동 스캔"""
    signals_found = 0
    failed_stocks = []

    for i, symbol in enumerate(self.watchlist):
      try:
        if (i + 1) % 10 == 0:
          self.logger.info(
              f"   진행률: {i + 1}/{len(self.watchlist)} ({(i + 1) / len(self.watchlist) * 100:.0f}%)")

        signals = self.check_signals(symbol)
        if signals:
          if self.process_signals(signals):
            signals_found += 1

        time.sleep(0.2)

      except Exception as e:
        self.logger.error(f"❌ {symbol} 스캔 오류: {e}")
        failed_stocks.append(symbol)
        continue

    if failed_stocks:
      self.logger.warning(f"⚠️ 스캔 실패 종목: {', '.join(failed_stocks)}")

    return signals_found

  def start_monitoring(self, scan_interval: int = 300):
    """자동 모니터링 시작 (수정된 버전)"""
    if self.is_monitoring:
      self.logger.warning("모니터링이 이미 실행 중입니다.")
      return

    self.is_monitoring = True
    self.start_time = datetime.now()
    self.scan_count = 0
    self.total_signals_sent = 0

    self.logger.info(f"🚀 자동 모니터링 시작 (스캔 간격: {scan_interval}초)")

    # Telegram bot 시작 (수정된 부분)
    if self.telegram_app and not self.telegram_running:
      self.telegram_running = True
      self.telegram_thread = threading.Thread(target=self._run_telegram_bot,
                                              daemon=True)
      self.telegram_thread.start()
      self.logger.info("✅ Telegram bot thread started")

    # Heartbeat 시작
    self.start_heartbeat()

    # 시작 메시지 전송
    if self.telegram_bot_token:
      start_message = f"""🤖 <b>Monitoring Started</b>

📊 Watching: {len(self.watchlist)} stocks (US Top 50)
⏰ Scan Interval: {scan_interval}s ({scan_interval // 60}min)
💓 Heartbeat: Every hour
🕐 Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}

🎯 Volatility Bollinger Band Strategy Active
⚡ Real-time alerts will be sent immediately
💓 System status updates every hour

📱 <b>Commands:</b>
• /ticker &lt;symbol&gt; - Analyze any stock
• /status - Show monitoring status
• /start - Show help

💡 <b>Example:</b> /ticker AAPL"""

      self.send_telegram_alert(start_message)

    # 모니터링 스레드 시작
    self.monitor_thread = threading.Thread(target=self._auto_monitoring_loop,
                                           args=(scan_interval,), daemon=True)
    self.monitor_thread.start()

    self.logger.info("✅ 자동 모니터링 스레드가 시작되었습니다.")

  def _run_telegram_bot(self):
    """Run Telegram bot in a separate thread (수정된 버전)."""
    try:
      self.logger.info("🤖 Starting Telegram bot polling...")

      # 새로운 이벤트 루프 생성
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)

      # 봇 실행
      self.telegram_app.run_polling(
          poll_interval=1.0,
          timeout=10,
          drop_pending_updates=True,
          stop_signals=None  # 시그널 처리 비활성화 (백그라운드 실행용)
      )

    except Exception as e:
      self.logger.error(f"❌ Telegram bot error: {e}")
      self.telegram_running = False
      # 재시작 시도
      if self.is_monitoring:
        self.logger.info(
            "🔄 Attempting to restart Telegram bot in 30 seconds...")
        time.sleep(30)
        if self.is_monitoring and not self.telegram_running:
          self.telegram_running = True
          self._run_telegram_bot()

  def _auto_monitoring_loop(self, scan_interval: int):
    """자동 모니터링 루프"""
    while self.is_monitoring:
      try:
        self.scan_count += 1
        current_time = datetime.now()

        is_market_open = self._is_market_hours()
        market_info = self.get_market_time_info()

        if is_market_open:
          self.logger.info(
              f"📊 스캔 #{self.scan_count} 시작 - {current_time.strftime('%H:%M:%S')}")
          self.logger.info(f"   🇺🇸 미국시간: {market_info.get('us_time', 'N/A')}")

          signals_found = self._scan_all_stocks_auto()

          if signals_found > 0:
            self.logger.info(f"🎯 {signals_found}개 신호 발견 및 알림 전송 완료")
          else:
            self.logger.info("📈 신호 없음 - 모니터링 계속")

          if self.scan_count % 5 == 0:
            self._send_status_summary(self.scan_count)

        else:
          if market_info.get('is_weekend'):
            status_msg = "주말"
          elif market_info.get('is_holiday'):
            status_msg = "공휴일"
          else:
            status_msg = "장마감 시간"

          next_scan_time = (
              current_time + timedelta(seconds=scan_interval)).strftime(
              '%H:%M:%S')
          self.logger.info(
              f"⏰ {status_msg} - 대기 중... (다음 스캔: {next_scan_time})")

          if market_info.get('next_open_korea'):
            self.logger.info(f"   📅 다음 개장: {market_info['next_open_korea']}")

        time.sleep(scan_interval)

      except Exception as e:
        self.logger.error(f"❌ 모니터링 루프 오류: {e}")
        time.sleep(30)

  def _send_status_summary(self, scan_count: int):
    """상태 요약 전송 (5회마다)"""
    if not self.telegram_bot_token:
      return

    current_time = datetime.now()
    uptime = current_time - self.start_time if self.start_time else timedelta(0)

    summary_message = f"""📊 <b>모니터링 상태 요약</b>

🔢 스캔 횟수: {scan_count}회  
⏰ 현재 시간: {current_time.strftime('%H:%M:%S')}
🕐 실행 시간: {str(uptime).split('.')[0]}
📈 감시 종목: {len(self.watchlist)}개
🎯 알림 전송: {self.total_signals_sent}개

✅ 시스템 정상 작동 중"""

    self.send_telegram_alert(summary_message)

  def stop_monitoring(self):
    """모니터링 중지 (수정된 버전)"""
    if not self.is_monitoring:
      self.logger.warning("모니터링이 실행되고 있지 않습니다.")
      return

    self.is_monitoring = False
    self.telegram_running = False

    # 스레드 정리
    if self.monitor_thread:
      self.monitor_thread.join(timeout=10)

    if self.telegram_app:
      try:
        # Telegram bot 정지
        asyncio.run(self.telegram_app.stop())
      except Exception as e:
        self.logger.warning(f"Error stopping Telegram bot: {e}")

    # 종료 메시지 전송
    if self.telegram_bot_token and self.start_time:
      end_time = datetime.now()
      uptime = end_time - self.start_time

      stop_message = f"""⏹️ <b>Monitoring Stopped</b>

🕐 Stop Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
⏱️ Total Runtime: {str(uptime).split('.')[0]}
🔢 Total Scans: {self.scan_count}
🎯 Total Alerts: {self.total_signals_sent}

✅ Monitoring stopped safely."""

      self.send_telegram_alert(stop_message)

    self.logger.info("✅ 모니터링이 중지되었습니다.")

  def run_continuous_monitoring(self, scan_interval: int = 300):
    """연속 모니터링 실행"""
    try:
      self.logger.info("=" * 80)
      self.logger.info("🚀 변동성 폭파 볼린저 밴드 연속 모니터링 시작")
      self.logger.info("=" * 80)
      self.logger.info(f"📊 감시 종목: {len(self.watchlist)}개 (미국 시총 50위)")
      self.logger.info(f"⏰ 스캔 간격: {scan_interval}초 ({scan_interval // 60}분)")
      self.logger.info(
          f"💓 Heartbeat: {self.heartbeat_interval}초 ({self.heartbeat_interval // 60}분) 간격")
      self.logger.info(
          f"📱 텔레그램 알림: {'활성화' if self.telegram_bot_token else '비활성화'}")

      if self.telegram_bot_token:
        if self.test_telegram_connection():
          self.logger.info("✅ 텔레그램 연결 테스트 성공")
        else:
          self.logger.warning("⚠️ 텔레그램 연결 실패 - 콘솔 로그만 출력")

      self.logger.info("\n📊 초기 시장 상황 확인 중...")
      initial_signals = self._scan_all_stocks_auto()
      self.logger.info(f"📈 초기 스캔 완료: {initial_signals}개 신호 발견")

      self.start_monitoring(scan_interval)

      self.logger.info(f"\n🎯 연속 모니터링 실행 중...")
      self.logger.info(f"   💓 Heartbeat: 1시간마다 상태 알림")
      self.logger.info(
          f"   📬 Use /ticker <symbol> to analyze a stock (e.g., /ticker AAPL or /ticker aapl)")
      self.logger.info(f"   종료하려면 Ctrl+C를 누르세요.")
      self.logger.info("=" * 80)

      while self.is_monitoring:
        time.sleep(60)

    except KeyboardInterrupt:
      self.logger.info(f"\n⏹️ 사용자에 의해 모니터링이 중단되었습니다.")
    except Exception as e:
      self.logger.error(f"❌ 모니터링 중 오류 발생: {e}")
    finally:
      self.stop_monitoring()

  def get_monitoring_statistics(self) -> Dict:
    """모니터링 통계 조회"""
    if hasattr(self, 'start_time') and self.start_time:
      uptime = datetime.now() - self.start_time
    else:
      uptime = timedelta(0)

    return {
      'is_running': self.is_monitoring,
      'watchlist_count': len(self.watchlist),
      'uptime_seconds': uptime.total_seconds(),
      'uptime_formatted': str(uptime).split('.')[0],
      'total_alerts': self.total_signals_sent,
      'scan_count': self.scan_count,
      'telegram_configured': bool(
          self.telegram_bot_token and self.telegram_chat_id),
      'market_hours': self._is_market_hours(),
      'last_heartbeat': self.last_heartbeat.strftime(
          '%Y-%m-%d %H:%M:%S') if self.last_heartbeat else None,
      'last_signal_time': self.last_signal_time.strftime(
          '%Y-%m-%d %H:%M:%S') if self.last_signal_time else None
    }

  def get_current_status(self) -> Dict:
    """현재 상태 조회"""
    status = {
      'is_monitoring': self.is_monitoring,
      'watchlist_count': len(self.watchlist),
      'last_alerts_count': len(self.last_alerts),
      'telegram_configured': bool(
          self.telegram_bot_token and self.telegram_chat_id),
      'scan_count': self.scan_count,
      'total_signals_sent': self.total_signals_sent
    }

    return status

  def add_to_watchlist(self, symbols: List[str]):
    """감시 목록에 종목 추가"""
    for symbol in symbols:
      if symbol not in self.watchlist:
        self.watchlist.append(symbol)
        self.logger.info(f"Added {symbol} to watchlist")

  def remove_from_watchlist(self, symbols: List[str]):
    """감시 목록에서 종목 제거"""
    for symbol in symbols:
      if symbol in self.watchlist:
        self.watchlist.remove(symbol)
        self.logger.info(f"Removed {symbol} from watchlist")

  def get_market_overview(self) -> pd.DataFrame:
    """시장 개요 조회"""
    overview_data = []

    self.logger.info("Generating market overview...")

    for symbol in self.watchlist:
      try:
        signals = self.check_signals(symbol)
        if signals:
          overview_data.append({
            'Symbol': symbol,
            'Price': f"${signals['price']:.2f}",
            'RSI': f"{signals['rsi']:.1f}",
            'BB_Position': f"{signals['bb_position']:.2f}",
            'Vol_Squeeze': '🔥' if signals['volatility_squeeze'] else '❄️',
            'Buy_Signal': '🚀' if signals['buy_signal'] else '',
            'Sell_50': '💡' if signals['sell_50_signal'] else '',
            'Sell_All': '🔴' if signals['sell_all_signal'] else ''
          })
      except Exception as e:
        self.logger.error(f"Error in overview for {symbol}: {e}")

    return pd.DataFrame(overview_data)

  def manual_scan(self, symbol: str = None):
    """수동 스캔"""
    if symbol:
      self.logger.info(f"Manual scan for {symbol}")
      self.scan_single_stock(symbol)
    else:
      self.logger.info("Manual scan for all stocks")
      self.scan_all_stocks()

  def test_telegram_connection(self):
    """텔레그램 연결 테스트"""
    test_message = f"""🧪 <b>연결 테스트</b>

텔레그램 봇이 정상적으로 작동합니다!
테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ 알림 수신 준비 완료
💓 Heartbeat 기능 활성화됨
🇰🇷 한국 시간 기준 미국 장시간 체크
📬 Use /ticker <symbol> to analyze a stock (e.g., /ticker AAPL or /ticker aapl)"""

    success = self.send_telegram_alert(test_message)
    if success:
      self.logger.info("Telegram connection test successful")
    else:
      self.logger.error("Telegram connection test failed")

    return success


def main():
  """메인 실행 함수"""
  TELEGRAM_BOT_TOKEN = os.getenv('US_BOLLINGER_TELEGRAM_BOT_TOKEN')
  TELEGRAM_CHAT_ID = os.getenv('US_BOLLINGER_TELEGRAM_CHAT_ID')

  monitor = RealTimeVolatilityMonitor(
      telegram_bot_token=TELEGRAM_BOT_TOKEN,
      telegram_chat_id=TELEGRAM_CHAT_ID
  )

  print("=== 실시간 변동성 폭파 모니터링 시스템 ===")
  print("💓 Heartbeat 기능: 1시간마다 상태 알림")
  print("🇰🇷 한국 시간 기준 미국 장시간 정확 체크")
  print(
      "📬 Use /ticker <symbol> to analyze a stock (e.g., /ticker AAPL or /ticker aapl)")

  if monitor.telegram_bot_token:
    monitor.test_telegram_connection()

  try:
    print("\n현재 시장 개요:")
    overview = monitor.get_market_overview()
    if not overview.empty:
      print(overview.to_string(index=False))

    market_info = monitor.get_market_time_info()
    if market_info:
      print(f"\n시장 시간 정보:")
      print(f"🇰🇷 한국 시간: {market_info.get('korea_time')}")
      print(f"🇺🇸 미국 시간: {market_info.get('us_time')}")
      print(
          f"📊 장 상태: {'🟢 개장' if market_info.get('is_market_open') else '🔴 마감'}")
      if market_info.get('next_open_korea'):
        print(f"📅 다음 개장: {market_info.get('next_open_korea')}")

    print("\n실시간 모니터링 시작...")
    monitor.run_continuous_monitoring(scan_interval=300)

  except KeyboardInterrupt:
    print("\n모니터링 종료 중...")
    monitor.stop_monitoring()
    print("모니터링이 종료되었습니다.")

  except Exception as e:
    print(f"오류 발생: {e}")
    monitor.stop_monitoring()


if __name__ == "__main__":
  main()
