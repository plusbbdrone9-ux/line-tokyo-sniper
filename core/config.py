import os
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Unified LINE Bot Hub"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    DATABASE_PATH: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "data", "line_bot.db")

    # AI (Gemini) Settings
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    SYSTEM_INSTRUCTION: str = (
        "คุณคือผู้ช่วย AI แอดมินตอบแชทของร้านค้า ทำหน้าที่ตอบคำถามลูกค้าอย่างสุภาพ อ่อนน้อม "
        "เป็นมิตร ให้ข้อมูลที่ถูกต้อง กระชับ เข้าใจง่าย ตอบเป็นภาษาไทย มีหางเสียง (ค่ะ/ครับ) "
        "หากลูกค้าถามเกี่ยวกับสินค้า ให้ค้นหาจากข้อมูลร้านค้าที่มี หรือแนะนำอย่างถูกต้อง"
    )

    # LINE Official Account (LINE OA) Settings
    LINE_OA_CHANNEL_SECRET: Optional[str] = os.getenv("LINE_OA_CHANNEL_SECRET", "")
    LINE_OA_CHANNEL_ACCESS_TOKEN: Optional[str] = os.getenv("LINE_OA_CHANNEL_ACCESS_TOKEN", "")

    # LINE Personal Bridge Settings
    PERSONAL_BRIDGE_SECRET: str = os.getenv("PERSONAL_BRIDGE_SECRET", "secret-token-for-bridge")
    PERSONAL_MODE: str = os.getenv("PERSONAL_MODE", "android")  # 'android' or 'desktop'

    # Cloud Protocol Sniper (Tokyo VPS) Settings
    LINE_AUTH_TOKEN: Optional[str] = os.getenv("LINE_AUTH_TOKEN", "")
    LINE_TOKYO_HOST: str = os.getenv("LINE_TOKYO_HOST", "ga2.line.naver.jp")
    TARGET_SQUARE_CHAT_MID: Optional[str] = os.getenv("TARGET_SQUARE_CHAT_MID", "")
    CLOUD_SNIPER_AUTO_START: bool = os.getenv("CLOUD_SNIPER_AUTO_START", "false").lower() == "true"

    # Automation & Human Takeover Settings
    AUTO_REPLY_ENABLED: bool = True
    HUMAN_TAKEOVER_TIMEOUT_MINUTES: int = 20  # บอทจะหยุดตอบเมื่อแอดมินคนจริงพิมพ์แทรก
    REPLY_DELAY_SECONDS: float = 1.0  # หน่วงเวลาตอบให้ดูธรรมชาติเสมือนคนจริง

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

