#!/usr/bin/env bash
# ==============================================================================
# ⚡ 1-Click Setup Script for LINE OpenChat Tokyo Cloud Protocol Sniper (< 20ms)
# Recommended OS: Ubuntu 22.04 / 24.04 LTS on Tokyo VPS (Vultr / AWS Lightsail)
# ==============================================================================

set -e

echo "=========================================================================="
echo "   🚀 ติดตั้งระบบ LINE OpenChat Protocol Sniper บน Tokyo Cloud VPS"
echo "=========================================================================="

# 1. Update system packages
echo "📦 [1/5] ทำการอัปเดตระบบและติดตั้งแพ็กเกจพื้นฐาน..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl htop

# 2. Setup Project Directory
INSTALL_DIR="/opt/chat-line-bot"
echo "📂 [2/5] ตั้งค่าโฟลเดอร์ระบบที่ $INSTALL_DIR..."
if [ ! -d "$INSTALL_DIR" ]; then
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown -R $USER:$USER "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# 3. Create Python Virtual Environment
echo "🐍 [3/5] สร้าง Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Dependencies
echo "📥 [4/5] ติดตั้ง Dependencies ความเร็วสูง (HTTP/2, Thrift, WebSocket)..."
pip install --upgrade pip
pip install fastapi uvicorn pydantic pydantic-settings python-dotenv aiosqlite httpx[http2] requests pycryptodome websockets qrcode pillow

# 5. Create systemd service for 24/7 background operation
echo "⚙️ [5/5] สร้าง Systemd Service (ทำงานอัตโนมัติ 24 ชม. และเริ่มใหม่เองเมื่อเซิร์ฟเวอร์รีบูต)..."
sudo tee /etc/systemd/system/line-tokyo-sniper.service > /dev/null <<EOF
[Unit]
Description=LINE OpenChat Tokyo Cloud Protocol Sniper (<20ms)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python -m gateways.cloud_protocol_sniper.runner
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PORT=8080

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable line-tokyo-sniper.service

echo ""
echo "=========================================================================="
echo "   🎉 การติดตั้งเสร็จสมบูรณ์ 100%!"
echo "=========================================================================="
echo "คำสั่งที่ใช้ควบคุมบอท:"
echo "   - ทดสอบรันสดดูหน้าจอ:      source venv/bin/activate && python -m gateways.cloud_protocol_sniper.runner"
echo "   - เริ่มทำงานเบื้องหลัง 24 ชม.: sudo systemctl start line-tokyo-sniper"
echo "   - ตรวจสอบสถานะการทำงาน:     sudo systemctl status line-tokyo-sniper"
echo "   - ดู Log สดแบบเรียลไทม์:    sudo journalctl -u line-tokyo-sniper -f"
echo "   - ตรวจสอบผ่าน Browser:      http://<IP_SERVER_ของคุณ>:8080/status"
echo "=========================================================================="
