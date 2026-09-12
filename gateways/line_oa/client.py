import httpx
import logging
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)

class LineOAClient:
    API_URL = "https://api.line.me/v2/bot/message"

    @classmethod
    async def send_reply(cls, reply_token: Optional[str], to_user_id: str, text: str) -> bool:
        token = settings.LINE_OA_CHANNEL_ACCESS_TOKEN
        if not token:
            logger.warning("LINE_OA_CHANNEL_ACCESS_TOKEN is not configured. Cannot send LINE OA message.")
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Try replyToken first (Free quota)
            if reply_token:
                payload = {
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": text}]
                }
                try:
                    res = await client.post(f"{cls.API_URL}/reply", json=payload, headers=headers)
                    if res.status_code == 200:
                        logger.info(f"LINE OA Reply sent successfully to {to_user_id}")
                        return True
                    else:
                        logger.warning(f"Failed to reply via replyToken ({res.status_code}): {res.text}. Falling back to push.")
                except Exception as e:
                    logger.error(f"Error replying to LINE OA: {e}")

            # 2. Fallback to Push Message if replyToken expired or unavailable
            if to_user_id:
                push_payload = {
                    "to": to_user_id,
                    "messages": [{"type": "text", "text": text}]
                }
                try:
                    res = await client.post(f"{cls.API_URL}/push", json=push_payload, headers=headers)
                    if res.status_code == 200:
                        logger.info(f"LINE OA Push sent successfully to {to_user_id}")
                        return True
                    else:
                        logger.error(f"Failed to push message ({res.status_code}): {res.text}")
                        return False
                except Exception as e:
                    logger.error(f"Error pushing to LINE OA: {e}")
                    return False

        return False
