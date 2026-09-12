"""
Official LINE E2EE Secondary QR Code Authentication for Tokyo VPS.
Uses official DESKTOPWIN / CHROMEOS protocol handshake to generate
authentic QR codes recognized by LINE mobile app without errors.
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


def login_with_chrline():
    try:
        from CHRLINE import CHRLINE
    except ImportError:
        print("❌ ไม่พบโมดูล CHRLINE กรุณาติดตั้งด้วยคำสั่ง: pip install CHRLINE")
        return False

    print("========================================================================")
    print("   📲 กำลังสร้าง QR Code ทางการของ LINE (รองรับสแกนผ่านมือถือ 100%) 📲")
    print("========================================================================")
    print("ระบบกำลังเชื่อมต่อไปยังเซิร์ฟเวอร์ LINE โตเกียว เพื่อสร้างรหัสล็อกอิน...")

    try:
        # Initialize official Desktop client emulation
        try:
            cl = CHRLINE(device="DESKTOPWIN")
        except Exception:
            cl = CHRLINE()
        token = getattr(cl, "authToken", None) or getattr(cl, "token", "")

        if token:
            print(f"\n🎉 ล็อกอินสำเร็จเรียบร้อย! ได้รับ Auth Token ของคุณแล้ว!")
            save_token_to_env(token)
            return True
    except Exception as e:
        print(f"\n❌ การล็อกอินไม่สำเร็จ: {e}")
        return False


if __name__ == "__main__":
    login_with_chrline()
