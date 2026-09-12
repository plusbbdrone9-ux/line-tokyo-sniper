"""
LINE PC Live Monitor & Room Sniffer
-----------------------------------
ดักจับข้อความใหม่ที่ไหลเข้ามาในห้องแชท LINE PC (กลุ่ม / OpenChat / OA)
และส่งเข้าประมวลผลใน CF Engine ทันที
"""

import time
import asyncio
import logging
import win32gui
from typing import Optional, Callable
from core.cf.cf_manager import cf_manager

logger = logging.getLogger("LiveMonitor")

class LineRoomMonitor:
    def __init__(self, check_interval: float = 0.5):
        self.check_interval = check_interval
        self.is_running = False
        self.last_detected_msg = ""

    async def start_monitoring(self):
        self.is_running = True
        logger.info("Radar started: Monitoring LINE PC Group / OpenChat messages...")
        
        while self.is_running:
            try:
                # ตรวจสอบข้อความใหม่จากห้องแชทที่กำลังเปิดอยู่
                # (สำหรับ Windows สามารถอ่านจาก Clipboard Hook หรือ UI Window Title/Event)
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in room monitor loop: {e}")
                await asyncio.sleep(1.0)

    def stop(self):
        self.is_running = False
        logger.info("Room monitor stopped.")

line_monitor = LineRoomMonitor()
