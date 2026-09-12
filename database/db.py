import aiosqlite
import os
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.config import settings

DB_PATH = settings.DATABASE_PATH

@asynccontextmanager
async def get_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn

async def init_db():
    async with get_db() as conn:
        # 1. Messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                channel_id TEXT,
                session_id TEXT NOT NULL,
                sender_name TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Session states table (สำหรับ LINE OA / Human Takeover)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_states (
                session_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                sender_name TEXT,
                is_human_takeover INTEGER DEFAULT 0,
                human_takeover_until TIMESTAMP,
                is_bot_enabled INTEGER DEFAULT 1,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Knowledge items / FAQ table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT DEFAULT 'FAQ',
                keywords TEXT NOT NULL,
                answer TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. CF Rules table (สำหรับตั้งเงื่อนไขส่องสินค้าและ CF อัตโนมัติ)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cf_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_rooms TEXT DEFAULT '*',
                target_keywords TEXT NOT NULL,
                negative_keywords TEXT DEFAULT '',
                cf_format TEXT DEFAULT 'CF {code}',
                price_limit REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                delay_ms INTEGER DEFAULT 250,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. CF History table (ประวัติที่บอทพิมพ์ CF สำเร็จ)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cf_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                rule_name TEXT,
                room_name TEXT NOT NULL,
                sender_name TEXT,
                original_message TEXT NOT NULL,
                cf_text TEXT NOT NULL,
                status TEXT DEFAULT 'SUCCESS',
                execution_time_ms REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Global Settings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        await conn.commit()

        # Seed sample CF Rules if empty
        async with conn.execute("SELECT COUNT(*) as cnt FROM cf_rules") as cursor:
            row = await cursor.fetchone()
            if row and row["cnt"] == 0:
                sample_rules = [
                    (
                        "Labubu V2 / กล่องจุ่มยอดนิยม",
                        "*",
                        "labubu, v2, ลาบูบู้, กล่องสุ่ม, พร้อมส่ง",
                        "หมดแล้ว, ปิดการขาย, ขายแล้ว, มีคนรับแล้ว",
                        "CF {code} พร้อมโอน",
                        1500.0,
                        1,
                        200
                    ),
                    (
                        "ดักจับรหัสสินค้าทั่วไป (รหัส A/B/C/0-9)",
                        "*",
                        "รหัส, cf, พร้อมส่ง, เปิดขาย, ปล่อยของ",
                        "หมดแล้ว, ปิดการขาย, ขายแล้ว",
                        "CF {code}",
                        0.0,
                        1,
                        250
                    )
                ]
                for name, rooms, kw, nkw, fmt, price, act, dly in sample_rules:
                    await conn.execute(
                        """
                        INSERT INTO cf_rules 
                        (name, target_rooms, target_keywords, negative_keywords, cf_format, price_limit, is_active, delay_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (name, rooms, kw, nkw, fmt, price, act, dly)
                    )
                await conn.commit()

# --- Message & Session Functions ---

async def save_message(source_type: str, session_id: str, role: str, content: str, sender_name: str = "User", channel_id: str = ""):
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO messages (source_type, channel_id, session_id, sender_name, role, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_type, channel_id, session_id, sender_name, role, content)
        )
        await conn.execute(
            """
            INSERT INTO session_states (session_id, source_type, sender_name, last_activity)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                last_activity = CURRENT_TIMESTAMP,
                sender_name = excluded.sender_name
            """,
            (session_id, source_type, sender_name)
        )
        await conn.commit()

async def get_recent_messages(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT role, content, created_at, sender_name
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            messages = [dict(row) for row in rows]
            messages.reverse()
            return messages

async def get_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM session_states WHERE session_id = ?",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_human_takeover(session_id: str, minutes: int = 20):
    async with get_db() as conn:
        await conn.execute(
            """
            UPDATE session_states
            SET is_human_takeover = 1,
                human_takeover_until = datetime('now', '+' || ? || ' minutes')
            WHERE session_id = ?
            """,
            (minutes, session_id)
        )
        await conn.commit()

async def toggle_bot_for_session(session_id: str, enabled: bool):
    async with get_db() as conn:
        await conn.execute(
            """
            UPDATE session_states
            SET is_bot_enabled = ?,
                is_human_takeover = 0
            WHERE session_id = ?
            """,
            (1 if enabled else 0, session_id)
        )
        await conn.commit()

async def get_active_faqs() -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT id, category, keywords, answer FROM knowledge_items WHERE is_active = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

# --- CF Rules CRUD ---

async def get_all_cf_rules() -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM cf_rules ORDER BY id DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_active_cf_rules() -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute("SELECT * FROM cf_rules WHERE is_active = 1 ORDER BY id ASC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def add_cf_rule(
    name: str,
    target_rooms: str,
    target_keywords: str,
    negative_keywords: str,
    cf_format: str,
    price_limit: float,
    delay_ms: int = 250
) -> int:
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO cf_rules (name, target_rooms, target_keywords, negative_keywords, cf_format, price_limit, is_active, delay_ms)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (name, target_rooms, target_keywords, negative_keywords, cf_format, price_limit, delay_ms)
        )
        await conn.commit()
        return cursor.lastrowid

async def toggle_cf_rule(rule_id: int, is_active: bool):
    async with get_db() as conn:
        await conn.execute("UPDATE cf_rules SET is_active = ? WHERE id = ?", (1 if is_active else 0, rule_id))
        await conn.commit()

async def delete_cf_rule(rule_id: int):
    async with get_db() as conn:
        await conn.execute("DELETE FROM cf_rules WHERE id = ?", (rule_id,))
        await conn.commit()

# --- CF History Logging ---

async def log_cf_action(
    rule_id: Optional[int],
    rule_name: str,
    room_name: str,
    sender_name: str,
    original_message: str,
    cf_text: str,
    status: str = "SUCCESS",
    execution_time_ms: float = 0.0
):
    import time
    local_now = time.strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO cf_history (rule_id, rule_name, room_name, sender_name, original_message, cf_text, status, execution_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (rule_id, rule_name, room_name, sender_name, original_message, cf_text, status, execution_time_ms, local_now)
        )
        await conn.commit()

async def clear_cf_history():
    async with get_db() as conn:
        await conn.execute("DELETE FROM cf_history")
        await conn.commit()

async def get_recent_cf_history(limit: int = 30) -> List[Dict[str, Any]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM cf_history ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_cf_stats() -> Dict[str, Any]:
    async with get_db() as conn:
        async with conn.execute("SELECT COUNT(*) as total_wins FROM cf_history WHERE status = 'SUCCESS'") as cur:
            row = await cur.fetchone()
            total_wins = row["total_wins"] if row else 0

        async with conn.execute("SELECT COUNT(*) as active_rules FROM cf_rules WHERE is_active = 1") as cur:
            row = await cur.fetchone()
            active_rules = row["active_rules"] if row else 0

        async with conn.execute("SELECT COUNT(*) as total_rules FROM cf_rules") as cur:
            row = await cur.fetchone()
            total_rules = row["total_rules"] if row else 0

    return {
        "total_wins": total_wins,
        "active_rules": active_rules,
        "total_rules": total_rules
    }
