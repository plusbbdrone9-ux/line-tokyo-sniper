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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.cf.rule_engine import CFRuleEngine
from database.db import init_db, get_db, add_cf_rule, get_active_cf_rules, get_recent_cf_history, log_cf_action

async def run_cf_tests():
    print("=== [1/5] Testing Database Init & Seed Rules ===")
    await init_db()
    rules = await get_active_cf_rules()
    print(f"[OK] Loaded {len(rules)} active CF rules:")
    for r in rules:
        print(f" - Rule: {r['name']} | Keywords: {r['target_keywords']} | Format: {r['cf_format']}")
    assert len(rules) >= 1, "At least one active rule should exist"

    print("\n=== [2/5] Testing Labubu V2 Seller Message (Should Match & CF) ===")
    test_msg_1 = "เปิดจองพร้อมส่ง Labubu V2 แท้ 100% รหัส A05 ราคา 850 บาท ใครรับพิมพ์ CF ด่วนค่ะ"
    res_1 = await CFRuleEngine.evaluate_message(
        room_name="OpenChat ซื้อขาย Labubu",
        sender_name="แม่ค้าแอน",
        message_text=test_msg_1
    )
    print(f"[OK] Evaluation Result: {res_1}")
    assert res_1["should_cf"] is True, "Should match Labubu rule"
    assert res_1["extracted_code"] == "A05", f"Expected code A05, got {res_1['extracted_code']}"
    assert "A05" in res_1["cf_message"], "CF message must contain extracted code"
    print(f"[OK] Generated CF Message: '{res_1['cf_message']}'")

    print("\n=== [3/5] Testing Negative Keyword Abort (Should NOT CF) ===")
    test_msg_2 = "Labubu V2 รหัส B01 ขายแล้วนะคะ หลุดจองจะแจ้งอีกทีค่ะ"
    res_2 = await CFRuleEngine.evaluate_message(
        room_name="OpenChat ซื้อขาย Labubu",
        sender_name="แม่ค้าแอน",
        message_text=test_msg_2
    )
    print(f"[OK] Evaluation Result: {res_2}")
    assert res_2["should_cf"] is False, "Should skip because item is sold out"
    print(f"[OK] Correctly skipped: {res_2['reason']}")

    print("\n=== [4/5] Testing Price Limit Filter ===")
    test_msg_3 = "พร้อมส่ง Labubu V2 รหัส C10 ราคา 3,500 บาท สภาพมือหนึ่ง"
    res_3 = await CFRuleEngine.evaluate_message(
        room_name="OpenChat ซื้อขาย Labubu",
        sender_name="แม่ค้าแอน",
        message_text=test_msg_3
    )
    print(f"[OK] Evaluation Result: {res_3}")
    # Default rule price limit is 1500.0, price is 3500.0
    assert res_3["should_cf"] is False, "Should skip because price exceeds limit"
    print(f"[OK] Correctly skipped over-budget item: {res_3['reason']}")

    print("\n=== [5/5] Testing CF Action Logging to Database ===")
    await log_cf_action(
        rule_id=1,
        rule_name="Labubu V2 / กล่องจุ่มยอดนิยม",
        room_name="OpenChat ซื้อขาย Labubu",
        sender_name="แม่ค้าแอน",
        original_message=test_msg_1,
        cf_text=res_1["cf_message"],
        status="SUCCESS",
        execution_time_ms=185.4
    )
    history = await get_recent_cf_history(limit=5)
    print(f"[OK] Retrieved {len(history)} items in CF history")
    assert len(history) > 0
    print(f"[OK] Latest CF Win: '{history[0]['cf_text']}' in '{history[0]['room_name']}' ({history[0]['execution_time_ms']}ms)")

    print("\n>>> ALL AUTO-CF SNIPER TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(run_cf_tests())
