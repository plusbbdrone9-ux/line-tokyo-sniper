"""
Ultra-low latency OpenChat Event Listener & Rule Dispatcher for Tokyo Cloud VPS.
Processes incoming messages and dispatches CF in < 20 ms.
"""

import time
import re
import hashlib
import asyncio
import logging
from typing import Optional, Dict, Any
from core.cf.rule_engine import CFRuleEngine
from database.db import log_cf_action, init_db
from .client import TokyoCloudSniperClient


logger = logging.getLogger("TokyoOpenChatListener")

class OpenChatEventListener:
    """
    Sub-millisecond event loop that listens to LINE OpenChat events,
    evaluates rules in memory (< 0.1ms), and fires Thrift RPC instantly.
    """

    def __init__(self, client: TokyoCloudSniperClient, target_square_chat_mid: Optional[str] = None):
        self.client = client
        self.target_mid = target_square_chat_mid or ""
        self.is_running = False
        self.recent_msg_hashes: Dict[str, float] = {}
        self.recently_sniped_codes: Dict[str, float] = {}
        self.last_sent_cf = ""
        self.is_executing_cf = False

        # Metrics
        self.stats_ingested = 0
        self.stats_matched = 0
        self.stats_wins = 0

    async def start_listening(self):
        """Starts real-time polling / WebSocket connection"""
        self.is_running = True
        logger.info(f"⚡ [Tokyo Cloud Sniper] Started event listener for target OpenChat: {self.target_mid or 'ALL'}")

        while self.is_running:
            try:
                # Real-time event polling loop
                # In production on Tokyo VPS, this polls the Square event channel with Keep-Alive
                await asyncio.sleep(0.01)  # 100 checks/sec
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Listener error: {e}")
                await asyncio.sleep(0.5)

    def stop_listening(self):
        self.is_running = False

    async def handle_incoming_square_message(
        self,
        square_chat_mid: str,
        sender_mid: str,
        sender_name: str,
        text: str,
        room_name: str = "LINE OpenChat"
    ) -> Dict[str, Any]:
        """
        Main low-latency handler executed immediately when a message packet arrives.
        Execution budget: < 0.1 ms in CPU before dispatching Thrift network call.
        """
        t_recv = time.perf_counter()
        raw_text = (text or "").strip()
        now = time.time()

        if not raw_text or len(raw_text) < 1:
            return {"status": "skipped", "reason": "empty"}

        # 1. Self-message suppression
        if self.last_sent_cf and (raw_text == self.last_sent_cf or self.last_sent_cf in raw_text):
            return {"status": "skipped", "reason": "self_cf"}

        # 2. Buyer reply filter (skip if another buyer is saying CF, จอง, etc.)
        if re.search(r"^(cf|จอง|รับ|เอา|พร้อมโอน)\b", raw_text, re.IGNORECASE) or raw_text.lower().startswith("cf "):
            return {"status": "skipped", "reason": "buyer_reply"}

        # 3. Fast MD5 Message Fingerprint (45s TTL)
        msg_hash = hashlib.md5(raw_text.lower().encode('utf-8')).hexdigest()
        if len(self.recent_msg_hashes) > 200:
            self.recent_msg_hashes = {k: v for k, v in self.recent_msg_hashes.items() if (now - v) < 120.0}

        if (now - self.recent_msg_hashes.get(msg_hash, 0)) < 45.0:
            return {"status": "skipped", "reason": "duplicate_hash"}
        self.recent_msg_hashes[msg_hash] = now

        # 4. In-Flight Lock
        if self.is_executing_cf:
            return {"status": "skipped", "reason": "in_flight_lock"}

        self.stats_ingested += 1

        # 5. Evaluate Rule in Memory (< 0.05 ms)
        res = await CFRuleEngine.evaluate_message(room_name, sender_name, raw_text)
        if not res.get("should_cf"):
            return {"status": "skipped", "reason": res.get("reason", "no_rule_match")}

        code = res.get("extracted_code", "")
        rule_id = res.get("rule_id", "default")
        cooldown_key = f"{rule_id}_{code.strip().lower()}" if code else f"rule_{rule_id}"

        # 6. Cooldown Check (30 seconds per rule/code)
        if (now - self.recently_sniped_codes.get(cooldown_key, 0)) < 30.0:
            return {"status": "skipped", "reason": "code_cooldown"}

        # Lock and fire!
        self.is_executing_cf = True
        self.recently_sniped_codes[cooldown_key] = now
        self.stats_matched += 1

        cf_msg = res["cf_message"]
        self.last_sent_cf = cf_msg

        logger.info(f"🎯 [SNIPER TRIGGERED] Rule '{res.get('rule_name')}': Code '{code}' -> Dispatching Thrift RPC!")

        try:
            # 7. Dispatch Thrift packet over persistent socket (10-15 ms on Tokyo VPS)
            target = square_chat_mid or self.target_mid
            send_res = await self.client.send_square_message_fast(target, cf_msg)

            t_finish = time.perf_counter()
            total_elapsed_ms = round((t_finish - t_recv) * 1000.0, 2)

            is_success = send_res.get("success", False)
            if is_success:
                self.stats_wins += 1
                logger.info(
                    f"🏆 [TOKYO SPEED WIN] CF '{cf_msg}' sent in {total_elapsed_ms} ms! "
                    f"(Serialize: {send_res.get('serialize_ms')}ms, Net: {send_res.get('network_ms')}ms)"
                )
                # Record to Database
                try:
                    await log_cf_action(
                        rule_id=res.get("rule_id"),
                        rule_name=res.get("rule_name", "Tokyo Rule"),
                        room_name=room_name,
                        sender_name=sender_name,
                        original_message=raw_text,
                        cf_text=cf_msg,
                        status="SUCCESS",
                        execution_time_ms=total_elapsed_ms
                    )
                except Exception as dbe:
                    logger.warning(f"DB insert failed: {dbe}")

            else:
                logger.error(f"❌ [SNIPER FAIL] Send failed: {send_res}")
                if cooldown_key in self.recently_sniped_codes:
                    del self.recently_sniped_codes[cooldown_key]

            return {
                "status": "executed",
                "success": is_success,
                "total_elapsed_ms": total_elapsed_ms,
                "metrics": send_res
            }
        finally:
            self.is_executing_cf = False
