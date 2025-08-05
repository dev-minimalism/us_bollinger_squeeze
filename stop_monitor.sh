# ===================================================================================
# 2. stop_monitor.sh - 백그라운드 모니터링 중지 스크립트
# ===================================================================================

#!/bin/bash
# stop_monitor.sh

echo "⏹️  변동성 폭파 모니터링 중지"
echo "=========================="

# PID 파일 경로
PID_FILE="output_files/monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ 실행 중인 모니터링을 찾을 수 없습니다."
    echo "💡 수동으로 중지하려면: pkill -f 'main.py.*monitor-default'"
    exit 1
fi

# PID 읽기
PID=$(cat "$PID_FILE")

# 프로세스가 실행 중인지 확인
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "❌ PID $PID 프로세스가 실행 중이 아닙니다."
    rm -f "$PID_FILE"
    exit 1
fi

echo "🛑 모니터링 프로세스 중지 중... (PID: $PID)"

# SIGTERM 신호 전송 (graceful shutdown)
kill -TERM "$PID"

# 최대 10초 대기
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ 모니터링이 안전하게 중지되었습니다."
        rm -f "$PID_FILE"
        exit 0
    fi
    echo "⏳ 종료 대기 중... ($i/10)"
    sleep 1
done

# 강제 종료
echo "⚠️  강제 종료 실행..."
kill -KILL "$PID"
rm -f "$PID_FILE"
echo "🛑 모니터링이 강제 종료되었습니다."
