from typing import List, Dict, Any
from database.db import get_active_faqs

class KnowledgeBase:
    @staticmethod
    async def get_relevant_context(user_message: str) -> str:
        faqs = await get_active_faqs()
        if not faqs:
            return ""

        user_lower = user_message.lower()
        matched_faqs = []

        for faq in faqs:
            keywords = [k.strip().lower() for k in faq["keywords"].split(",") if k.strip()]
            # If any keyword matches user query
            if any(k in user_lower for k in keywords):
                matched_faqs.append(faq)

        # If no specific keyword matched, include top 5 general FAQs as background context
        target_faqs = matched_faqs if matched_faqs else faqs[:5]

        context_lines = ["\n[ข้อมูลของทางร้าน/Knowledge Base]:"]
        for f in target_faqs:
            context_lines.append(f"- หมวดหมู่: {f['category']} | คำถาม/คำสำคัญ: {f['keywords']} -> ข้อมูล: {f['answer']}")

        return "\n".join(context_lines)
