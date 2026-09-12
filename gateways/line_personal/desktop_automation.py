"""
LINE Desktop (Windows PC) Automation Bridge
-------------------------------------------
สคริปต์นี้ใช้สำหรับรันบน Windows เพื่อเชื่อมต่อ LINE PC เข้ากับระบบ AI
วิธีการทำงาน:
1. ตรวจจับหน้าต่าง LINE PC และข้อความแชทใหม่
2. ส่งข้อความเข้า Hub ผ่าน /api/personal/incoming
3. เมื่อได้รับคำตอบจาก AI จะพิมพ์ข้อความตอบกลับไปยังหน้าต่างแชททันที
"""

import time
import requests
import pyperclip
import logging
import win32gui
import win32con
import win32api

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LineDesktopBridge")

HUB_URL = "http://127.0.0.1:8000/api/personal/incoming"
BRIDGE_SECRET = "secret-token-for-bridge"

def find_line_windows():
    """ค้นหาหน้าต่าง LINE ทั้งหมดบน Windows"""
    windows = []
    def enum_windows_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if "LINE" in title or "Line" in class_name:
                windows.append((hwnd, title, class_name))
    win32gui.EnumWindows(enum_windows_callback, None)
    return windows

def send_text_to_chat_window(hwnd, text: str):
    """ส่งข้อความภาษาไทยเข้าหน้าต่างแชทด้วยการจำลองการคลิกและ Paste เพื่อรองรับภาษาไทย 100%"""
    try:
        # ดึงหน้าต่างขึ้นมาด้านหน้า
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)

        # ก็อปปี้ข้อความลง Clipboard
        pyperclip.copy(text)

        # กด Ctrl + V
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord('V'), 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.2)

        # กด Enter เพื่อส่ง
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        logger.info("Sent message to LINE PC successfully.")
        return True
    except Exception as e:
        logger.error(f"Error sending text to LINE window: {e}")
        return False

def process_and_reply(session_id: str, sender_name: str, message_content: str, target_hwnd=None):
    """ส่งข้อความไปหา AI Hub และตอบกลับ"""
    payload = {
        "session_id": session_id,
        "sender_name": sender_name,
        "content": message_content,
        "secret": BRIDGE_SECRET
    }

    try:
        res = requests.post(HUB_URL, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("should_send") and data.get("reply_text"):
                reply_text = data["reply_text"]
                logger.info(f"AI Replying: {reply_text}")
                if target_hwnd:
                    send_text_to_chat_window(target_hwnd, reply_text)
                return reply_text
            else:
                logger.info(f"No reply needed. Reason: {data.get('reason')}")
        else:
            logger.error(f"Hub returned status {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"Failed to communicate with Hub: {e}")
    return None

if __name__ == "__main__":
    print("=" * 60)
    print(" LINE Desktop Automation Bridge Ready ")
    print("=" * 60)
    wins = find_line_windows()
    print(f"Found {len(wins)} LINE related window(s):")
    for h, t, c in wins:
        print(f" - HWND: {h} | Title: '{t}' | Class: '{c}'")

    print("\nBridge is ready for incoming events. You can integrate UI hook or run in loop.")
