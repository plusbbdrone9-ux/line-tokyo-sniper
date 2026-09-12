import os
import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from database.db import init_db
from gateways.line_oa.webhook import router as line_oa_router
from gateways.line_personal.bridge_server import router as line_personal_router
from web_ui.routes import router as dashboard_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite database
    logger.info("Initializing SQLite database...")
    await init_db()
    logger.info("System initialized and ready!")
    yield
    # Shutdown
    logger.info("Shutting down LINE Bot Hub...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Unified LINE Bot Automation Hub (LINE OA & Personal Account)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for dashboard UI
static_dir = os.path.join(os.path.dirname(__file__), "web_ui", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routers
app.include_router(dashboard_router)
app.include_router(line_oa_router)
app.include_router(line_personal_router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "auto_reply": settings.AUTO_REPLY_ENABLED,
        "gemini_model": settings.GEMINI_MODEL
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
