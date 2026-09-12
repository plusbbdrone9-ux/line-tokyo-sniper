"""
Android / LDPlayer Automation Bridge for Personal LINE
-------------------------------------------------------
เชื่อมต่อ LDPlayer หรือเครื่อง Android ผ่าน ADB / UIAutomator2
เพื่ออ่านแชท LINE ส่วนบุคคล และตอบกลับอัตโนมัติด้วย AI 24 ชั่วโมง
"""

import time
import requests
import logging
import re
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AndroidLineBridge")

HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8000/api/personal/incoming")
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "secret-token-for-bridge")

class AndroidLineBot:
    def __init__(self, device_serial: str = None):
        self.device_serial = device_serial
        self.d = None
        self._init_device()

    def _init_device(self):
        try:
            import uiautomator2 as u2
            if self.device_serial:
                self.d = u2.connect(self.device_serial)
            else:
                self.d = u2.connect()  # Connects to the primary device / LDPlayer
            logger.info(f"Connected to Android device: {self.d.device_info.get('model', 'Unknown')}")
        except Exception as e:
            logger.warning(f"Could not connect to Android via uiautomator2: {e}")
            logger.info("Make sure LDPlayer or Android device is running with USB Debugging enabled.")

    def listen_and_reply_loop(self, poll_interval: float = 3.0):
        """
        วนลูปตรวจจับข้อความเข้าใหม่ในหน้าแชท LINE
        """
        if not self.d:
            logger.error("Device not connected. Exiting loop.")
            return

        logger.info("Starting Android LINE automation loop...")
        last_seen_message = ""

        while True:
            try:
                # ตรวจสอบว่าแอป LINE เปิดอยู่หรือไม่
                current_app = self.d.app_current()
                if "jp.naver.line.android" not in current_app.get("package", ""):
                    time.sleep(poll_interval)
                    continue

                # ดึงข้อความล่าสุดจาก Bubble แชทใน LINE
                # คลาสข้อความแชทใน LINE มักเป็น TextView หรือ View ใน ListView / RecyclerView
                chat_texts = self.d(resourceIdMatches=".*chat_bubble.*|.*message_text.*|.*text1.*")
                
                if chat_texts.exists:
                    # หาข้อความล่าสุด (element สุดท้าย)
                    latest_element = chat_texts[-1]
                    content = latest_element.get_text()

                    if content and content != last_seen_message:
                        logger.info(f"New chat detected on Android: {content}")
                        last_seen_message = content

                        # ดึงชื่อคู่สนทนาจากส่วนหัวของห้องแชท
                        title_elem = self.d(resourceIdMatches=".*header_title.*|.*room_name.*|.*action_bar_title.*")
                        sender_name = title_elem.get_text() if title_elem.exists else "LINE Friend"
                        session_id = f"personal_{sender_name.strip()}"

                        # ส่งข้อความไปให้ AI Hub
                        self._handle_message(session_id, sender_name, content)

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info("Automation stopped by user.")
                break
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                time.sleep(poll_interval)

    def _handle_message(self, session_id: str, sender_name: str, content: str):
        payload = {
            "session_id": session_id,
            "sender_name": sender_name,
            "content": content,
            "secret": BRIDGE_SECRET
        }
        try:
            res = requests.post(HUB_URL, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if data.get("should_send") and data.get("reply_text"):
                    reply_text = data["reply_text"]
                    logger.info(f"AI response ready: {reply_text}")
                    self.send_reply_in_chat(reply_text)
                else:
                    logger.info(f"No reply needed. Reason: {data.get('reason')}")
        except Exception as e:
            logger.error(f"Failed to post message to AI Hub: {e}")

    def send_reply_in_chat(self, text: str):
        """พิมพ์และกดส่งข้อความในหน้าแชท LINE ของ Android"""
        try:
            # หาช่องพิมพ์ข้อความ (Edit Text)
            input_box = self.d(className="android.widget.EditText")
            if input_box.exists:
                input_box.click()
                time.sleep(0.3)
                # ตั้งค่าข้อความภาษาไทยผ่าน uiautomator2 set_text
                self.d.set_fastinput_ime(True)  # รองรับ UTF-8 / Thai
                input_box.set_text(text)
                time.sleep(0.5)

                # กดปุ่มส่ง (Send Button)
                send_btn = self.d(descriptionMatches=".*ส่ง.*|.*Send.*", resourceIdMatches=".*send.*|.*button_send.*")
                if send_btn.exists:
                    send_btn.click()
                else:
                    # กด Enter บนคีย์บอร์ด
                    self.d.press("enter")

                logger.info(f"Successfully sent reply to {text[:20]}...")
            else:
                logger.warning("Chat input box not found on screen.")
        except Exception as e:
            logger.error(f"Error sending reply on Android: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print(" Android / LDPlayer LINE Automation Bridge ")
    print("=" * 60)
    bot = AndroidLineBot()
    bot.listen_and_reply_loop()
