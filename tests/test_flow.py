import asyncio
import os
import sys

# Set utf-8 encoding for Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.dispatcher import dispatcher
from core.memory.session_manager import SessionManager
from database.db import init_db, get_db, get_recent_messages, get_session_state, toggle_bot_for_session
from core.config import settings

async def run_all_tests():
    print("=== [1/5] Testing Database Initialization ===")
    await init_db()
    async with get_db() as conn:
        async with conn.execute("SELECT COUNT(*) as cnt FROM knowledge_items") as cur:
            row = await cur.fetchone()
            print(f"[OK] DB initialized successfully! Default FAQ count: {row['cnt']}")
            assert row["cnt"] > 0, "Default FAQs should be seeded"

    print("\n=== [2/5] Testing Incoming LINE OA Message ===")
    test_session_oa = "user_line_oa_001"
    # Reset session takeover state to ensure idempotent testing
    await toggle_bot_for_session(test_session_oa, True)

    res_oa = await dispatcher.process_incoming_message(
        source_type="LINE_OA",
        session_id=test_session_oa,
        content="เวลาทำการของร้านเปิดกี่โมงครับ",
        sender_name="สมศักดิ์ LINE OA"
    )
    print("[OK] LINE OA Dispatcher Result:", res_oa)
    assert res_oa.get("reply_text") is not None
    print(f"[OK] Bot Generated Reply: {res_oa.get('reply_text')}")

    print("\n=== [3/5] Testing Incoming LINE Personal Message ===")
    test_session_personal = "user_personal_002"
    await toggle_bot_for_session(test_session_personal, True)

    res_personal = await dispatcher.process_incoming_message(
        source_type="LINE_PERSONAL",
        session_id=test_session_personal,
        content="ส่งของด้วยขนส่งอะไร มีเก็บเงินปลายทางไหม",
        sender_name="สมหญิง LINE ส่วนบุคคล"
    )
    print("[OK] LINE Personal Dispatcher Result:", res_personal)
    assert res_personal["replied"] is True
    print(f"[OK] Bot Generated Reply for Personal: {res_personal.get('reply_text')}")

    print("\n=== [4/5] Testing Chat History Persistence ===")
    history = await get_recent_messages(test_session_oa)
    print(f"[OK] Retrieved {len(history)} messages for session {test_session_oa}")
    assert len(history) >= 2, "Should contain at least user message and bot reply"

    print("\n=== [5/5] Testing Human Takeover Trigger ===")
    res_takeover = await dispatcher.process_incoming_message(
        source_type="LINE_OA",
        session_id=test_session_oa,
        content="ขอคุยกับคนหน่อยครับ มีปัญหาการโอนเงิน",
        sender_name="สมศักดิ์ LINE OA"
    )
    state = await get_session_state(test_session_oa)
    print(f"[OK] Session State after takeover trigger: is_human_takeover={state.get('is_human_takeover')}")
    assert state.get("is_human_takeover") == 1, "Session should be marked for human takeover"

    # Now verify bot won't reply automatically while takeover is active
    should_reply, reason = await SessionManager.should_bot_reply(test_session_oa, "ฮัลโหล")
    print(f"[OK] Should bot reply now? {should_reply} (Reason: {reason})")
    assert should_reply is False, "Bot should yield to human agent"

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
