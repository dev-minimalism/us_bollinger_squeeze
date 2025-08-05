"""
변동성 폭파 볼린저 밴드 트레이딩 시스템 - 메인 실행 파일

사용법:
    python main.py --mode backtest    # 백테스트만 실행
    python main.py --mode monitor     # 실시간 모니터링만 실행
    python main.py --mode monitor-default  # 백그라운드 모니터링 (기본값)
    python main.py --mode both        # 백테스트 후 모니터링 실행 (기본값)

텔레그램 설정:
    export TELEGRAM_BOT_TOKEN="your_bot_token"
    export TELEGRAM_CHAT_ID="your_chat_id"
"""

import argparse
import logging
import os
import signal
import sys
from datetime import datetime, timedelta

# 모듈 import
try:
  from backtest_strategy import VolatilityBollingerBacktest
  from realtime_monitor import RealTimeVolatilityMonitor
except ImportError as e:
  print(f"❌ 모듈 import 오류: {e}")
  print("📁 backtest_strategy.py와 realtime_monitor.py 파일이 같은 디렉토리에 있는지 확인하세요.")
  sys.exit(1)

# ===================================================================================
# 로깅 설정
# ===================================================================================

def setup_logging():
  """백그라운드 실행을 위한 로깅 설정"""
  log_dir = "output_files/logs"
  os.makedirs(log_dir, exist_ok=True)

  log_filename = os.path.join(log_dir, f"monitor_{datetime.now().strftime('%Y%m%d')}.log")

  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(levelname)s - %(message)s',
      handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
      ]
  )

  return logging.getLogger(__name__)

# ===================================================================================
# 백그라운드 모니터링 (기본값)
# ===================================================================================

def run_monitor_default():
  """백그라운드 모니터링 실행 (모든 설정 기본값) - 수정된 버전"""
  logger = setup_logging()

  print("=" * 80)
  print("📡 변동성 폭파 백그라운드 모니터링 (기본 설정)")
  print("=" * 80)

  # 기본 설정값
  telegram_bot_token = os.getenv('US_BOLLINGER_TELEGRAM_BOT_TOKEN')
  telegram_chat_id = os.getenv('US_BOLLINGER_TELEGRAM_CHAT_ID')
  scan_interval = 300  # 5분 간격

  logger.info("백그라운드 모니터링 시작")
  logger.info(f"스캔 간격: {scan_interval}초 ({scan_interval // 60}분)")
  logger.info(f"로그 파일: output_files/logs/monitor_{datetime.now().strftime('%Y%m%d')}.log")

  print(f"🎯 백그라운드 모니터링 설정:")
  print(f"   📊 감시 종목: 50개 (미국 시총 상위)")
  print(f"   ⏰ 스캔 간격: 5분")
  print(f"   📱 텔레그램 알림: 활성화")
  print(f"   📝 로그 파일: output_files/logs/monitor_{datetime.now().strftime('%Y%m%d')}.log")
  print(f"   🔄 자동 재시작: 활성화")
  print(f"   🤖 텔레그램 명령어: /ticker, /status, /start")

  # 시그널 핸들러 설정 (graceful shutdown)
  def signal_handler(signum, frame):
    logger.info(f"종료 신호 수신: {signum}")
    print(f"\n⏹️ 모니터링을 안전하게 종료합니다...")
    try:
      if 'monitor' in locals():
        monitor.stop_monitoring()
    except:
      pass
    sys.exit(0)

  signal.signal(signal.SIGINT, signal_handler)
  signal.signal(signal.SIGTERM, signal_handler)

  # 모니터링 시스템 초기화
  try:
    monitor = RealTimeVolatilityMonitor(
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id
    )

    # 텔레그램 연결 테스트
    if monitor.telegram_bot_token:
      print(f"\n🤖 텔레그램 봇 연결 테스트 중...")
      if monitor.test_telegram_connection():
        print("✅ 텔레그램 연결 성공")
        print("📱 사용 가능한 명령어:")
        print("   • /ticker AAPL - 개별 종목 분석")
        print("   • /status - 모니터링 상태 확인")
        print("   • /start - 도움말 보기")
      else:
        print("⚠️ 텔레그램 연결 실패 - 로그만 출력")

    print(f"\n" + "=" * 80)
    print("🚀 백그라운드 모니터링 시작!")
    print("   - 모든 설정이 기본값으로 자동 설정되었습니다")
    print("   - 신호 발생시 텔레그램으로 즉시 알림을 전송합니다")
    print("   - 텔레그램에서 /ticker 명령어로 개별 종목 분석 가능")
    print("   - 5회 스캔마다 상태 요약을 전송합니다")
    print("   - 오류 발생시 자동으로 재시작합니다")
    print("   - 종료하려면: kill -TERM [PID] 또는 Ctrl+C")
    print("=" * 80)

    # 연속 모니터링 실행
    monitor.run_continuous_monitoring(scan_interval)

  except Exception as e:
    logger.error(f"모니터링 초기화 실패: {e}")
    print(f"❌ 모니터링 초기화 실패: {e}")
    print(f"💡 텔레그램 설정이나 네트워크 연결을 확인해주세요.")
    sys.exit(1)

# ===================================================================================
# 백테스트 실행
# ===================================================================================

def run_backtest():
  """백테스트 실행"""
  print("=" * 80)
  print("🚀 변동성 폭파 볼린저 밴드 백테스트")
  print("=" * 80)

  # 초기 자금 설정
  print(f"\n💰 초기 자금을 설정하세요:")
  print("1. $10,000 (1만 달러)")
  print("2. $50,000 (5만 달러)")
  print("3. $100,000 (10만 달러)")
  print("4. 사용자 정의")

  capital_options = {"1": 10000, "2": 50000, "3": 100000}

  try:
    capital_choice = input("\n초기 자금 선택 (1-4, 기본값: 1): ").strip() or "1"

    if capital_choice == "4":
      custom_capital = float(input("사용자 정의 금액 ($): "))
      initial_capital = custom_capital
    else:
      initial_capital = capital_options.get(capital_choice, 10000)

    print(f"✅ 선택된 초기 자금: ${initial_capital:,.2f}")

  except ValueError:
    print("잘못된 입력입니다. 기본값($10,000)으로 설정합니다.")
    initial_capital = 10000

  # 투자 전략 선택
  print(f"\n📊 투자 전략을 선택하세요:")
  print("1. 보수적 전략 (안전 우선, RSI 70)")
  print("2. 균형 전략 (적당한 위험, RSI 65)")
  print("3. 공격적 전략 (수익 추구, RSI 60)")

  try:
    strategy_choice = input("\n전략 선택 (1-3, 기본값: 2): ").strip() or "2"
    strategy_map = {"1": "conservative", "2": "balanced", "3": "aggressive"}
    strategy_mode = strategy_map.get(strategy_choice, "balanced")
  except:
    strategy_mode = "balanced"

  # 백테스트 인스턴스 생성
  backtest = VolatilityBollingerBacktest(initial_capital=initial_capital, strategy_mode=strategy_mode)

  # 백테스트 기간 설정
  end_date = datetime.now().strftime('%Y-%m-%d')
  start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')  # 2년간

  print(f"📅 분석 기간: {start_date} ~ {end_date} (약 2년)")

  # 종목 수 선택
  print(f"\n📊 분석할 종목 수를 선택하세요:")
  print("1. 10개 종목 (빠름)")
  print("2. 20개 종목 (표준)")
  print("3. 30개 종목")
  print("4. 전체 50개 종목 (시간 오래 걸림)")

  stock_options = {"1": 10, "2": 20, "3": 30, "4": 50}

  max_stocks = 20
  analysis_mode = "top5"
  description = "표준 분석"
  backtest_choice = "3"
  save_charts = True

  try:
    stock_choice = input("\n종목 수 선택 (1-4, 기본값: 2): ").strip() or "2"
    max_stocks = stock_options.get(stock_choice, 20)

    print(f"✅ 선택된 종목 수: {max_stocks}개")

    analysis_options = {
      "1": ("top3", "빠른 분석 (상위 3개 종목 상세분석)"),
      "2": ("top5", "표준 분석 (상위 5개 종목 상세분석)"),
      "3": ("positive", "수익 종목 전체 상세분석"),
      "4": ("all", "전체 종목 상세분석 (매우 오래 걸림)"),
      "5": ("none", "요약만 (상세 분석 없음)")
    }

    print(f"\n📈 상세 분석 모드를 선택하세요:")
    for key, (mode, desc) in analysis_options.items():
      print(f"{key}. {desc}")

    choice = input(f"\n선택 (1-5, 기본값: 2): ").strip() or "2"
    analysis_mode, description = analysis_options.get(choice, ("top5", "표준 분석"))

    print(f"✅ 선택된 분석 모드: {description}")
    print(f"📊 총 {max_stocks}개 종목 백테스트 + {description}")

    print(f"\n📊 백테스트 유형을 선택하세요:")
    print("1. 개별 종목 분석 (각 종목별 독립 분석)")
    print("2. 기존 포트폴리오 (종목별 균등 배분)")
    print("3. 진정한 통합 포트폴리오 (동적 자금 관리) ⭐ 추천")
    print("4. 개별 + 진정한 통합 (둘 다 실행)")

    try:
      backtest_choice = input("\n백테스트 유형 (1-4, 기본값: 3): ").strip() or "3"

      if backtest_choice == "1":
        run_individual = True
        run_old_portfolio = False
        run_true_portfolio = False
      elif backtest_choice == "2":
        run_individual = False
        run_old_portfolio = True
        run_true_portfolio = False
      elif backtest_choice == "3":
        run_individual = False
        run_old_portfolio = False
        run_true_portfolio = True
      else:
        run_individual = True
        run_old_portfolio = False
        run_true_portfolio = True

    except:
      run_individual = False
      run_old_portfolio = False
      run_true_portfolio = True

    if analysis_mode != "none" and run_individual:
      chart_choice = input(
          "\n차트 저장 방식을 선택하세요 (1: 파일저장, 2: 화면출력, 기본값: 1): ").strip() or "1"
      save_charts = (chart_choice == "1")

      if save_charts:
        print("✅ 차트는 'output_files/charts/' 폴더에 PNG 파일로 저장됩니다.")
      else:
        print("✅ 차트는 화면에 출력됩니다.")

    if max_stocks >= 30:
      print(f"⚠️ {max_stocks}개 종목 분석은 시간이 오래 걸릴 수 있습니다.")
    if analysis_mode == "all":
      print(f"⚠️ 전체 종목 상세분석은 매우 오래 걸립니다.")

    if run_true_portfolio:
      print(f"\n🚀 진정한 통합 포트폴리오 백테스트 실행...")
      true_portfolio_result = backtest.run_true_portfolio_backtest(start_date, end_date, max_stocks=max_stocks)

      if true_portfolio_result:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chart_filename = f"true_portfolio_performance_{timestamp}.png"
        backtest.plot_portfolio_performance(true_portfolio_result, save_path=chart_filename)

        result_filename = f"true_portfolio_backtest_{timestamp}.csv"
        backtest.save_portfolio_results(true_portfolio_result, result_filename)

        print(f"\n🎉 진정한 통합 포트폴리오 백테스트 완료!")
      else:
        print("❌ 진정한 통합 포트폴리오 백테스트 실패")

    elif run_old_portfolio:
      print(f"\n🚀 기존 포트폴리오 백테스트 실행...")
      portfolio_result = backtest.run_portfolio_backtest(start_date, end_date, max_stocks=max_stocks)

      if portfolio_result:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chart_filename = f"old_portfolio_performance_{timestamp}.png"
        backtest.plot_portfolio_performance(portfolio_result, save_path=chart_filename)
        backtest.save_portfolio_results(portfolio_result)
        print(f"\n🎉 기존 포트폴리오 백테스트 완료!")
      else:
        print("❌ 기존 포트폴리오 백테스트 실패")

    elif analysis_mode == "none":
      results_df = backtest.run_multi_stock_backtest(start_date, end_date, max_stocks=max_stocks)
      if not results_df.empty:
        backtest._print_summary_statistics(results_df)
        backtest.save_results_to_csv(results_df)
      else:
        print("❌ 백테스트 결과가 없습니다.")
    else:
      if run_individual:
        print(f"\n🔍 개별 종목 분석 실행...")
        comprehensive_results = backtest.run_comprehensive_analysis(
            start_date=start_date,
            end_date=end_date,
            max_stocks=max_stocks,
            detailed_analysis=analysis_mode,
            save_charts=save_charts
        )

        if comprehensive_results:
          print(f"\n✅ 개별 종목 분석 완료!")
          print(f"📊 총 {len(comprehensive_results.get('summary_results', []))}개 종목 분석")
          print(f"📈 상세 분석: {len(comprehensive_results.get('detailed_results', []))}개 종목")
        else:
          print("❌ 개별 종목 분석 실패")

      if backtest_choice == "4":
        print(f"\n💼 진정한 통합 포트폴리오 백테스트 추가 실행...")
        true_portfolio_result = backtest.run_true_portfolio_backtest(start_date, end_date, max_stocks=max_stocks)

        if true_portfolio_result:
          timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
          chart_filename = f"true_portfolio_performance_{timestamp}.png"
          backtest.plot_portfolio_performance(true_portfolio_result, save_path=chart_filename)
          result_filename = f"true_portfolio_backtest_{timestamp}.csv"
          backtest.save_portfolio_results(true_portfolio_result, result_filename)
          print(f"\n🎉 진정한 통합 포트폴리오 백테스트도 완료!")
        else:
          print("❌ 진정한 통합 포트폴리오 백테스트 실패")

  except KeyboardInterrupt:
    print(f"\n⏹️ 사용자에 의해 백테스트가 중단되었습니다.")
  except Exception as e:
    print(f"❌ 백테스트 중 오류 발생: {e}")
    print(f"\n🔄 기본 백테스트를 실행합니다...")
    print(f"📊 사용자가 선택한 {max_stocks}개 종목으로 기본 분석을 진행합니다.")

    try:
      results_df = backtest.run_multi_stock_backtest(start_date, end_date, max_stocks=max_stocks)
      if not results_df.empty:
        print(f"\n📊 기본 백테스트 결과 (상위 5개):")
        print(results_df.head().to_string(index=False))
        backtest.save_results_to_csv(results_df)

        total_stocks = len(results_df)
        profitable_stocks = len(results_df[results_df['Total_Return(%)'] > 0])
        avg_return = results_df['Total_Return(%)'].mean()

        print(f"\n📈 간단 요약:")
        print(f"   성공 종목: {total_stocks}개")
        print(f"   수익 종목: {profitable_stocks}개 ({profitable_stocks / total_stocks * 100:.1f}%)")
        print(f"   평균 수익률: {avg_return:.2f}%")

      else:
        print("❌ 기본 백테스트 결과도 없습니다.")

    except Exception as fallback_error:
      print(f"❌ 기본 백테스트도 실패했습니다: {fallback_error}")
      print(f"\n🔄 최소 설정(10개 종목)으로 재시도합니다...")
      try:
        results_df = backtest.run_multi_stock_backtest(start_date, end_date, max_stocks=10)
        if not results_df.empty:
          print(f"✅ 최소 설정 백테스트 성공!")
          print(results_df.head().to_string(index=False))
          backtest.save_results_to_csv(results_df)
        else:
          print("❌ 모든 백테스트 시도가 실패했습니다.")
      except Exception as final_error:
        print(f"❌ 최소 설정 백테스트도 실패: {final_error}")
        print(f"💡 네트워크 연결이나 Yahoo Finance API 상태를 확인해주세요.")

# ===================================================================================
# 실시간 모니터링 실행
# ===================================================================================

def run_monitor():
  """실시간 모니터링 실행 (대화형) - 수정된 버전"""
  print("=" * 80)
  print("📡 변동성 폭파 실시간 자동 모니터링")
  print("=" * 80)

  telegram_bot_token = os.getenv('US_BOLLINGER_TELEGRAM_BOT_TOKEN')
  telegram_chat_id = os.getenv('US_BOLLINGER_TELEGRAM_CHAT_ID')

  if not telegram_bot_token or not telegram_chat_id:
    print("⚠️ 텔레그램 설정이 필요합니다!")
    print("💡 설정 방법:")
    print("   1. @BotFather에서 봇 생성 후 토큰 획득")
    print("   2. @userinfobot에서 chat_id 확인")
    print("   3. 환경변수 설정:")
    print("      export TELEGRAM_BOT_TOKEN='your_bot_token'")
    print("      export TELEGRAM_CHAT_ID='your_chat_id'")
    print("\n❌ 텔레그램 설정 없이는 모니터링을 실행할 수 없습니다.")
    return
  else:
    print("✅ 텔레그램 설정 확인됨")

  print(f"\n⚙️ 모니터링 설정:")
  print("1. 5분 간격 (기본값)")
  print("2. 10분 간격")
  print("3. 15분 간격")
  print("4. 30분 간격")
  print("5. 사용자 정의")

  interval_options = {"1": 300, "2": 600, "3": 900, "4": 1800}

  try:
    choice = input("\n스캔 간격 선택 (1-5, 기본값: 1): ").strip() or "1"

    if choice == "5":
      custom_minutes = int(input("사용자 정의 간격 (분): "))
      scan_interval = custom_minutes * 60
    else:
      scan_interval = interval_options.get(choice, 300)

    print(f"✅ 스캔 간격: {scan_interval}초 ({scan_interval // 60}분)")

  except ValueError:
    print("잘못된 입력입니다. 기본값(5분)으로 설정합니다.")
    scan_interval = 300

  monitor = RealTimeVolatilityMonitor(
      telegram_bot_token=telegram_bot_token,
      telegram_chat_id=telegram_chat_id
  )

  print(f"\n🎯 모니터링 설정 완료:")
  print(f"   📊 감시 종목: {len(monitor.watchlist)}개 (미국 시총 50위)")
  print(f"   ⏰ 스캔 간격: {scan_interval // 60}분")
  print(f"   📱 텔레그램 알림: 활성화")
  print(f"   🕐 시장 시간 체크: 자동")
  print(f"   🤖 텔레그램 명령어: /ticker, /status, /start")

  # 텔레그램 연결 테스트
  print(f"\n🤖 텔레그램 봇 연결 테스트 중...")
  if monitor.test_telegram_connection():
    print("✅ 텔레그램 연결 성공")
    print("📱 사용 가능한 명령어:")
    print("   • /ticker AAPL - 개별 종목 분석")
    print("   • /status - 모니터링 상태 확인")
    print("   • /start - 도움말 보기")
  else:
    print("⚠️ 텔레그램 연결 실패 - 로그만 출력")

  print(f"\n" + "=" * 80)
  print("🚀 자동 모니터링을 시작합니다!")
  print("   - 명령어 입력 없이 자동으로 50개 종목을 모니터링합니다")
  print("   - 신호 발생시 텔레그램으로 즉시 알림을 전송합니다")
  print("   - 텔레그램에서 /ticker 명령어로 개별 종목 분석 가능")
  print("   - 5회 스캔마다 상태 요약을 전송합니다")
  print("   - 종료하려면 Ctrl+C를 누르세요")
  print("=" * 80)

  monitor.run_continuous_monitoring(scan_interval)

# ===================================================================================
# 메인 실행 함수
# ===================================================================================

def main():
  """메인 실행 함수"""
  parser = argparse.ArgumentParser(
      description='🚀 변동성 폭파 볼린저 밴드 트레이딩 시스템',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
📖 사용 예시:
    python main.py --mode backtest         # 백테스트만 실행
    python main.py --mode monitor          # 실시간 모니터링 (대화형)
    python main.py --mode monitor-default  # 백그라운드 모니터링 (기본값)
    python main.py --mode both             # 백테스트 후 모니터링 실행 (기본값)
  
📱 텔레그램 설정:
    1. @BotFather에서 봇 생성
    2. 봇 토큰 획득
    3. @userinfobot에서 chat_id 확인
    4. 환경변수 설정:
       export TELEGRAM_BOT_TOKEN="your_bot_token"
       export TELEGRAM_CHAT_ID="your_chat_id"

🎯 전략 개요:
    - 변동성 압축 감지 (밴드폭 < 최근 50일 중 20% 하위)
    - RSI > 70 + 변동성 압축 시 매수
    - 분할 익절: BB 80% 위치에서 50% → 하단에서 나머지

🔄 백그라운드 실행 (우분투):
    nohup python main.py --mode monitor-default > /dev/null 2>&1 &
    # 또는
    python main.py --mode monitor-default &
        """
  )

  parser.add_argument(
      '--mode', '-m',
      choices=['backtest', 'monitor', 'monitor-default', 'both'],
      default='both',
      help='실행 모드 (기본값: both)'
  )

  args = parser.parse_args()

  print("🚀" + "=" * 78 + "🚀")
  print("     변동성 폭파 볼린저 밴드 트레이딩 시스템")
  print("🚀" + "=" * 78 + "🚀")
  print(f"⚙️ 실행 모드: {args.mode.upper()}")
  print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
  print(f"🐍 Python 버전: {sys.version.split()[0]}")
  print(f"📬 Telegram Commands: Use /ticker to analyze a stock (e.g., /AAPL)")

  try:
    if args.mode in ['backtest', 'both']:
      run_backtest()

      if args.mode == 'both':
        print(f"\n" + "=" * 80)
        print("🎯 백테스트가 완료되었습니다!")
        print("📡 실시간 모니터링을 시작하려면 Enter를 누르세요...")
        print("🛑 종료하려면 Ctrl+C를 누르세요.")
        print("=" * 80)
        input()

    if args.mode in ['monitor', 'both']:
      run_monitor()

    elif args.mode == 'monitor-default':
      run_monitor_default()

  except KeyboardInterrupt:
    print(f"\n⏹️ 사용자에 의해 프로그램이 중단되었습니다.")

  except Exception as e:
    print(f"❌ 예상치 못한 오류가 발생했습니다: {e}")
    print(f"🔧 문제가 지속되면 GitHub Issues에 보고해주세요.")

  finally:
    print(f"\n🏁 프로그램을 종료합니다.")
    print(f"📅 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💖 Happy Trading!")

if __name__ == "__main__":
  main()
