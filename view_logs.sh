# ===================================================================================
# 5. view_logs.sh - 로그 실시간 보기 스크립트
# ===================================================================================

#!/bin/bash
# view_logs.sh

echo "📋 변동성 폭파 모니터링 로그 실시간 조회"
echo "=================================="

# 로그 파일 경로
LOG_FILE="output_files/logs/monitor_$(date +%Y%m%d).log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ 오늘 날짜의 로그 파일을 찾을 수 없습니다: $LOG_FILE"
    echo "📂 사용 가능한 로그 파일들:"
    if [ -d "output_files/logs" ]; then
        ls -la output_files/logs/ | grep "monitor"
    else
        echo "   로그 디렉토리가 없습니다."
    fi
    exit 1
fi

echo "📊 로그 파일: $LOG_FILE"
echo "🔄 실시간 모니터링 중... (Ctrl+C로 종료)"
echo "=================================="

# 실시간 로그 조회
tail -f "$LOG_FILE"
