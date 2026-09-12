import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from core.config import settings
from core.ai.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self):
        if settings.GEMINI_API_KEY:
            try:
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Google GenAI client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI client: {e}")
                self._client = None
        else:
            logger.warning("GEMINI_API_KEY is not set. Running in rule-based / fallback mode.")

    async def generate_reply(
        self,
        user_message: str,
        chat_history: List[Dict[str, Any]],
        sender_name: str = "ลูกค้า"
    ) -> str:
        # Check if client is initialized
        if not self._client and settings.GEMINI_API_KEY:
            self._init_client()

        # Retrieve Knowledge Base context
        kb_context = await KnowledgeBase.get_relevant_context(user_message)

        # Fallback if no API key is provided yet
        if not self._client:
            return (
                f"สวัสดีค่ะคุณ {sender_name} ขอบคุณที่ติดต่อเรานะคะ 😊\n\n"
                f"[ระบบทดสอบ: กรุณาใส่ GEMINI_API_KEY ในไฟล์ .env หรือ Web Dashboard]\n"
                f"ข้อความที่ได้รับ: \"{user_message}\"\n\n"
                f"เบื้องต้นทางร้านเปิดบริการ 09:00 - 18:00 น. เจ้าหน้าที่จะรีบดูแลให้นะคะ"
            )

        try:
            # Build conversation contents
            contents = []
            
            # Format history (take up to last 8 messages)
            for msg in chat_history[-8:]:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg["content"])]
                    )
                )

            # Add current user message
            current_user_prompt = f"ลูกค้าชื่อ: {sender_name}\nข้อความ: {user_message}"
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=current_user_prompt)]
                )
            )

            # Prepare system instruction with store knowledge
            full_system_instruction = (
                f"{settings.SYSTEM_INSTRUCTION}\n\n"
                f"{kb_context}\n\n"
                "แนวทางการตอบ:\n"
                "1. ตอบคำถามอย่างเป็นมิตร สุภาพ มีหางเสียง (ค่ะ/ครับ)\n"
                "2. อ้างอิงข้อมูลจาก [ข้อมูลของทางร้าน/Knowledge Base] ข้างต้นเสมอ\n"
                "3. หากเป็นคำถามนอกเหนือจากข้อมูล ให้ตอบรับอย่างสุภาพและแจ้งว่าจะประสานงานเจ้าหน้าที่ให้\n"
                "4. ถ้าลูกค้าขอคุยกับคน หรือต้องการเจ้าหน้าที่ ให้บอกว่าได้แจ้งแอดมินให้แล้ว เจ้าหน้าที่จะรีบเข้ามาตอบ"
            )

            config = types.GenerateContentConfig(
                system_instruction=full_system_instruction,
                temperature=0.7,
                max_output_tokens=600
            )

            # Async generation
            response = await self._client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=config
            )

            if response and response.text:
                return response.text.strip()
            else:
                return "ขออภัยนะคะ ระบบไม่สามารถประมวลผลคำตอบได้ชั่วคราว รบกวนรอแอดมินสักครู่นะคะ"

        except Exception as e:
            logger.error(f"Error generating content from Gemini: {e}")
            return (
                "ขออภัยในความไม่สะดวกนะคะ ขณะนี้ระบบ AI ขัดข้องชั่วคราว "
                "เจ้าหน้าที่แอดมินกำลังเข้ามาดูแลให้ค่ะ 🙏"
            )

gemini_service = GeminiService()
