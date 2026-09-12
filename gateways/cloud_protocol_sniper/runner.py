"""
Headless Runner for Tokyo Cloud Protocol Sniper (< 20ms).
Run on Tokyo VPS:
    python -m gateways.cloud_protocol_sniper.runner
"""

import sys
import os
import time
import asyncio
import logging
from typing import Optional

# Setup base directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


from core.config import settings
from database.db import init_db, get_active_cf_rules
from gateways.cloud_protocol_sniper.client import TokyoCloudSniperClient
from gateways.cloud_protocol_sniper.listener import OpenChatEventListener
from gateways.cloud_protocol_sniper.protocol_thrift import build_send_square_message_compact

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TokyoSniperRunner")

BANNER = r"""
========================================================================
   ⚡ LINE OpenChat Tokyo Cloud Protocol Sniper (Ultra-Fast < 20ms) ⚡
========================================================================
   Location Target : Tokyo Data Center (ga2.line.naver.jp / legy-jp)
   Protocol        : Thrift RPC / Keep-Alive HTTP/2 Socket
   Engine Mode     : Sub-Millisecond In-Memory Rule Evaluation
========================================================================
"""

async def run_latency_benchmark(client: TokyoCloudSniperClient):
    """Measures RTT to LINE Gateway and Serialization Speed"""
    print("\n🔍 [1/3] กำลังทดสอบวัดความเร็วการประมวลผลและค่า Ping...")

    # Benchmark in-memory serialization
    t0 = time.perf_counter()
    for _ in range(1000):
        _ = build_send_square_message_compact("c1234567890abcdef", "CF C0 พร้อมโอน", seq_id=1)
    t1 = time.perf_counter()
    avg_serialize_us = round(((t1 - t0) / 1000.0) * 1_000_000, 2)
    print(f"   ⚡ ความเร็วประกอบข้อมูล Binary Thrift ในแรม: {avg_serialize_us} µs (ไมโครวินาที) ต่อแพ็กเก็ต!")

    # Benchmark Ping to Tokyo LINE Gateway
    ping_ms = await client.measure_ping_ms()
    if ping_ms < 10.0:
        badge = "🟢 ยอดเยี่ยม! (Tokyo VPS Data Center)"
    elif ping_ms < 40.0:
        badge = "🟡 ดี (ภูมิภาคเอเชียใกล้เคียง)"
    else:
        badge = "🔴 ปานกลาง (รันจากเน็ตบ้านนอกประเทศญี่ปุ่น)"

    print(f"   📡 ค่า Latency Ping ไปยัง LINE Gateway ({client.host}): {ping_ms} ms -> {badge}\n")


async def print_active_rules():
    """Prints all active sniper rules loaded from database"""
    rules = await get_active_cf_rules()
    print(f"📋 [2/3] รายการกฎสไนเปอร์ที่เปิดใช้งานในระบบ ({len(rules)} กฎ):")
    if not rules:
        print("   ⚠ ยังไม่มีกฎการ CF ในระบบ กรุณาเพิ่มกฎผ่านหน้า Desktop App หรือ Web UI")
    for r in rules:
        print(f"   - [ID:{r['id']}] {r['name']} | ห้อง: '{r.get('target_rooms') or 'ทุกห้อง'}' | คีย์เวิร์ด: '{r['target_keywords']}' -> CF: '{r['cf_format']}'")
    print("")



async def start_http_status_server(listener: OpenChatEventListener, port: int = 8080):
    """Lightweight HTTP server on VPS for status monitoring and simulation"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class StatusHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/status" or self.path == "/":
                data = {
                    "status": "online",
                    "mode": "TOKYO_PROTOCOL_SNIPER",
                    "stats": {
                        "ingested": listener.stats_ingested,
                        "matched": listener.stats_matched,
                        "wins": listener.stats_wins
                    },
                    "target_mid": listener.target_mid or "ALL",
                    "timestamp": time.time()
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/simulate" or self.path == "/api/square/incoming":
                length = int(self.headers.get("content-length", 0))
                data = self.rfile.read(length)
                try:
                    payload = json.loads(data.decode("utf-8"))
                    text = payload.get("text", "")
                    sender = payload.get("sender", "แม่ค้า")
                    room = payload.get("room", "LINE OpenChat")
                    square_mid = payload.get("square_chat_mid", "mock_mid")

                    # Dispatch to low-latency handler
                    asyncio.run_coroutine_threadsafe(
                        listener.handle_incoming_square_message(
                            square_chat_mid=square_mid,
                            sender_mid="mock_sender",
                            sender_name=sender,
                            text=text,
                            room_name=room
                        ),
                        asyncio.get_event_loop()
                    )

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"received","processed":true}')
                except Exception as e:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(str(e).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

    import threading
    server = HTTPServer(("0.0.0.0", port), StatusHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"🌐 [3/3] เปิด Web Status & Ingest API เรียบร้อยที่: http://0.0.0.0:{port}/status\n")


async def main():
    print(BANNER)
    await init_db()

    client = TokyoCloudSniperClient()
    listener = OpenChatEventListener(client=client, target_square_chat_mid=settings.TARGET_SQUARE_CHAT_MID)

    # 1. Latency & Ping
    await run_latency_benchmark(client)

    # 2. Rules List
    await print_active_rules()

    # 3. Status Server
    port = int(os.getenv("PORT", "8080"))
    await start_http_status_server(listener, port=port)

    # 4. Auth Verification
    if not client.auth_token:
        print("💡 [คำแนะนำการเข้าสู่ระบบ]:")
        print("   ยังไม่พบ LINE_AUTH_TOKEN ในไฟล์ .env")
        print("   คุณสามารถใส่ LINE_AUTH_TOKEN=<โทเค็น> ใน .env เพื่อเชื่อมต่อทันที")
        print("   ระบบกำลังเตรียมพร้อมรอรับข้อความผ่าน Socket และ API...\n")
    else:
        print(f"🔑 [เข้าสู่ระบบ]: พบ Token เรียบร้อยแล้ว (ความยาว: {len(client.auth_token)} ตัวอักษร)\n")

    print("🟢 [READY] ระบบ Tokyo Cloud Protocol Sniper กำลังทำงานและพร้อมยิงทันทีในระดับ < 20ms!")
    print("กด Ctrl+C เพื่อหยุดการทำงาน\n")

    try:
        await listener.start_listening()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n🛑 หยุดการทำงานเรียบร้อยแล้ว")
    finally:
        await client.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
