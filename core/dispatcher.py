import asyncio
import logging
from typing import Dict, Any, Optional
from core.config import settings
from core.memory.session_manager import SessionManager
from core.ai.gemini_service import gemini_service
from database.db import save_message, get_recent_messages

logger = logging.getLogger(__name__)

class MessageDispatcher:
    @staticmethod
    async def process_incoming_message(
        source_type: str,
        session_id: str,
        content: str,
        sender_name: str = "User",
        channel_id: str = "",
        reply_token: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Unified handler for messages from LINE OA and LINE Personal.
        """
        logger.info(f"[{source_type}] Message received from {sender_name} ({session_id}): {content}")

        # 1. Save incoming user message to Database
        await save_message(
            source_type=source_type,
            session_id=session_id,
            role="user",
            content=content,
            sender_name=sender_name,
            channel_id=channel_id
        )

        # 2. Check if bot should reply
        should_reply, reason = await SessionManager.should_bot_reply(session_id, content)
        if not should_reply:
            logger.info(f"Skipping reply for {session_id}. Reason: {reason}")
            return {
                "replied": False,
                "reason": reason,
                "reply_text": None
            }

        # 3. Simulate human reading/typing delay if configured
        if settings.REPLY_DELAY_SECONDS > 0:
            await asyncio.sleep(settings.REPLY_DELAY_SECONDS)

        # 4. Fetch recent conversation history
        history = await get_recent_messages(session_id, limit=8)

        # 5. Generate AI reply
        reply_text = await gemini_service.generate_reply(
            user_message=content,
            chat_history=history,
            sender_name=sender_name
        )

        # 6. Save bot reply to Database
        await save_message(
            source_type=source_type,
            session_id=session_id,
            role="assistant",
            content=reply_text,
            sender_name=settings.APP_NAME,
            channel_id=channel_id
        )

        # 7. Dispatch reply to outbound gateway if LINE OA
        if source_type == "LINE_OA":
            from gateways.line_oa.client import LineOAClient
            success = await LineOAClient.send_reply(
                reply_token=reply_token,
                to_user_id=session_id,
                text=reply_text
            )
            return {
                "replied": success,
                "source": "LINE_OA",
                "reply_text": reply_text
            }

        # For LINE_PERSONAL, return reply_text so bridge client can execute the send action
        return {
            "replied": True,
            "source": "LINE_PERSONAL",
            "reply_text": reply_text
        }

dispatcher = MessageDispatcher()
