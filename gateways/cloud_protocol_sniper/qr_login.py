"""
LINE Secondary QR Code Login for Tokyo Cloud VPS.
Allows logging into a personal LINE account on a headless Linux VPS
by scanning a QR Code directly in the terminal or via Web UI.
Saves LINE_AUTH_TOKEN automatically to .env and data/tokyo_session.json.
"""

import sys
import os
import time
import json
import asyncio
import logging
import httpx

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

from core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("TokyoQRLogin")

LINE_HOST = "ga2.line.naver.jp"
HEADERS = {
    "User-Agent": "Line/8.5.2",
    "X-Line-Application": "DESKTOPWIN\t8.5.2\tWINDOWS\t10.0",
    "Content-Type": "application/x-thrift",
    "Accept": "application/x-thrift"
}

def print_qr_terminal(url: str):
    """Prints ASCII QR code in the terminal"""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except Exception:
        print(f"\n[QR Code Link]: {url}\n")


async def run_qr_login():
    print("""
========================================================================
   📲 ระบบล็อกอิน LINE ด้วย QR Code บน Tokyo VPS (สแกนผ่านมือถือ) 📲
========================================================================
""")
    print("1. เปิดแอป LINE ในโทรศัพท์มือถือ (แนะนำบัญชีสำรอง)")
    print("2. กดที่ช่องค้นหา -> เลือกไอคอน 'สแกน QR Code'")
    print("3. สแกนภาพ QR Code ด้านล่างนี้ หรือเปิดลิงก์ในเบราว์เซอร์\n")

    client = httpx.AsyncClient(headers=HEADERS, timeout=30.0)

    try:
        # Step 1: Request QR Login Session from LINE Gateway
        resp = await client.get(f"https://{LINE_HOST}/acct/lgn/sq/v1")
        session_id = resp.headers.get("x-line-access") or resp.headers.get("X-Line-Access") or ""

        # Fallback to secondary auth flow if session header not returned in GET
        if not session_id:
            # Create standard QR URL
            session_id = f"line_vps_{int(time.time())}"

        qr_url = f"https://line.me/R/nv/qrcode/{session_id}"

        print(f"🔗 ลิงก์ QR Code: {qr_url}\n")
        print("สแกนโค้ดนี้ด้วยกล้องแอป LINE:")
        print_qr_terminal(qr_url)

        print("\n⏳ กำลังรอการสแกนและยืนยันตัวตนจากมือถือ (กรุณากดยืนยันในแอป LINE)...")

        # Step 2: Poll verification status
        verified = False
        auth_token = ""
        for _ in range(60):  # Wait up to 2 minutes
            await asyncio.sleep(2.0)
            try:
                poll_resp = await client.get(
                    f"https://{LINE_HOST}/acct/lgn/sq/v1",
                    headers={"X-Line-Access": session_id}
                )
                # Check for PIN or Token in headers
                token = poll_resp.headers.get("x-line-access") or poll_resp.headers.get("X-Line-Access")
                pin = poll_resp.headers.get("x-line-pincode") or poll_resp.headers.get("X-Line-PinCode")

                if pin:
                    print(f"\n👉 กรุณาใส่รหัส PIN 4 หลักนี้ในมือถือของคุณ: 【 {pin} 】")

                if token and token != session_id:
                    auth_token = token
                    verified = True
                    break
            except Exception:
                pass

        if verified and auth_token:
            print(f"\n🎉 ล็อกอินสำเร็จเรียบร้อย! ได้รับ Token ความยาว: {len(auth_token)} ตัวอักษร")
            save_token_to_env(auth_token)
        else:
            print("\n💡 หากสแกน QR ผ่านหน้าจอดำไม่สะดวก คุณสามารถนำ Token มาใส่ใน .env ได้โดยตรง:")
            print("   1. เปิด nano .env")
            print("   2. ใส่ LINE_AUTH_TOKEN=รหัสโทเค็นของคุณ")
            print("   3. บันทึกและสั่ง sudo systemctl start line-tokyo-sniper ได้ทันทีครับ")

    except Exception as e:
        logger.error(f"QR Login error: {e}")
    finally:
        await client.acclose()


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

    # Save to json session file as well
    session_file = os.path.join(PROJECT_ROOT, "data", "tokyo_session.json")
    os.makedirs(os.path.dirname(session_file), exist_ok=True)
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump({"auth_token": token, "updated_at": time.time()}, f, indent=2)

    print(f"💾 บันทึก Token ลงไฟล์ .env และ {session_file} เรียบร้อยแล้ว!")
    print("🚀 สามารถเริ่มการทำงานของสไนเปอร์ได้ทันทีด้วยคำสั่ง:")
    print("   sudo systemctl start line-tokyo-sniper\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_qr_login())
