import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from core.config import settings
from core.cf.cf_manager import cf_manager
from core.cf.rule_engine import CFRuleEngine
from database.db import (
    get_db,
    get_all_cf_rules,
    get_active_cf_rules,
    add_cf_rule,
    toggle_cf_rule,
    delete_cf_rule,
    get_recent_cf_history,
    get_cf_stats,
    save_message
)

router = APIRouter(tags=["Auto-CF Sniper Hub"])

class TestFlightRequest(BaseModel):
    room_name: str = "OpenChat ปล่อยของ"
    message: str
    sender_name: Optional[str] = "แม่ค้า"

class RuleCreateRequest(BaseModel):
    name: str
    target_rooms: str = "*"
    target_keywords: str
    negative_keywords: Optional[str] = ""
    cf_format: str = "CF {code} พร้อมโอน"
    price_limit: float = 0.0
    delay_ms: int = 200

class IncomingRoomMessageRequest(BaseModel):
    room_name: str
    sender_name: str = "แม่ค้า"
    content: str
    image_path: Optional[str] = None
    secret: Optional[str] = None

class SniperSettingsRequest(BaseModel):
    platform: str = "windows"
    jitter: str = "normal"
    secret: Optional[str] = None

@router.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/api/sniper/stats")
async def get_sniper_stats():
    stats = await get_cf_stats()
    stats["is_sniper_active"] = cf_manager.is_sniper_active
    stats["platform"] = cf_manager.mode
    return stats

@router.post("/api/sniper/toggle-master")
async def toggle_master_switch():
    cf_manager.is_sniper_active = not cf_manager.is_sniper_active
    return {"is_sniper_active": cf_manager.is_sniper_active}

@router.post("/api/sniper/test-flight")
async def test_flight(req: TestFlightRequest):
    """
    ทดสอบประเมินข้อความจำลอง โดยไม่กดส่งข้อความจริงเข้า LINE
    """
    res = await CFRuleEngine.evaluate_message(
        room_name=req.room_name,
        sender_name=req.sender_name or "แม่ค้า",
        message_text=req.message
    )
    # บันทึกลง radar feed
    await save_message(
        source_type="TEST_SIMULATOR",
        session_id=req.room_name,
        role="user",
        content=req.message,
        sender_name=req.sender_name or "แม่ค้า",
        channel_id=req.room_name
    )
    return {
        "matched": res.get("should_cf", False),
        "rule_name": res.get("rule_name"),
        "extracted_code": res.get("extracted_code"),
        "extracted_price": res.get("extracted_price"),
        "cf_message": res.get("cf_message"),
        "delay_ms": res.get("delay_ms", 200),
        "reason": res.get("reason")
    }

@router.post("/api/sniper/incoming")
async def process_live_room_message(req: IncomingRoomMessageRequest):
    """
    Endpoint สำหรับรับข้อความจริงที่ตรวจจับได้จากห้องแชท LINE PC หรือ Android
    และประมวลผลยิง CF เข้า LINE ทันที
    """
    # บันทึกลง radar feed
    await save_message(
        source_type="LINE_SNIPER_ROOM",
        session_id=req.room_name,
        role="user",
        content=req.content,
        sender_name=req.sender_name,
        channel_id=req.room_name
    )

    result = await cf_manager.process_room_message(
        room_name=req.room_name,
        sender_name=req.sender_name,
        content=req.content,
        image_path=req.image_path
    )

    return result

@router.get("/api/sniper/radar-feed")
async def get_radar_feed():
    """ดึงข้อความสด 30 รายการล่าสุดที่ไหลเข้ามาในเรดาร์"""
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, session_id as room_name, sender_name, content, created_at
            FROM messages
            ORDER BY id DESC
            LIMIT 30
            """
        ) as cur:
            rows = await cur.fetchall()
            messages = [dict(r) for r in rows]
            messages.reverse()
            return messages

@router.get("/api/sniper/rules")
async def list_rules():
    return await get_all_cf_rules()

@router.post("/api/sniper/rules")
async def create_rule(req: RuleCreateRequest):
    new_id = await add_cf_rule(
        name=req.name,
        target_rooms=req.target_rooms,
        target_keywords=req.target_keywords,
        negative_keywords=req.negative_keywords or "",
        cf_format=req.cf_format,
        price_limit=req.price_limit,
        delay_ms=req.delay_ms
    )
    return {"status": "success", "id": new_id}

@router.post("/api/sniper/rules/{rule_id}/toggle")
async def toggle_rule_state(rule_id: int, active: bool):
    await toggle_cf_rule(rule_id, active)
    return {"status": "success", "id": rule_id, "active": active}

@router.delete("/api/sniper/rules/{rule_id}")
async def remove_rule(rule_id: int):
    await delete_cf_rule(rule_id)
    return {"status": "success", "id": rule_id}

@router.get("/api/sniper/history")
async def list_history():
    return await get_recent_cf_history(limit=50)

@router.post("/api/sniper/settings")
async def save_settings(req: SniperSettingsRequest):
    cf_manager.mode = req.platform
    if req.secret:
        settings.PERSONAL_BRIDGE_SECRET = req.secret
    return {"status": "success", "platform": cf_manager.mode}
