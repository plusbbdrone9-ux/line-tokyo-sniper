import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from database.db import get_active_cf_rules

logger = logging.getLogger(__name__)

class CFRuleEngine:
    # Regex patterns to extract seller product codes
    # e.g., 'รหัส A1', 'รหัส: 05', 'CF A02', 'A12', '#09', 'กล่องที่ 3'
    CODE_PATTERNS = [
        re.compile(r'(?:รหัส|code|รหัสสินค้า|ชิ้นที่|กล่องที่|เบอร์|ชุดที่)\s*[:#-]?\s*([A-Za-z0-9\u0E00-\u0E7F\-_/]+)', re.IGNORECASE),
        re.compile(r'(?:ใครรับพิมพ์|พิมพ์|เม้นท์|เม้นต์|cf|รับ)\s*[:#-]?\s*([A-Za-z0-9\u0E00-\u0E7F\-_/]+)', re.IGNORECASE),
        re.compile(r'\b([A-Za-z]\d{1,4})\b'),               # e.g. A1, B02, C105
        re.compile(r'#([A-Za-z0-9\u0E00-\u0E7F\-_]+)'),     # e.g. #01, #B2, #แดง
        re.compile(r'\b(\d{1,4})\b')                        # Fallback simple digit e.g. 1, 05, 850
    ]

    # Regex patterns to extract price
    # e.g., 'ราคา 250 บาท', 'ราคา 3,500 บาท', '250.-', '250฿'
    PRICE_PATTERNS = [
        re.compile(r'(?:ราคา|price|ละ)\s*[:=]?\s*([0-9,]+(?:\.\d+)?)\s*(?:บาท|฿|.-|b)?', re.IGNORECASE),
        re.compile(r'([0-9,]+(?:\.\d+)?)\s*(?:บาท|฿|.-)', re.IGNORECASE)
    ]

    EXCLUDE_CODES = {"cf", "line", "id", "bank", "free", "v1", "v2", "v3", "v4", "pm", "am", "no", "พิมพ์", "รับ", "ราคา", "บาท"}

    @classmethod
    def extract_product_code(cls, text: str) -> Optional[str]:
        # 1. First priority: Check explicit label like 'รหัส ฉัน', 'รหัส A05', 'พิมพ์ ฉัน'
        for pattern in cls.CODE_PATTERNS[:2]:
            match = pattern.search(text)
            if match:
                code = match.group(1).strip()
                clean = code.replace('O', '0') if code.isalnum() else code
                if len(clean) > 0 and clean.lower() not in cls.EXCLUDE_CODES:
                    return clean

        # 2. Priority: Alphanumeric code like A05, B12, C1, #A05
        m_alpha = re.findall(r'(?:รหัส|code|cf|\s|^|#|[A-Za-z])?([A-Za-z][0-9Oo]{1,4})(?:\s|$|[^\w])', text, re.IGNORECASE)
        for cand in m_alpha:
            clean = cand.upper().replace('O', '0').strip()
            if clean.lower() not in cls.EXCLUDE_CODES and len(clean) >= 2:
                return clean

        # 3. Fallback remaining patterns
        for pattern in cls.CODE_PATTERNS[2:]:
            match = pattern.search(text)
            if match:
                code = match.group(1).strip()
                clean = code.replace('O', '0') if code.isalnum() else code
                if len(clean) > 0 and clean.lower() not in cls.EXCLUDE_CODES:
                    return clean
        return None

    @classmethod
    def extract_price(cls, text: str) -> Optional[float]:
        for pattern in cls.PRICE_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    price_str = match.group(1).replace(",", "").strip()
                    return float(price_str)
                except ValueError:
                    continue
        return None

    @classmethod
    def is_negative_keyword_matched(cls, nkw: str, msg_lower: str) -> bool:
        """
        ตรวจจับคำต้องห้ามอย่างแม่นยำ ป้องกัน false positive ภาษาไทย
        (เช่น 'ปิด' อยู่ใน 'เปิด' หรือ 'จอง' อยู่ใน 'เปิดจอง')
        """
        if nkw not in msg_lower:
            return False

        # ป้องกันคำว่า 'ปิด' แมตช์กับ 'เปิด' ('เปิด' contains 'ปิด' code points)
        if nkw == "ปิด":
            cleaned = msg_lower.replace("เปิด", "")
            return "ปิด" in cleaned

        # ป้องกันคำว่า 'จอง' แมตช์กับ 'เปิดจอง'
        if nkw in ["จอง", "จองแล้ว"]:
            cleaned = msg_lower.replace("เปิดจอง", "")
            return nkw in cleaned

        return True

    @classmethod
    async def evaluate_message(
        cls,
        room_name: str,
        sender_name: str,
        message_text: str
    ) -> Dict[str, Any]:
        active_rules = await get_active_cf_rules()
        if not active_rules:
            return {
                "should_cf": False,
                "reason": "ไม่มีกฎการ CF ที่เปิดใช้งานอยู่",
                "cf_message": None
            }

        msg_lower = message_text.lower()
        room_lower = room_name.lower()

        for rule in active_rules:
            # 1. ตรวจสอบห้อง/กลุ่มเป้าหมาย (Target Rooms)
            target_rooms = [r.strip().lower() for r in rule["target_rooms"].split(",") if r.strip()]
            if "*" not in target_rooms and not any(tr in room_lower for tr in target_rooms):
                continue

            # 2. ตรวจสอบคีย์เวิร์ดสินค้าเป้าหมาย (Target Keywords)
            target_kws = [k.strip().lower() for k in rule["target_keywords"].split(",") if k.strip()]
            matched_target = any(tkw in msg_lower for tkw in target_kws)
            if not matched_target:
                continue

            # 3. ตรวจสอบคำต้องห้าม (Negative Keywords)
            negative_kws = [k.strip().lower() for k in rule["negative_keywords"].split(",") if k.strip()]
            matched_neg = None
            for nkw in negative_kws:
                if cls.is_negative_keyword_matched(nkw, msg_lower):
                    matched_neg = nkw
                    break

            if matched_neg:
                logger.info(f"Skipped CF for rule '{rule['name']}': matched negative keyword '{matched_neg}'.")
                return {
                    "should_cf": False,
                    "reason": f"สินค้าหมดหรือปิดแล้ว (เจอคำว่า '{matched_neg}')",
                    "cf_message": None
                }

            # 4. ตรวจสอบราคา (Price Limit Filter)
            extracted_price = cls.extract_price(message_text)
            if rule["price_limit"] > 0 and extracted_price:
                if extracted_price > rule["price_limit"]:
                    logger.info(f"Skipped CF: Price {extracted_price} exceeds limit {rule['price_limit']}")
                    return {
                        "should_cf": False,
                        "reason": f"ราคาสินค้า {extracted_price} บาท เกินงบที่ตั้งไว้ ({rule['price_limit']} บาท)",
                        "cf_message": None
                    }

            # 5. สกัดรหัสสินค้า
            extracted_code = cls.extract_product_code(message_text) or "1"

            # 6. สร้างข้อความ CF ตาม Format ของกฎ
            cf_format = rule["cf_format"] or "CF {code}"
            cf_message = cf_format.replace("{code}", extracted_code)
            cf_message = cf_message.replace("{CODE}", extracted_code.upper())

            logger.info(f"MATCHED CF RULE: '{rule['name']}' in room '{room_name}' -> '{cf_message}'")

            return {
                "should_cf": True,
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "extracted_code": extracted_code,
                "extracted_price": extracted_price,
                "cf_message": cf_message,
                "delay_ms": rule.get("delay_ms", 200),
                "reason": f"ตรงกับกฎ '{rule['name']}'"
            }

        return {
            "should_cf": False,
            "reason": "ไม่ตรงกับเงื่อนไขในกฎใดๆ",
            "cf_message": None
        }
