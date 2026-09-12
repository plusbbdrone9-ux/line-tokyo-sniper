import hmac
import hashlib
import base64
import logging
from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
from core.config import settings
from core.dispatcher import dispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/line-oa", tags=["LINE OA Webhook"])

def verify_line_signature(body_bytes: bytes, signature: str) -> bool:
    channel_secret = settings.LINE_OA_CHANNEL_SECRET
    if not channel_secret:
        # If secret not set yet in development, log warning
        logger.warning("LINE_OA_CHANNEL_SECRET not set, signature verification skipped (development mode)")
        return True
    
    hash_value = hmac.new(
        channel_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)

@router.post("")
async def line_oa_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(None, alias="X-Line-Signature")
):
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    # Verify signature if header is provided
    if x_line_signature and not verify_line_signature(body_bytes, x_line_signature):
        logger.error("Invalid LINE signature received")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = data.get("events", [])
    logger.info(f"Received {len(events)} LINE OA events")

    for event in events:
        event_type = event.get("type")
        source = event.get("source", {})
        user_id = source.get("userId") or source.get("groupId") or "unknown_oa_user"

        if event_type == "message":
            message = event.get("message", {})
            msg_type = message.get("type")
            reply_token = event.get("replyToken")

            if msg_type == "text":
                text = message.get("text", "").strip()
                # Run dispatcher in background to return 200 OK fast to LINE platform
                background_tasks.add_task(
                    dispatcher.process_incoming_message,
                    source_type="LINE_OA",
                    session_id=user_id,
                    content=text,
                    sender_name="LINE OA Customer",
                    channel_id="LINE_OA",
                    reply_token=reply_token
                )

        elif event_type == "follow":
            # Welcome message when someone adds LINE OA as a friend
            reply_token = event.get("replyToken")
            welcome_text = (
                "สวัสดีค่ะ ยินดีต้อนรับสู่ร้านของเรานะคะ! 😊\n"
                "สอบถามข้อมูลสินค้า บริการ หรือเวลาทำการได้ตลอดเวลาเลยนะคะ"
            )
            background_tasks.add_task(
                dispatcher.process_incoming_message,
                source_type="LINE_OA",
                session_id=user_id,
                content="[ลูกค้าเพิ่มเพื่อนใหม่]",
                sender_name="New Follower",
                channel_id="LINE_OA",
                reply_token=reply_token
            )

    return {"status": "ok"}
