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

        # 2. Print QR in terminal
        print("🔗 ลิงก์ล็อกอินทางการ:")
        print(f"   {full_url}\n")
        print("สแกนภาพ QR Code ด้านล่างนี้ด้วยกล้องของแอป LINE ในมือถือ:")
        cl.genQrcodeImageAndPrint(full_url)

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
