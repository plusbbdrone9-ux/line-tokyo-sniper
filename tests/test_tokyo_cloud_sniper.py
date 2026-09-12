"""
Unit test for Tokyo Cloud Protocol Sniper (< 20ms).
Verifies serialization speed, memory matching, and anti-duplicate filtering.
"""

import unittest
import asyncio
import time

from gateways.cloud_protocol_sniper.protocol_thrift import (
    build_send_square_message_compact,
    build_get_square_events_compact
)
from gateways.cloud_protocol_sniper.client import TokyoCloudSniperClient
from gateways.cloud_protocol_sniper.listener import OpenChatEventListener
from database.db import init_db, add_cf_rule

async def test_compact_thrift_serialization_speed():
    """Verify serialization takes < 0.05ms (50 microseconds)"""
    t0 = time.perf_counter()
    count = 500
    for i in range(count):
        payload = build_send_square_message_compact(
            square_chat_mid="mc1234567890abcdef",
            text=f"CF A{i} พร้อมโอน",
            seq_id=i
        )
        assert len(payload) > 20
    t1 = time.perf_counter()

    avg_us = ((t1 - t0) / count) * 1_000_000
    print(f"\nAverage Compact Thrift serialization: {avg_us:.2f} µs")
    assert avg_us < 50.0  # Must be faster than 50 microseconds (0.05ms)


async def test_listener_deduplication_and_buyer_filter():

    """Verify buyer messages and duplicate messages are skipped immediately"""
    await init_db()

    client = TokyoCloudSniperClient()
    listener = OpenChatEventListener(client=client, target_square_chat_mid="mock_sq_mid")

    # 1. Buyer reply should be skipped
    res1 = await listener.handle_incoming_square_message(
        square_chat_mid="mock_sq_mid",
        sender_mid="buyer_1",
        sender_name="Buyer1",
        text="CF C0 พร้อมโอน"
    )
    assert res1["status"] == "skipped"
    assert res1["reason"] == "buyer_reply"

    # 2. Another buyer reply
    res2 = await listener.handle_incoming_square_message(
        square_chat_mid="mock_sq_mid",
        sender_mid="buyer_2",
        sender_name="Buyer2",
        text="จอง 1 ตัว"
    )
    assert res2["status"] == "skipped"
    assert res2["reason"] == "buyer_reply"

    # 3. Duplicate hash detection
    res3 = await listener.handle_incoming_square_message(
        square_chat_mid="mock_sq_mid",
        sender_mid="seller_1",
        sender_name="แม่ค้า",
        text="สวัสดีค่ะ ขอต้อนรับทุกคน"
    )
    # First time: skipped because no rule match
    assert res3["status"] == "skipped"

    # Second time immediately with exact same text: skipped because duplicate hash!
    res4 = await listener.handle_incoming_square_message(
        square_chat_mid="mock_sq_mid",
        sender_mid="seller_1",
        sender_name="แม่ค้า",
        text="สวัสดีค่ะ ขอต้อนรับทุกคน"
    )
    assert res4["status"] == "skipped"
    assert res4["reason"] == "duplicate_hash"
