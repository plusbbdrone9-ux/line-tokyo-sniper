import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from core.config import settings
from core.dispatcher import dispatcher
from core.memory.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personal", tags=["LINE Personal Bridge"])

class PersonalMessagePayload(BaseModel):
    session_id: str
    sender_name: str
    content: str
    is_group: bool = False
    group_name: Optional[str] = None
    secret: Optional[str] = None

class AdminSentPayload(BaseModel):
    session_id: str
    sender_name: Optional[str] = "Admin"
    content: Optional[str] = ""
    secret: Optional[str] = None

def verify_bridge_secret(secret: Optional[str]):
    if settings.PERSONAL_BRIDGE_SECRET and secret != settings.PERSONAL_BRIDGE_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid bridge secret")

@router.post("/incoming")
async def receive_personal_message(payload: PersonalMessagePayload):
    """
    Called by Android Notification Listener / Desktop Automation script
    when a new personal LINE message is detected.
    """
    verify_bridge_secret(payload.secret)

    res = await dispatcher.process_incoming_message(
        source_type="LINE_PERSONAL",
        session_id=payload.session_id,
        content=payload.content,
        sender_name=payload.sender_name,
        channel_id="LINE_PERSONAL",
        extra_metadata={
            "is_group": payload.is_group,
            "group_name": payload.group_name
        }
    )

    return {
        "status": "success",
        "should_send": res.get("replied", False),
        "reason": res.get("reason"),
        "reply_text": res.get("reply_text"),
        "session_id": payload.session_id,
        "sender_name": payload.sender_name
    }

@router.post("/admin-sent")
async def notify_admin_sent(payload: AdminSentPayload):
    """
    Called when a human admin sends a message to this chat manually.
    This automatically engages Human Takeover mode, pausing the bot.
    """
    verify_bridge_secret(payload.secret)
    await SessionManager.trigger_admin_takeover(payload.session_id)
    return {
        "status": "success",
        "message": f"Human takeover activated for {payload.session_id} for {settings.HUMAN_TAKEOVER_TIMEOUT_MINUTES} minutes."
    }
