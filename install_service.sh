# ===================================================================================
# 6. install_service.sh - systemd 서비스 설치 (선택사항)
# ===================================================================================

#!/bin/bash
# install_service.sh

echo "🔧 systemd 서비스 설치"
echo "===================="

# 현재 디렉토리
CURRENT_DIR="$(pwd)"
USER_NAME="$(whoami)"

# 서비스 파일 생성
SERVICE_FILE="/tmp/volatility-monitor.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Volatility Bollinger Band Monitor
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/main.py --mode monitor-default
Restart=always
RestartSec=30
StandardOutput=append:$CURRENT_DIR/output_files/logs/service.log
StandardError=append:$CURRENT_DIR/output_files/logs/service_error.log

[Install]
WantedBy=multi-user.target
EOF

echo "📝 서비스 파일 생성됨: $SERVICE_FILE"
echo "🔐 sudo 권한이 필요합니다..."

# 서비스 설치
sudo cp "$SERVICE_FILE" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable volatility-monitor.service

echo "✅ 서비스가 설치되었습니다!"
echo ""
echo "📖 사용법:"
echo "   sudo systemctl start volatility-monitor    # 서비스 시작"
echo "   sudo systemctl stop volatility-monitor     # 서비스 중지"
echo "   sudo systemctl status volatility-monitor   # 서비스 상태"
echo "   sudo systemctl restart volatility-monitor  # 서비스 재시작"
echo ""
echo "🚀 서비스 시작하려면: sudo systemctl start volatility-monitor"
