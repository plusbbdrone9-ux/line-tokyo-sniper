"""
Official LINE E2EE Modern QR Code Authentication for Tokyo VPS & Local PC.
Uses modern LINE Desktop Protocol (Line/9.2.0.3400) to generate authentic
QR codes recognized by LINE mobile app without error 403.
"""

import sys
import os
import time
import json
import logging

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("TokyoVPSAuth")

def save_token_to_env(token: str):
    """Saves auth token to .env and data/tokyo_session.json"""
    env_path = os.path.join(PROJECT_ROOT, ".env")
    lines = []
    token_set = False

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("LINE_AUTH_TOKEN="):
                    lines.append(f"LINE_AUTH_TOKEN={token}\n")
                    token_set = True
                else:
                    lines.append(line)

    if not token_set:
        lines.append(f"\nLINE_AUTH_TOKEN={token}\n")
        lines.append("LINE_TOKYO_HOST=ga2.line.naver.jp\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    session_file = os.path.join(PROJECT_ROOT, "data", "tokyo_session.json")
    os.makedirs(os.path.dirname(session_file), exist_ok=True)
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump({"auth_token": token, "updated_at": time.time()}, f, indent=2)

    print(f"\n💾 บันทึก Token ลงไฟล์ .env และ {session_file} เรียบร้อยแล้ว!")
    print("🚀 สามารถเริ่มระบบสไนเปอร์ทำงาน 24 ชม. ได้ทันทีด้วยคำสั่ง:")
    print("   sudo systemctl start line-tokyo-sniper\n")


def login_modern_qr():
    try:
        import CHRLINE
    except ImportError:
        print("❌ ไม่พบโมดูล CHRLINE กรุณาติดตั้งด้วยคำสั่ง: pip install CHRLINE")
        return False

    print("========================================================================")
    print("   📲 ระบบสร้าง QR Code ทางการของ LINE (เวอร์ชันใหม่ Line/9.2.0) 📲")
    print("========================================================================")
    print("ระบบกำลังเชื่อมต่อไปยังเซิร์ฟเวอร์ LINE โตเกียว เพื่อสร้างรหัสล็อกอิน...\n")

    try:
        # Initialize with modern official desktop protocol
        cl = CHRLINE.CHRLINE(device="DESKTOPWIN", version="9.2.0.3400", noLogin=True)
        cl.USER_AGENT = "Line/9.2.0.3400"

        # 1. Create Session & QR
        session_resp = cl.createSession()
        sqr = cl.checkAndGetValue(session_resp, 1, "val_1")
        qr_resp = cl.createQrCode(sqr)
        url = cl.checkAndGetValue(qr_resp, 1, "val_1")

        secret, secretUrl = cl.createSqrSecret()
        full_url = url + secretUrl

        # 2. Serve clean high-res QR code on Web Browser (http://IP:8080/qr)
        import qrcode
        import io
        import base64
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading

        qr = qrcode.QRCode(border=1)
        qr.add_data(full_url)
        img_buf = io.BytesIO()
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(img_buf, format="PNG")
        png_b64 = base64.b64encode(img_buf.getvalue()).decode("ascii")

        html_page = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>LINE Tokyo VPS QR Login</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ background: #0b1120; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
    .card {{ background: #1e293b; padding: 30px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 2px solid #06c755; text-align: center; max-width: 360px; }}
    h2 {{ color: #06c755; margin: 0 0 10px 0; font-size: 22px; }}
    p {{ color: #94a3b8; font-size: 14px; margin-bottom: 20px; }}
    .qr-box {{ background: white; padding: 12px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
    img {{ width: 260px; height: 260px; display: block; }}
    .hint {{ margin-top: 18px; font-size: 13px; color: #38bdf8; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>📲 สแกน QR Code เข้าสู่ระบบ</h2>
    <p>เปิดแอป LINE ในมือถือ แล้วสแกนภาพด้านล่างนี้ได้เลยครับ</p>
    <div class="qr-box">
      <img src="data:image/png;base64,{png_b64}" alt="LINE QR Code">
    </div>
    <div class="hint">⚡ เมื่อสแกนแล้ว ให้ดูเลข PIN 4 หลักบนหน้าจอ Terminal</div>
  </div>
</body>
</html>"""

        class QRServer(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_page.encode("utf-8"))

        web_srv = HTTPServer(("0.0.0.0", 8080), QRServer)
        t_web = threading.Thread(target=web_srv.serve_forever, daemon=True)
        t_web.start()

        print("========================================================================")
        print("🌟 วิธีสแกนที่ง่ายที่สุด (เปิดบน Browser สแกนได้ทันทีใน 1 วินาที):")
        print("👉 เปิดลิงก์นี้ในคอมหรือมือถือของคุณ: http://3.113.9.175:8080/qr")
        print("========================================================================\n")
        print("หรือถ้าต้องการสแกนบนหน้าจอดำ (แบบย่อขนาดพอดีจอ ไม่ล้น):")
        try:
            qr.print_ascii(invert=True)
        except Exception:
            pass

        print("\n⏳ [1/2] กำลังรอมือถือของคุณสแกน QR Code...")

        # 3. Check QR Scanned
        if cl.checkQrCodeVerified(sqr):
            print("✅ [2/2] ตรวจพบการสแกนแล้ว! กำลังตรวจสอบรหัส PIN...")
            try:
                cl.verifyCertificate(sqr, cl.getSqrCert())
            except Exception:
                pin = cl.createPinCode(sqr)
                if isinstance(pin, dict):
                    pin = cl.checkAndGetValue(pin, 1, "val_1")
                print(f"\n👉👉👉 กรุณากดใส่รหัส PIN 4 หลักนี้ในมือถือของคุณ: 【 {pin} 】 👈👈👈\n")
                cl.checkPinCodeVerified(sqr)

            # 4. Exchange for AuthToken
            login_resp = cl.qrCodeLoginV2(sqr, cl.APP_TYPE, cl.SYSTEM_NAME, True)
            try:
                cert = cl.checkAndGetValue(login_resp, 1)
                cl.saveSqrCert(cert)
            except Exception:
                pass

            tokenV3Info = cl.checkAndGetValue(login_resp, 3)
            authToken = cl.checkAndGetValue(tokenV3Info, 1)

            if authToken:
                print(f"\n🎉 ล็อกอินสำเร็จเรียบร้อย! ได้รับ Auth Token ของคุณแล้ว!")
                print(f"🔑 Auth Token: {authToken[:20]}...{authToken[-10:]}")
                save_token_to_env(authToken)
                return True
            else:
                print("❌ ไม่พบ authToken ในคำตอบจากเซิร์ฟเวอร์")
                return False

    except Exception as e:
        print(f"\n❌ การล็อกอินไม่สำเร็จ: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    login_modern_qr()
