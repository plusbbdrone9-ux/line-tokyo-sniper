"""
Android / LDPlayer Auto-CF Sniper Client
----------------------------------------
เชื่อมต่อ LDPlayer หรือเครื่อง Android เพื่อสไนเปอร์ CF สินค้าใน OpenChat / กลุ่มไลน์
"""

import time
import logging
import asyncio
from typing import Optional
from database.db import log_cf_action

logger = logging.getLogger("AndroidCFSniper")

class AndroidLineSniper:
    def __init__(self, serial: Optional[str] = None):
        self.serial = serial
        self.d = None
        self._connect()

    def _connect(self):
        try:
            import uiautomator2 as u2
            if self.serial:
                self.d = u2.connect(self.serial)
            else:
                self.d = u2.connect()
            logger.info(f"Connected to Android device for CF Sniping: {self.d.device_info.get('model', 'OK')}")
        except Exception as e:
            logger.warning(f"Could not connect to Android via uiautomator2: {e}")

    async def execute_cf(
        self,
        cf_message: str,
        room_name: str = "Android LINE Room",
        sender_name: str = "แม่ค้า",
        original_message: str = "",
        rule_id: Optional[int] = None,
        rule_name: str = "Auto Rule",
        delay_ms: int = 200
    ) -> bool:
        start_time = time.time()
        if not self.d:
            logger.error("Android device not connected.")
            return False

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        try:
            # 1. คลิกช่องพิมพ์ข้อความ
            input_box = self.d(className="android.widget.EditText")
            if input_box.exists:
                input_box.click()
                self.d.set_fastinput_ime(True)
                input_box.set_text(cf_message)
                await asyncio.sleep(0.05)

                # 2. กดปุ่มส่ง (Send)
                send_btn = self.d(descriptionMatches=".*ส่ง.*|.*Send.*", resourceIdMatches=".*send.*|.*button_send.*")
                if send_btn.exists:
                    send_btn.click()
                else:
                    self.d.press("enter")

                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.info(f"⚡ [ANDROID SNIPER WIN] Sent '{cf_message}' in {duration_ms}ms!")

                await log_cf_action(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    room_name=room_name,
                    sender_name=sender_name,
                    original_message=original_message,
                    cf_text=cf_message,
                    status="SUCCESS",
                    execution_time_ms=duration_ms
                )
                return True
            else:
                logger.warning("Chat input box not found on Android screen.")
                return False

        except Exception as e:
            logger.error(f"Error executing Android sniper: {e}")
            return False

android_sniper = AndroidLineSniper()
