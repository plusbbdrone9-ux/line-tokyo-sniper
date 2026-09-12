import logging
from datetime import datetime
from typing import Tuple
from core.config import settings
from database.db import get_session_state, set_human_takeover

logger = logging.getLogger(__name__)

class SessionManager:
    # Trigger keywords where bot should automatically yield to a human agent
    TAKEOVER_KEYWORDS = [
        "ขอคุยกับคน", "คุยกับเจ้าหน้าที่", "ติดต่อแอดมิน", "ติดต่อคน", 
        "ไม่ใช่บอท", "ขอคน", "คุยกับคน", "เจ้าหน้าที่", "แอดมินหน่อย"
    ]

    @classmethod
    async def should_bot_reply(cls, session_id: str, user_message: str) -> Tuple[bool, str]:
        """
        Returns (should_reply: bool, reason: str)
        """
        # 1. Global switch
        if not settings.AUTO_REPLY_ENABLED:
            return False, "Global auto-reply is disabled"

        # 2. Check session state in DB
        state = await get_session_state(session_id)
        if state:
            # Check if bot is explicitly turned off for this user
            if state.get("is_bot_enabled") == 0:
                return False, "Bot is disabled for this session"

            # Check human takeover active
            if state.get("is_human_takeover") == 1:
                takeover_until_str = state.get("human_takeover_until")
                if takeover_until_str:
                    try:
                        # SQLite returns 'YYYY-MM-DD HH:MM:SS'
                        takeover_until = datetime.fromisoformat(takeover_until_str.replace(" ", "T"))
                        if datetime.utcnow() < takeover_until:
                            return False, f"Human takeover active until {takeover_until_str}"
                    except Exception as e:
                        logger.warning(f"Error parsing takeover timestamp: {e}")

        # 3. Check if user is asking for a human agent right now
        user_lower = user_message.lower()
        if any(kw in user_lower for kw in cls.TAKEOVER_KEYWORDS):
            # Flag this session for human takeover
            await set_human_takeover(session_id, minutes=settings.HUMAN_TAKEOVER_TIMEOUT_MINUTES)
            logger.info(f"Human takeover triggered by user message for session: {session_id}")
            # Still reply this one time with an acknowledgment, or let the bot handle it with notification
            return True, "Human takeover triggered - sending acknowledgment"

        return True, "OK"

    @classmethod
    async def trigger_admin_takeover(cls, session_id: str, minutes: int = None):
        """Called when a real human admin sends a message to the chat"""
        if minutes is None:
            minutes = settings.HUMAN_TAKEOVER_TIMEOUT_MINUTES
        await set_human_takeover(session_id, minutes=minutes)
        logger.info(f"Admin takeover enabled for session {session_id} for {minutes} minutes.")
