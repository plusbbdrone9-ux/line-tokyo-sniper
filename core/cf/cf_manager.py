import logging
import asyncio
from typing import Dict, Any, Optional
from core.cf.rule_engine import CFRuleEngine
from gateways.personal_sniper.windows_sniper import WindowsLineSniper
from database.db import log_cf_action

logger = logging.getLogger(__name__)

class CFManager:
    def __init__(self):
        self.is_sniper_active = True
        self.mode = "windows"  # 'windows' or 'android'

    async def process_room_message(
        self,
        room_name: str,
        sender_name: str,
        content: str,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ศูนย์รับข้อความจากกลุ่ม/OpenChat ตรวจสอบและยิง CF ทันที
        """
        # หากส่งรูปมา ให้รัน OCR ดึงข้อความจากภาพก่อน
        if image_path:
            from core.cf.ocr_sniffer import ImageOCRSniffer
            extracted_img_text = ImageOCRSniffer.extract_text_from_image(image_path)
            if extracted_img_text:
                content = f"{content} {extracted_img_text}".strip()

        if not self.is_sniper_active:
            return {
                "triggered": False,
                "reason": "Sniper is currently paused",
                "room_name": room_name,
                "content": content
            }

        # ประเมินกฎการ CF
        eval_result = await CFRuleEngine.evaluate_message(
            room_name=room_name,
            sender_name=sender_name,
            message_text=content
        )

        if not eval_result.get("should_cf"):
            return {
                "triggered": False,
                "reason": eval_result.get("reason"),
                "room_name": room_name,
                "content": content
            }

        cf_msg = eval_result["cf_message"]
        delay_ms = eval_result.get("delay_ms", 200)

        logger.info(f"🎯 TRIGGER SNIPER! Sending '{cf_msg}' to '{room_name}' (Delay: {delay_ms}ms)")

        # ยิง CF ทันทีตามแพลตฟอร์ม
        success = False
        if self.mode == "windows":
            success = await WindowsLineSniper.execute_cf(
                cf_message=cf_msg,
                room_name=room_name,
                sender_name=sender_name,
                original_message=content,
                rule_id=eval_result.get("rule_id"),
                rule_name=eval_result.get("rule_name", "Auto Rule"),
                delay_ms=delay_ms
            )
        else:
            from gateways.personal_sniper.android_sniper import android_sniper
            success = await android_sniper.execute_cf(
                cf_message=cf_msg,
                room_name=room_name,
                sender_name=sender_name,
                original_message=content,
                rule_id=eval_result.get("rule_id"),
                rule_name=eval_result.get("rule_name", "Auto Rule"),
                delay_ms=delay_ms
            )

        return {
            "triggered": True,
            "success": success,
            "cf_message": cf_msg,
            "room_name": room_name,
            "rule_name": eval_result.get("rule_name"),
            "extracted_code": eval_result.get("extracted_code"),
            "content": content
        }

cf_manager = CFManager()
