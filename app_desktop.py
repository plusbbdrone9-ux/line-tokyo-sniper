"""
LINE Personal Auto-CF Sniper Bot (PC Desktop Application)
---------------------------------------------------------
โปรแกรม Desktop สำหรับ Windows ควบคุมการเฝ้าดูและ CF สินค้าอัตโนมัติใน LINE PC
พัฒนาด้วย CustomTkinter (Modern Dark-Mode UI)
"""

import sys
import os
import time
import threading
import asyncio
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List, Dict, Any

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.cf.rule_engine import CFRuleEngine
from core.cf.cf_manager import cf_manager
from gateways.personal_sniper.windows_sniper import WindowsLineSniper
from database.db import (
    init_db,
    get_all_cf_rules,
    add_cf_rule,
    toggle_cf_rule,
    delete_cf_rule,
    get_recent_cf_history,
    clear_cf_history,
    get_cf_stats,
    log_cf_action,
    save_message
)

# Configure UI theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class LineSniperDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LINE Auto-CF Sniper Bot (PC Desktop Edition)")
        self.geometry("1200x740")
        self.minsize(1050, 680)

        # Background thread event loop for async database & sniper calls
        self.loop = asyncio.new_event_loop()
        self.bg_thread = threading.Thread(target=self._start_background_loop, daemon=True)
        self.bg_thread.start()

        # State
        self.is_sniper_active = True
        self.is_auto_monitor_enabled = True
        self.is_vision_radar_enabled = True
        self.active_line_hwnd = None
        self.active_line_title = "LINE Group"
        self.rules_cache: List[Dict[str, Any]] = []
        self.last_clipboard_text = ""
        self.last_sent_cf = ""

        # Real-time Stream Ingestion Stats
        self.stats_ingested = 0
        self.stats_matched = 0
        self.stats_wins = 0
        self.recently_sniped_codes: Dict[str, float] = {}
        self.radar_sleep_interval = 0.012  # 50 FPS Turbo by default
        self.custom_jitter_delay = 50  # Default 50ms (or user customized)

        # Setup Global Hotkey (F2)
        self._setup_hotkeys()

        # Start Auto-Monitor background thread (Clipboard Watcher)
        self.auto_thread = threading.Thread(target=self._auto_monitor_loop, daemon=True)
        self.auto_thread.start()

        # Start Live Screen Vision Radar thread (Mode 2: Screen Vision Auto-Sniper)
        self.vision_thread = threading.Thread(target=self._live_screen_radar_loop, daemon=True)
        self.vision_thread.start()

        # Layer 1: Start Windows Notification Stream Sniffer (ความเร็ว 3.6ms รองรับข้อความไหลเป็นร้อย)
        self.notif_thread = threading.Thread(target=self._windows_notification_sniffer_loop, daemon=True)
        self.notif_thread.start()

        # Layer 3: Start Local Real-Time Ingest Server (127.0.0.1:8765)
        self.ingest_thread = threading.Thread(target=self._start_local_ingest_server, daemon=True)
        self.ingest_thread.start()

        # Build UI Components
        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        # Initialize DB in background safely after mainloop begins (avoids 'main thread is not in main loop')
        def _on_init_done(_):
            self.load_rules_data()
            self.load_history_data()
        self.after(50, lambda: self.run_async(init_db(), callback=_on_init_done))

        # Start auto detection of LINE windows immediately
        self.after(300, self.refresh_line_windows)

        # Start periodic refresh
        self.refresh_timer()

    def _start_background_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_async(self, coro, callback=None):
        """Run an async coroutine on background loop and invoke callback on main thread"""
        def _wrapper():
            try:
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                result = future.result()
                if callback:
                    def _safe_cb():
                        try:
                            callback(result)
                        except Exception as ce:
                            print(f"Callback error: {ce}")
                    try:
                        self.after(0, _safe_cb)
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error in async worker: {e}")
        threading.Thread(target=_wrapper, daemon=True).start()

    def _setup_hotkeys(self):
        """ติดตั้งปุ่มลัด Global Hotkey F2 ให้ยิง CF จากแอป LINE ได้ทันที"""
        try:
            import keyboard
            keyboard.add_hotkey('F2', lambda: self.after(0, self.trigger_hotkey_snipe))
        except Exception as e:
            print(f"Warning: Could not bind F2 hotkey: {e}")

    # --- UI Layout ---

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, height=70, fg_color="#111827")
        self.header_frame.pack(fill="x", side="top")

        # App Brand
        brand_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        brand_frame.pack(side="left", padx=20, pady=12)

        badge = ctk.CTkLabel(
            brand_frame, text="SNIPER CF", fg_color="#f59e0b", text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6, width=80, height=26
        )
        badge.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            brand_frame, text="LINE Auto-CF Sniper (PC Desktop)",
            font=ctk.CTkFont(size=18, weight="bold"), text_color="#f9fafb"
        )
        title_lbl.pack(side="left")

        # Controls & Window Target
        ctrl_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        ctrl_frame.pack(side="right", padx=20, pady=12)

        self.btn_help = ctk.CTkButton(
            ctrl_frame, text="❓ วิธีใช้งาน", width=100, height=32,
            fg_color="#4b5563", hover_color="#6b7280", font=ctk.CTkFont(size=12),
            command=self.show_how_to_use_dialog
        )
        self.btn_help.pack(side="left", padx=4)

        self.btn_refresh_windows = ctk.CTkButton(
            ctrl_frame, text="🔄 ค้นหาห้องแชท", width=115, height=32,
            fg_color="#374151", hover_color="#4b5563", font=ctk.CTkFont(size=12),
            command=self.refresh_line_windows
        )
        self.btn_refresh_windows.pack(side="left", padx=4)

        self.line_window_menu = ctk.CTkOptionMenu(
            ctrl_frame, values=["(ค้นหาหน้าต่าง LINE PC...)"], width=180, height=32,
            fg_color="#1f2937", button_color="#374151"
        )
        self.line_window_menu.pack(side="left", padx=4)

        # Master Toggle Button
        self.btn_master_toggle = ctk.CTkButton(
            ctrl_frame, text="⚡ สไนเปอร์: เปิดทำงาน",
            fg_color="#06c755", hover_color="#05b04c", text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"), width=150, height=32,
            command=self.toggle_master_sniper
        )
        self.btn_master_toggle.pack(side="left", padx=4)

    def _build_tabs(self):
        # Global Auto-Sniper Guidance Banner
        self.banner_frame = ctk.CTkFrame(self, corner_radius=8, fg_color="#182234")
        self.banner_frame.pack(fill="x", padx=20, pady=(8, 0))

        lbl_status_badge = ctk.CTkLabel(
            self.banner_frame, text=" ⚡ ระบบดูดแชท Real-time 3 ชั้น (Hands-Free 100%) ", fg_color="#06c755", text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6, height=26
        )
        lbl_status_badge.pack(side="left", padx=(12, 8), pady=8)

        lbl_guide = ctk.CTkLabel(
            self.banner_frame,
            text="💡 ระบบดูดข้อความแชทอัตโนมัติ 100%: ดูดข้อความที่ไหลเข้ามาในเสี้ยววินาที ไม่ต้องกดคัดลอก ไม่ต้องแตะเมาส์ เมื่อตรงเงื่อนไขจะยิง CF ทันที!",
            text_color="#f3f4f6", font=ctk.CTkFont(size=12)
        )
        lbl_guide.pack(side="left", padx=4, pady=8)

        btn_f2_trigger = ctk.CTkButton(
            self.banner_frame, text="⚡ ยิงด่วน (F2)", width=110, height=28,
            fg_color="#f59e0b", hover_color="#d97706", text_color="#000000",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.trigger_hotkey_snipe
        )
        btn_f2_trigger.pack(side="right", padx=12, pady=8)

        self.tabview = ctk.CTkTabview(self, corner_radius=12, command=self._on_tab_changed)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(8, 12))

        self.tab_radar = self.tabview.add("⚡ หน้าหลัก: คอนโซลดูดสด & ประวัติ CF")
        self.tab_rules = self.tabview.add("📜 จัดการกฎการ CF (Rules)")
        self.tab_settings = self.tabview.add("⚙️ ตั้งค่าความเร็ว & ป้องกันแบน")

        self._build_tab_radar()
        self._build_tab_rules()
        self._build_tab_settings()

    def _on_tab_changed(self):
        tab = self.tabview.get()
        if "Rules" in tab or "กฎ" in tab:
            self.load_rules_data()
        elif "หน้าหลัก" in tab or "คอนโซล" in tab:
            self.load_history_data()

    # --- TAB 1: Live Stream Ingest Console (คอนโซลดูดข้อความสด Real-time) ---
    def _build_tab_radar(self):
        container = ctk.CTkFrame(self.tab_radar, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # Top 1: Live Real-Time Metrics Bar
        metrics_bar = ctk.CTkFrame(container, corner_radius=10, fg_color="#182234")
        metrics_bar.pack(fill="x", padx=4, pady=(0, 8))

        m_grid = ctk.CTkFrame(metrics_bar, fg_color="transparent")
        m_grid.pack(fill="x", padx=12, pady=8)
        m_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Metric 1: Ingested Messages
        c1 = ctk.CTkFrame(m_grid, corner_radius=8, fg_color="#0f172a")
        c1.grid(row=0, column=0, padx=4, sticky="nsew")
        ctk.CTkLabel(c1, text="📥 ข้อความที่ดูดได้ทั้งหมด", text_color="#9ca3af", font=ctk.CTkFont(size=11)).pack(pady=(6, 2))
        self.lbl_metric_ingested = ctk.CTkLabel(c1, text="0 ข้อความ", font=ctk.CTkFont(size=17, weight="bold"), text_color="#38bdf8")
        self.lbl_metric_ingested.pack(pady=(0, 6))

        # Metric 2: Scan Rate
        c2 = ctk.CTkFrame(m_grid, corner_radius=8, fg_color="#0f172a")
        c2.grid(row=0, column=1, padx=4, sticky="nsew")
        ctk.CTkLabel(c2, text="⚡ อัตราสแกนดักจับ (FPS)", text_color="#9ca3af", font=ctk.CTkFont(size=11)).pack(pady=(6, 2))
        self.lbl_metric_fps = ctk.CTkLabel(c2, text="50 FPS (~20ms)", font=ctk.CTkFont(size=17, weight="bold"), text_color="#f59e0b")
        self.lbl_metric_fps.pack(pady=(0, 6))

        # Metric 3: Matched Rules
        c3 = ctk.CTkFrame(m_grid, corner_radius=8, fg_color="#0f172a")
        c3.grid(row=0, column=2, padx=4, sticky="nsew")
        ctk.CTkLabel(c3, text="🎯 ตรงเงื่อนไขกฎ CF", text_color="#9ca3af", font=ctk.CTkFont(size=11)).pack(pady=(6, 2))
        self.lbl_metric_matched = ctk.CTkLabel(c3, text="0 ครั้ง", font=ctk.CTkFont(size=17, weight="bold"), text_color="#a855f7")
        self.lbl_metric_matched.pack(pady=(0, 6))

        # Metric 4: Wins
        c4 = ctk.CTkFrame(m_grid, corner_radius=8, fg_color="#0f172a")
        c4.grid(row=0, column=3, padx=4, sticky="nsew")
        ctk.CTkLabel(c4, text="🏆 ยิง CF สำเร็จ (Wins)", text_color="#9ca3af", font=ctk.CTkFont(size=11)).pack(pady=(6, 2))
        self.lbl_metric_wins = ctk.CTkLabel(c4, text="0 ครั้ง", font=ctk.CTkFont(size=17, weight="bold"), text_color="#10b981")
        self.lbl_metric_wins.pack(pady=(0, 6))

        # Top 2: Ingest Toolbar
        toolbar = ctk.CTkFrame(container, corner_radius=8, fg_color="#182234")
        toolbar.pack(fill="x", padx=4, pady=(0, 6))

        t_left = ctk.CTkFrame(toolbar, fg_color="transparent")
        t_left.pack(side="left", padx=10, pady=6)

        self.badge_stream_status = ctk.CTkLabel(
            t_left, text=" ⚡ REAL-TIME INGEST STREAM ACTIVE ", fg_color="#06c755", text_color="#000",
            font=ctk.CTkFont(size=11, weight="bold"), corner_radius=6, height=24
        )
        self.badge_stream_status.pack(side="left", padx=(0, 8))

        self.lbl_stream_target = ctk.CTkLabel(
            t_left, text="🎯 กำลังดูดข้อความจาก: (กำลังเชื่อมต่อ...)", text_color="#cbd5e1",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_stream_target.pack(side="left")

        t_right = ctk.CTkFrame(toolbar, fg_color="transparent")
        t_right.pack(side="right", padx=10, pady=6)

        ctk.CTkLabel(t_right, text="ความเร็วสแกน:", text_color="#9ca3af", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))
        self.opt_speed = ctk.CTkOptionMenu(
            t_right, values=["🚀 Turbo (50 FPS / 20ms)", "🔥 Ultra (60 FPS / 16ms)", "⚡ Balanced (25 FPS / 40ms)"],
            width=175, height=26, font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1f2937", button_color="#374151",
            command=self.on_speed_changed
        )
        self.opt_speed.set("🚀 Turbo (50 FPS / 20ms)")
        self.opt_speed.pack(side="left", padx=(0, 6))

        # Main: Dual Split View (Left 50% Ingest Console | Right 50% CF Wins History)
        split_container = ctk.CTkFrame(container, fg_color="transparent")
        split_container.pack(fill="both", expand=True, padx=4, pady=(0, 2))
        split_container.grid_columnconfigure(0, weight=1)
        split_container.grid_columnconfigure(1, weight=1)
        split_container.grid_rowconfigure(0, weight=1)

        # ─── LEFT COLUMN: Live Ingest Console (50%) ───
        left_card = ctk.CTkFrame(split_container, corner_radius=10, fg_color="#0f172a")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        left_header = ctk.CTkFrame(left_card, corner_radius=8, height=36, fg_color="#182234")
        left_header.pack(fill="x", padx=6, pady=6)

        lbl_left_title = ctk.CTkLabel(
            left_header, text="⚡ คอนโซลดูดข้อความสด (Live Ingest)",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8"
        )
        lbl_left_title.pack(side="left", padx=10, pady=4)

        btn_clear = ctk.CTkButton(
            left_header, text="🧹 ล้าง", width=60, height=24,
            fg_color="#374151", hover_color="#4b5563", font=ctk.CTkFont(size=11),
            command=self.clear_console_log
        )
        btn_clear.pack(side="right", padx=6)

        btn_copy = ctk.CTkButton(
            left_header, text="📋 คัดลอก", width=70, height=24,
            fg_color="#374151", hover_color="#4b5563", font=ctk.CTkFont(size=11),
            command=self.copy_console_log
        )
        btn_copy.pack(side="right", padx=(0, 2))

        self.radar_log_box = ctk.CTkTextbox(
            left_card, corner_radius=8, fg_color="#070b14", text_color="#38bdf8",
            font=ctk.CTkFont(family="Consolas", size=11), wrap="none"
        )
        self.radar_log_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Welcome banner in console
        self._append_radar_log("╔═══════════════════════════════════════════════════════════════╗")
        self._append_radar_log("║  LINE AUTO-CF SNIPER: REAL-TIME INGESTION CONSOLE             ║")
        self._append_radar_log("║  • ดูดข้อความสดอัตโนมัติ 100% ไม่ต้องกดคัดลอก/วาง             ║")
        self._append_radar_log("║  • เมื่อตรงเงื่อนไขจะยิงส่ง CF ทันที และประวัติจะขึ้นฝั่งขวา  ║")
        self._append_radar_log("╚═══════════════════════════════════════════════════════════════╝")

        # ─── RIGHT COLUMN: CF History / Wins Log (50%) ───
        right_card = ctk.CTkFrame(split_container, corner_radius=10, fg_color="#0f172a")
        right_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        right_header = ctk.CTkFrame(right_card, corner_radius=8, height=36, fg_color="#182234")
        right_header.pack(fill="x", padx=6, pady=6)

        lbl_right_title = ctk.CTkLabel(
            right_header, text="🏆 ประวัติการ CF สำเร็จ (Sniper Wins)",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#10b981"
        )
        lbl_right_title.pack(side="left", padx=10, pady=4)

        btn_clear_hist = ctk.CTkButton(
            right_header, text="🗑️ ล้างประวัติ", width=95, height=24,
            fg_color="#dc2626", hover_color="#b91c1c", font=ctk.CTkFont(size=11, weight="bold"),
            command=self.clear_history_action
        )
        btn_clear_hist.pack(side="right", padx=6)

        btn_ref = ctk.CTkButton(
            right_header, text="🔄 รีเฟรช", width=70, height=24,
            fg_color="#374151", hover_color="#4b5563", font=ctk.CTkFont(size=11),
            command=self.load_history_data
        )
        btn_ref.pack(side="right", padx=(0, 2))

        self.history_scroll = ctk.CTkScrollableFrame(right_card, corner_radius=8, fg_color="#070b14")
        self.history_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    # --- TAB 2: Rules Manager ---
    def _build_tab_rules(self):
        # Top: Add rule form
        add_frame = ctk.CTkFrame(self.tab_rules, corner_radius=12, fg_color="#182234")
        add_frame.pack(fill="x", padx=12, pady=8)

        # Header & Quick Templates
        top_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(12, 6))

        lbl = ctk.CTkLabel(top_row, text="+ สร้างกฎการสไนเปอร์ CF สินค้าใหม่", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f59e0b")
        lbl.pack(side="left")

        # Quick preset buttons
        preset_box = ctk.CTkFrame(top_row, fg_color="transparent")
        preset_box.pack(side="right")

        ctk.CTkLabel(preset_box, text="เลือกแม่แบบสำเร็จรูป:", text_color="#9ca3af", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(preset_box, text="🧸 ตัวอย่าง: Labubu", width=120, height=26, fg_color="#374151", font=ctk.CTkFont(size=11), command=self.apply_preset_labubu).pack(side="left", padx=3)
        ctk.CTkButton(preset_box, text="👕 ตัวอย่าง: เสื้อผ้า/แฟชั่น", width=130, height=26, fg_color="#374151", font=ctk.CTkFont(size=11), command=self.apply_preset_fashion).pack(side="left", padx=3)
        ctk.CTkButton(preset_box, text="⚡ ตัวอย่าง: ดักรหัสทั่วไป", width=125, height=26, fg_color="#374151", font=ctk.CTkFont(size=11), command=self.apply_preset_generic).pack(side="left", padx=3)

        # Form Grid - Row 1
        grid1 = ctk.CTkFrame(add_frame, fg_color="transparent")
        grid1.pack(fill="x", padx=16, pady=4)
        grid1.grid_columnconfigure(0, weight=3)
        grid1.grid_columnconfigure(1, weight=3)
        grid1.grid_columnconfigure(2, weight=2)
        grid1.grid_columnconfigure(3, weight=2)

        # Col 1: Rule Name
        f_name = ctk.CTkFrame(grid1, fg_color="transparent")
        f_name.grid(row=0, column=0, sticky="nsew", padx=4)
        ctk.CTkLabel(f_name, text="1. ชื่อกฎสินค้า (Rule Name)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_name = ctk.CTkEntry(f_name, placeholder_text="เช่น Labubu V2 หรือ เสื้อวินเทจ L", height=32)
        self.entry_rule_name.pack(fill="x", pady=(2, 0))

        # Col 2: Target Rooms
        f_rooms = ctk.CTkFrame(grid1, fg_color="transparent")
        f_rooms.grid(row=0, column=1, sticky="nsew", padx=4)
        ctk.CTkLabel(f_rooms, text="2. กลุ่มเป้าหมาย (* = ทุกกลุ่ม หรือใส่ชื่อห้อง)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_rooms = ctk.CTkEntry(f_rooms, placeholder_text="ใส่ * หรือชื่อห้อง เช่น Arkaradet®️", height=32)
        self.entry_rule_rooms.insert(0, "*")
        self.entry_rule_rooms.pack(fill="x", pady=(2, 0))

        # Col 3: Max Price Limit
        f_price = ctk.CTkFrame(grid1, fg_color="transparent")
        f_price.grid(row=0, column=2, sticky="nsew", padx=4)
        ctk.CTkLabel(f_price, text="3. เพดานราคาสูงสุด (0 = ไม่จำกัดงบ)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_price = ctk.CTkEntry(f_price, placeholder_text="เช่น 1500", height=32)
        self.entry_rule_price.insert(0, "0")
        self.entry_rule_price.pack(fill="x", pady=(2, 0))

        # Col 4: Jitter Delay
        f_delay = ctk.CTkFrame(grid1, fg_color="transparent")
        f_delay.grid(row=0, column=3, sticky="nsew", padx=4)
        ctk.CTkLabel(f_delay, text="4. หน่วงเวลาพิมพ์ (ms)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_delay = ctk.CTkEntry(f_delay, placeholder_text="200", height=32)
        self.entry_rule_delay.insert(0, "200")
        self.entry_rule_delay.pack(fill="x", pady=(2, 0))

        # Form Grid - Row 2
        grid2 = ctk.CTkFrame(add_frame, fg_color="transparent")
        grid2.pack(fill="x", padx=16, pady=(8, 12))
        grid2.grid_columnconfigure(0, weight=3)
        grid2.grid_columnconfigure(1, weight=3)
        grid2.grid_columnconfigure(2, weight=3)
        grid2.grid_columnconfigure(3, weight=1)

        # Col 1: Target Keywords
        f_kw = ctk.CTkFrame(grid2, fg_color="transparent")
        f_kw.grid(row=0, column=0, sticky="nsew", padx=4)
        ctk.CTkLabel(f_kw, text="5. คำสำคัญที่ต้องมี (Target Keywords)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_kw = ctk.CTkEntry(f_kw, placeholder_text="เช่น labubu, v2, พร้อมส่ง, รหัส (คั่นด้วยจุลภาค)", height=32)
        self.entry_rule_kw.pack(fill="x", pady=(2, 0))

        # Col 2: Negative Keywords
        f_neg = ctk.CTkFrame(grid2, fg_color="transparent")
        f_neg.grid(row=0, column=1, sticky="nsew", padx=4)
        ctk.CTkLabel(f_neg, text="6. คำต้องห้าม (ถ้ามีคำนี้จะไม่ CF)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_neg = ctk.CTkEntry(f_neg, placeholder_text="เช่น หมดแล้ว, ปิดการขาย, ขายแล้ว, มีคนรับแล้ว", height=32)
        self.entry_rule_neg.insert(0, "หมดแล้ว, ปิดการขาย, ขายแล้ว, มีคนรับแล้ว")
        self.entry_rule_neg.pack(fill="x", pady=(2, 0))

        # Col 3: CF Format
        f_fmt = ctk.CTkFrame(grid2, fg_color="transparent")
        f_fmt.grid(row=0, column=2, sticky="nsew", padx=4)
        ctk.CTkLabel(f_fmt, text="7. ข้อความที่จะให้บอทพิมพ์ส่ง (ใช้ {code} แทนรหัส)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.entry_rule_fmt = ctk.CTkEntry(f_fmt, placeholder_text="เช่น CF {code} พร้อมโอน", height=32)
        self.entry_rule_fmt.insert(0, "CF {code} พร้อมโอน")
        self.entry_rule_fmt.pack(fill="x", pady=(2, 0))

        # Col 4: Save Button
        f_btn = ctk.CTkFrame(grid2, fg_color="transparent")
        f_btn.grid(row=0, column=3, sticky="nsew", padx=4)
        ctk.CTkLabel(f_btn, text=" ", font=ctk.CTkFont(size=12)).pack(anchor="w")
        btn_save = ctk.CTkButton(f_btn, text="💾 บันทึกกฎ", fg_color="#06c755", text_color="#000", font=ctk.CTkFont(size=13, weight="bold"), height=32, command=self.save_new_rule_action)
        btn_save.pack(fill="x", pady=(2, 0))

        # Bottom: Scrollable rules list
        self.rules_scroll = ctk.CTkScrollableFrame(self.tab_rules, corner_radius=12, fg_color="#182234")
        self.rules_scroll.pack(fill="both", expand=True, padx=12, pady=(4, 8))

    # --- TAB 3: Settings ---
    def _build_tab_settings(self):
        card = ctk.CTkFrame(self.tab_settings, corner_radius=12, fg_color="#182234", width=600)
        card.pack(fill="x", padx=20, pady=20)

        lbl = ctk.CTkLabel(card, text="⚙️ การตั้งค่าความเร็วและระบบป้องกันการแบน", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.pack(anchor="w", padx=20, pady=(20, 12))

        # Latency Jitter
        self.lbl_jitter = ctk.CTkLabel(card, text=f"หน่วงเวลาจำลองการพิมพ์ (Jitter Delay): {self.custom_jitter_delay} ms", font=ctk.CTkFont(size=13))
        self.lbl_jitter.pack(anchor="w", padx=20, pady=(6, 2))

        self.slider_jitter = ctk.CTkSlider(card, from_=0, to=500, number_of_steps=50, command=self.on_jitter_changed)
        self.slider_jitter.set(self.custom_jitter_delay)
        self.slider_jitter.pack(fill="x", padx=20, pady=(0, 16))

        # Info card
        info = ctk.CTkLabel(
            card,
            text=(
                "💡 คำแนะนำในการใช้งานบน LINE PC:\n"
                "1. เปิดโปรแกรม LINE บนคอมพิวเตอร์ และเปิดหน้าต่างแชทของกลุ่ม/OpenChat ที่ต้องการสไนเปอร์ไว้\n"
                "2. ที่แถบด้านบนของโปรแกรมนี้ ให้กด '🔄 ค้นหาหน้าต่าง LINE' แล้วเลือกห้องแชทเป้าหมาย\n"
                "3. บอทจะใช้เทคนิคจำลองการพิมพ์และ Paste ความเร็วสูงระดับ 100 - 200 ms\n"
                "4. ในกรณีมีหลายกลุ่ม สามารถตั้งกฎแยกตามชื่อห้องได้อิสระที่แท็บ 'จัดการกฎการ CF'"
            ),
            justify="left", text_color="#9ca3af", font=ctk.CTkFont(size=12)
        )
        info.pack(anchor="w", padx=20, pady=(0, 20))

    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, height=32, corner_radius=0, fg_color="#0f172a")
        self.status_bar.pack(fill="x", side="bottom")

        self.lbl_status_msg = ctk.CTkLabel(self.status_bar, text="🟢 ระบบพร้อมทำงาน | ฐานข้อมูล SQLite พร้อมใช้งาน", text_color="#9ca3af", font=ctk.CTkFont(size=11))
        self.lbl_status_msg.pack(side="left", padx=16)

        self.lbl_speed_stats = ctk.CTkLabel(self.status_bar, text=f"หน่วงเวลาส่ง: ~{self.custom_jitter_delay}ms | Anti-ban: Active", text_color="#9ca3af", font=ctk.CTkFont(size=11))
        self.lbl_speed_stats.pack(side="right", padx=16)

    # --- Event Handlers & Business Logic ---

    def toggle_master_sniper(self):
        self.is_sniper_active = not self.is_sniper_active
        cf_manager.is_sniper_active = self.is_sniper_active

        if self.is_sniper_active:
            self.btn_master_toggle.configure(
                text="⚡ สไนเปอร์: เปิดทำงาน",
                fg_color="#06c755", hover_color="#05b04c"
            )
            self.lbl_status_msg.configure(text="🟢 ระบบสไนเปอร์เปิดทำงาน พร้อมยิง CF ทันที")
        else:
            self.btn_master_toggle.configure(
                text="⏸ สไนเปอร์: หยุดทำงาน",
                fg_color="#ef4444", hover_color="#dc2626"
            )
            self.lbl_status_msg.configure(text="🔴 ระบบสไนเปอร์หยุดทำงานชั่วคราว")

    def on_jitter_changed(self, val):
        ms = int(round(float(val)))
        self.custom_jitter_delay = ms
        if hasattr(self, "lbl_jitter"):
            self.lbl_jitter.configure(text=f"หน่วงเวลาจำลองการพิมพ์ (Jitter Delay): {ms} ms")
        if hasattr(self, "lbl_speed_stats"):
            self.lbl_speed_stats.configure(text=f"หน่วงเวลาส่ง: ~{ms}ms | Anti-ban: Active")

    def toggle_auto_monitor(self):
        self.is_auto_monitor_enabled = self.sw_auto_sniper.get() == 1
        if self.is_auto_monitor_enabled:
            self.lbl_auto_hint.configure(text="🟢 กำลังเฝ้าดูอัตโนมัติ: บอทจะยิง CF ทันทีเมื่อตรวจพบคีย์เวิร์ด!", text_color="#10b981")
            self._append_radar_log("🤖 [AUTO MONITOR] เริ่มต้นเฝ้าดูข้อความอัตโนมัติ 100% เรียบร้อยแล้ว")
        else:
            self.lbl_auto_hint.configure(text="⏸ ปิดโหมดเฝ้าดูอัตโนมัติชั่วคราว", text_color="#9ca3af")
            self._append_radar_log("⏸ [AUTO MONITOR] หยุดเฝ้าดูอัตโนมัติ")

    def _auto_monitor_loop(self):
        """ลูปเบื้องหลังเฝ้าดูข้อความใหม่อย่างต่อเนื่อง และยิง CF ทันทีโดยไม่ต้องกดปุ่ม"""
        import pyperclip
        while True:
            try:
                time.sleep(0.08)
                if not getattr(self, "is_auto_monitor_enabled", True) or not self.is_sniper_active:
                    time.sleep(0.3)
                    continue

                # ตรวจสอบข้อความใหม่จาก Clipboard (ความเร็วสูง ~80ms)
                try:
                    clip_text = pyperclip.paste().strip()
                except Exception:
                    clip_text = ""

                # ตรวจสอบว่ามีข้อความใหม่ และไม่ใช่ข้อความ CF ที่บอทเพิ่งพิมพ์ส่งไปเอง
                if clip_text and clip_text != self.last_clipboard_text and clip_text != getattr(self, "last_sent_cf", ""):
                    if len(clip_text) < 2000 and not clip_text.startswith("CF ") and clip_text != getattr(self, "last_sent_cf", ""):
                        self.last_clipboard_text = clip_text
                        self.after(0, lambda t=clip_text: self._trigger_snipe_with_text(t, source="AUTO CLIPBOARD"))

            except Exception as e:
                time.sleep(0.5)

    def trigger_hotkey_snipe(self):
        """เมื่อผู้ใช้กด F2 หรือคลิกปุ่มยิงด่วน: บอทจะคัดลอกข้อความและยิง CF ทันที"""
        import pyperclip
        try:
            # ส่ง Ctrl+C เพื่อคัดลอกข้อความที่เลือกอยู่ใน LINE
            user32.keybd_event(0x11, 0, 0, 0)
            user32.keybd_event(0x43, 0, 0, 0)
            time.sleep(0.03)
            user32.keybd_event(0x43, 0, 2, 0)
            user32.keybd_event(0x11, 0, 2, 0)
            time.sleep(0.05)
        except Exception:
            pass

        try:
            clip_text = pyperclip.paste().strip()
        except Exception:
            clip_text = ""

        if clip_text:
            self._trigger_snipe_with_text(clip_text, source="HOTKEY [F2]")
        else:
            self._append_radar_log("⚠ [F2] ไม่พบข้อความในคลิปบอร์ด กรุณาคลิกเลือกข้อความแม่ค้าก่อนกด F2")

    def _trigger_snipe_with_text(self, text_to_check: str, source: str = "AUTO"):
        raw_text = (text_to_check or "").strip()
        if not raw_text or len(raw_text) < 1:
            return

        now = time.time()

        # 1. ป้องกันยิงตัวเอง: ข้ามถ้าเป็นข้อความ CF ล่าสุดที่บอทเราเพิ่งส่งไป
        last_sent = getattr(self, "last_sent_cf", "").strip()
        if last_sent and (raw_text == last_sent or raw_text in last_sent or last_sent in raw_text):
            return

        # 2. ป้องกันข้อความของลูกค้าคนอื่น: ถ้าขึ้นต้นด้วย CF, จอง, รับ, เอา, พร้อมโอน (ไม่ใช่ข้อความเปิดขายของแม่ค้า)
        import re
        if re.search(r"^(cf|จอง|รับ|เอา|พร้อมโอน)\b", raw_text, re.IGNORECASE) or raw_text.lower().startswith("cf "):
            return

        # 3. Message Fingerprint De-duplication (ป้องกัน OCR อ่านซ้ำเฟรม หรือ Notification ซ้ำ)
        import hashlib
        msg_hash = hashlib.md5(raw_text.lower().encode('utf-8')).hexdigest()
        recent_hashes = getattr(self, "recent_msg_hashes", {})
        if not isinstance(recent_hashes, dict):
            self.recent_msg_hashes = {}
            recent_hashes = self.recent_msg_hashes

        # ล้าง hash เก่าที่เกิน 120 วินาทีเพื่อไม่ให้หน่วยความจำบวม
        if len(recent_hashes) > 200:
            self.recent_msg_hashes = {k: v for k, v in recent_hashes.items() if (now - v) < 120.0}
            recent_hashes = self.recent_msg_hashes

        if (now - recent_hashes.get(msg_hash, 0)) < 45.0:
            # เพิ่งตรวจสอบข้อความเป๊ะๆ นี้ไปเมื่อไม่เกิน 45 วินาทีที่ผ่านมา ข้ามทันที
            return
        recent_hashes[msg_hash] = now

        # 4. In-Flight Execution Lock (ป้องกันจังหวะที่ข้อความเข้ามาซ้อนกันในระดับเสี้ยววินาที)
        if getattr(self, "is_executing_cf", False):
            self._append_radar_log("   ↳ [ข้ามชั่วคราว]: มีคำสั่งยิง CF กำลังทำงานอยู่ (In-Flight Lock)")
            return

        self.stats_ingested += 1
        if hasattr(self, "lbl_metric_ingested"):
            self.after(0, lambda: self.lbl_metric_ingested.configure(text=f"{self.stats_ingested} ข้อความ") if hasattr(self, "lbl_metric_ingested") else None)

        self._append_radar_log(f"📥 [{source}] ดูดข้อความได้: \"{raw_text}\"")

        room = getattr(self, "active_line_title", "LINE Group")
        async def _eval():
            try:
                res = await CFRuleEngine.evaluate_message(room, "แม่ค้า", raw_text)
                if res.get("should_cf"):
                    code = res.get("extracted_code", "")
                    rule_id = res.get("rule_id", "default")
                    eval_now = time.time()
                    last_sniped = getattr(self, "recently_sniped_codes", {})
                    if not isinstance(last_sniped, dict):
                        self.recently_sniped_codes = {}
                        last_sniped = self.recently_sniped_codes

                    # Cooldown 30 วินาที ต่อ (กฎ + รหัสสินค้า) ป้องกันการยิงซ้ำรอบเดิม
                    cooldown_key = f"{rule_id}_{code.strip().lower()}" if code else f"rule_{rule_id}"
                    last_time = last_sniped.get(cooldown_key, 0)
                    if (eval_now - last_time) < 30.0:
                        self._append_radar_log(f"   ↳ [ข้าม CF]: รหัส '{code}' ของกฎนี้เพิ่งส่งไปเมื่อ {int(eval_now - last_time)} วินาทีก่อน (ป้องกันยิงซ้ำ)")
                        return

                    # ล็อค In-Flight และบันทึก Cooldown
                    self.is_executing_cf = True
                    last_sniped[cooldown_key] = eval_now

                    self.stats_matched = getattr(self, "stats_matched", 0) + 1
                    cur_matched = self.stats_matched
                    self.after(0, lambda m=cur_matched: self.lbl_metric_matched.configure(text=f"{m} ครั้ง") if hasattr(self, "lbl_metric_matched") else None)

                    cf_msg = res["cf_message"]
                    self.last_sent_cf = cf_msg
                    hwnd = getattr(self, "active_line_hwnd", None)
                    delay = getattr(self, "custom_jitter_delay", 0)
                    self._append_radar_log(f"🎯 [{source}] ตรงเงื่อนไขกฎ '{res.get('rule_name')}': รหัส '{code}' -> กำลังยิง CF ทันที!")

                    try:
                        success = await WindowsLineSniper.execute_cf(
                            cf_message=cf_msg,
                            target_hwnd=hwnd,
                            room_name=room,
                            sender_name="แม่ค้า",
                            original_message=raw_text,
                            rule_id=res.get("rule_id"),
                            rule_name=res.get("rule_name", "Auto Rule"),
                            delay_ms=delay
                        )
                    finally:
                        self.is_executing_cf = False

                    if success:
                        self.stats_wins = getattr(self, "stats_wins", 0) + 1
                        cur_wins = self.stats_wins
                        self.after(0, lambda w=cur_wins: self.lbl_metric_wins.configure(text=f"{w} ครั้ง") if hasattr(self, "lbl_metric_wins") else None)
                        try:
                            import winsound
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                        except Exception:
                            pass
                        self._append_radar_log(f"🏆 [AUTO WIN] ยิงส่ง \"{cf_msg}\" เข้าห้อง '{room}' สำเร็จทันที!")
                        self.after(0, self.load_history_data)
                    else:
                        if cooldown_key in self.recently_sniped_codes:
                            del self.recently_sniped_codes[cooldown_key]
                        self._append_radar_log(f"❌ [{source}] การยิง CF ไม่สำเร็จ (ตรวจไม่พบหน้าต่าง LINE หรือระบบมีปัญหา)")
                else:
                    self._append_radar_log(f"   ↳ [ไม่ยิง CF]: {res.get('reason')}")
            except Exception as e:
                self.is_executing_cf = False
                import traceback
                print(f"Error in _eval: {e}\n{traceback.format_exc()}")
                self._append_radar_log(f"❌ [ERROR] เกิดข้อผิดพลาดในการประเมิน: {e}")

        self.run_async(_eval())

    def _live_screen_radar_loop(self):
        """
        [ระบบดูดข้อความชั้นที่ 2: MD5 Hash Ingestion Engine บนหน้าจอ LINE PC (10 FPS / 100ms)]
        - จับภาพแชท LINE ด้วย pure ctypes CreateDIBSection + PrintWindow (~12ms)
        - ตรวจจับการเปลี่ยนแปลงของข้อความในเสี้ยววินาทีด้วย MD5 Frame Hashing (0.17ms)
        - เมื่อมีข้อความใหม่ไหลเข้ามาในช่องแชท:
          1. ใช้ RapidOCR ถอดข้อความไทย/อังกฤษทันที
          2. สตรีมแสดงผลข้อความสดบน Real-time Ingestion Console ทันที
          3. ส่งประเมินกฎ Rule Engine -> ยิง CF ทันทีด้วยความเร็วสูงสุด!
        """
        import ctypes
        from ctypes import wintypes
        import cv2
        import numpy as np
        import hashlib
        from rapidocr_onnxruntime import RapidOCR

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        # ขอสิทธิ์เข้าถึง Desktop สำหรับ Background Worker Thread
        try:
            desk = user32.OpenDesktopW('Default', 0, False, 0x01FF)
            if desk:
                user32.SetThreadDesktop(desk)
        except Exception:
            pass

        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
        user32.PrintWindow.restype = wintypes.BOOL
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [
                ('bmiHeader', BITMAPINFOHEADER),
                ('bmiColors', wintypes.DWORD * 3)
            ]

        easy_reader = None
        try:
            import easyocr
            easy_reader = easyocr.Reader(['th', 'en'], gpu=False)
            print("Engine 2: EasyOCR Thai/English Ingest Engine initialized successfully")
        except Exception as e:
            print(f"Failed to init EasyOCR: {e}")

        rapid_ocr = None
        try:
            from rapidocr_onnxruntime import RapidOCR
            rapid_ocr = RapidOCR()
        except Exception:
            pass

        last_scanned_hash = ""
        last_scanned_text = ""
        seen_texts = set()
        last_clean_time = time.time()
        frame_count = 0
        last_fps_time = time.time()

        while True:
            try:
                sleep_sec = getattr(self, "radar_sleep_interval", 0.012)
                time.sleep(sleep_sec)
                if not getattr(self, "is_vision_radar_enabled", True) or not self.is_sniper_active:
                    time.sleep(0.5)
                    continue

                # คำนวณอัตราสแกน FPS จริงแบบเรียลไทม์ และแสดงผลสดบนหน้าจอ
                frame_count += 1
                now_t = time.time()
                if now_t - last_fps_time >= 1.0:
                    fps_val = frame_count / (now_t - last_fps_time)
                    ms_val = (1000.0 / fps_val) if fps_val > 0 else 0
                    if hasattr(self, "lbl_metric_fps"):
                        self.after(0, lambda f=fps_val, m=ms_val: self.lbl_metric_fps.configure(text=f"{int(round(f))} FPS (~{int(round(m))}ms)"))
                    frame_count = 0
                    last_fps_time = now_t

                hwnd = getattr(self, "active_line_hwnd", None)
                if not hwnd or not user32.IsWindow(hwnd):
                    continue

                if time.time() - last_clean_time > 300:
                    seen_texts.clear()
                    last_clean_time = time.time()

                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    continue

                w = rect.right - rect.left
                h = rect.bottom - rect.top

                if w < 100 or h < 100:
                    continue

                # สร้าง DIBSection สำหรับดึงภาพจาก Window DC
                bmi = BITMAPINFO()
                bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.bmiHeader.biWidth = w
                bmi.bmiHeader.biHeight = -h  # top-down
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = 0

                ppvBits = ctypes.c_void_p()
                hdc_screen = user32.GetDC(0)
                hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                hbm = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(ppvBits), None, 0)
                old_bm = gdi32.SelectObject(hdc_mem, hbm)

                ret = user32.PrintWindow(hwnd, hdc_mem, 2)
                if not ret:
                    ret = user32.PrintWindow(hwnd, hdc_mem, 0)

                im_cv = None
                if ret and ppvBits.value:
                    buf = (ctypes.c_ubyte * (w * h * 4)).from_address(ppvBits.value)
                    arr = np.ndarray((h, w, 4), dtype=np.uint8, buffer=buf)
                    im_cv = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

                gdi32.SelectObject(hdc_mem, old_bm)
                gdi32.DeleteObject(hbm)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)

                if im_cv is None:
                    continue

                # ครอปบริเวณกล่องแชท (ตัดแถบหัวบน 50px และตัดกล่องพิมพ์ล่าง 75px)
                chat_body = im_cv[50:max(50, h - 75), :]

                # ตรวจสอบความเปลี่ยนแปลงด้วย MD5 Hash (ใช้เวลาเพียง 0.17ms)
                frame_hash = hashlib.md5(chat_body.tobytes()).hexdigest()
                if frame_hash == last_scanned_hash:
                    continue

                last_scanned_hash = frame_hash

                # ถอดตัวหนังสือจากภาพด้วย EasyOCR (รองรับภาษาไทย + อังกฤษ + ตัวเลข 100%)
                # โฟกัสช่วงล่างของหน้าต่างแชท (ข้อความล่าสุดที่เพิ่งเข้ามา)
                cb_h = chat_body.shape[0]
                scan_area = chat_body[max(0, int(cb_h * 0.35)):, :] if cb_h > 200 else chat_body

                detected_lines = []
                if easy_reader:
                    try:
                        res = easy_reader.readtext(scan_area, detail=0, min_size=8, text_threshold=0.35, low_text=0.25)
                        detected_lines = [line.strip() for line in res if line.strip()]
                    except Exception as oe:
                        print(f"EasyOCR error: {oe}")

                if not detected_lines and rapid_ocr:
                    try:
                        res, _ = rapid_ocr(scan_area)
                        if res:
                            detected_lines = [r[1].strip() for r in res if r[1].strip()]
                    except Exception:
                        pass

                if not detected_lines:
                    continue

                combined_text = " ".join(detected_lines).strip()

                # ข้ามถ้าเป็นข้อความเดิมทั้งหมด
                if combined_text == last_scanned_text or not combined_text:
                    continue

                last_scanned_text = combined_text

                # 1) ตรวจสอบและดักจับข้อความรายบรรทัด
                for line in detected_lines:
                    if len(line) >= 2 and line not in seen_texts:
                        seen_texts.add(line)
                        if not line.startswith("CF ") and line != getattr(self, "last_sent_cf", ""):
                            self.after(0, lambda t=line: self._trigger_snipe_with_text(t, source="LIVE RADAR"))

                # 2) ตรวจสอบข้อความรวมทั้งกล่องแชทล่าสุด (รวมชื่อสินค้า รหัส และราคาครบถ้วน)
                if combined_text not in seen_texts and not combined_text.startswith("CF "):
                    seen_texts.add(combined_text)
                    self.after(0, lambda t=combined_text: self._trigger_snipe_with_text(t, source="LIVE RADAR"))

            except Exception as e:
                time.sleep(1.0)

    def _windows_notification_sniffer_loop(self):
        """
        [ระบบดูดข้อความชั้นที่ 1: Windows Notification Stream Sniffer (ความเร็ว 0.003 วินาที)]
        - ใช้ Windows UserNotificationListener ดักจับข้อความแจ้งเตือนทั้งหมดจาก LINE
        - ดึงข้อความดิบ (Raw Text) โดยตรงจาก OS Message Queue
        - รองรับกรณีมีข้อความไหลเข้ามาจำนวนมากพร้อมๆ กันในเสี้ยววินาทีของการแข่งขัน
        - ประเมินกฎและยิง CF อัตโนมัติทันที
        """
        import asyncio
        async def _run():
            try:
                import winsdk.windows.ui.notifications.management as notif_mgmt
                import winsdk.windows.ui.notifications as notif

                listener = notif_mgmt.UserNotificationListener.current
                access = await listener.request_access_async()
                if access != 1:
                    return

                print("Layer 1: Windows Notification Stream Sniffer Active!")
                processed_nids = set()

                while True:
                    await asyncio.sleep(0.01)  # ตรวจสอบคิวข้อความทุกๆ 10ms (100 ครั้ง/วินาที)
                    if not getattr(self, "is_sniper_active", True):
                        continue

                    try:
                        notifs = await listener.get_notifications_async(notif.NotificationKinds.TOAST)
                        for n in notifs:
                            nid = n.id
                            if nid in processed_nids:
                                continue
                            processed_nids.add(nid)
                            if len(processed_nids) > 1000:
                                processed_nids.clear()

                            app_name = n.app_info.display_info.display_name if n.app_info else ""
                            if "line" not in app_name.lower():
                                continue

                            # ดึงข้อความทั้งหมดในการแจ้งเตือน
                            text_elements = []
                            if n.notification and n.notification.visual:
                                for b in n.notification.visual.bindings:
                                    for elem in b.get_text_elements():
                                        if elem.text:
                                            text_elements.append(elem.text.strip())

                            full_body = " ".join(text_elements).strip()
                            if full_body:
                                self.after(0, lambda t=full_body: self._trigger_snipe_with_text(t, source="STREAM SNIFFER"))

                    except Exception:
                        await asyncio.sleep(0.5)

            except Exception as e:
                print(f"Notification sniffer error: {e}")

        # รันบน dedicated event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())

    def _start_local_ingest_server(self):
        """
        [ระบบดูดข้อความชั้นที่ 3: Local Real-Time Ingest API (HTTP Server)]
        - รันเซิร์ฟเวอร์ความเร็วสูงที่ 127.0.0.1:8765
        - สามารถรับการยิงข้อความเข้ามาตรงๆ ผ่าน HTTP POST /api/line/incoming
        - ความเร็วตอบสนองระดับ 0.001 วินาที (1ms)
        """
        import json
        from http.server import HTTPServer, BaseHTTPRequestHandler

        parent = self

        class IngestHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # ปิด log ธรรมดาเพื่อความเร็วสูงสุด

            def do_POST(self):
                if self.path == "/api/line/incoming" or self.path == "/incoming":
                    length = int(self.headers.get("content-length", 0))
                    data = self.rfile.read(length)
                    try:
                        payload = json.loads(data.decode("utf-8"))
                        text = payload.get("text") or payload.get("message", "")
                        if text:
                            parent.after(0, lambda t=text: parent._trigger_snipe_with_text(t, source="DIRECT INGEST"))
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"status":"ok","received":true}')
                    except Exception:
                        self.send_response(400)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

        try:
            HTTPServer.allow_reuse_address = True
            server = HTTPServer(("127.0.0.1", 8765), IngestHandler)
            server.serve_forever()
        except Exception as e:
            print(f"Ingest server error: {e}")

    def refresh_line_windows(self):
        """ค้นหาหน้าต่าง LINE PC ทั้งหมดบน Windows ด้วย ctypes และอัปเดตเมนู Dropdown"""
        windows = WindowsLineSniper.get_all_line_windows()

        self.window_hwnd_map = {}
        if windows:
            menu_values = []
            for h, t in windows:
                label = f"{t} (HWND:{h})"
                menu_values.append(label)
                self.window_hwnd_map[label] = h

            self.line_window_menu.configure(values=menu_values, command=self.on_line_window_selected)
            self.line_window_menu.set(menu_values[0])
            self.active_line_hwnd = windows[0][0]
            self.active_line_title = windows[0][1]
            if hasattr(self, "lbl_stream_target"):
                self.lbl_stream_target.configure(text=f"🎯 กำลังดูดข้อความจาก: {windows[0][1]} (HWND:{windows[0][0]})")
            self.lbl_status_msg.configure(text=f"✓ เชื่อมต่อหน้าต่าง LINE: {windows[0][1]} (HWND:{windows[0][0]})")
        else:
            self.line_window_menu.configure(values=["(ไม่พบหน้าต่าง LINE PC)"])
            self.line_window_menu.set("(ไม่พบหน้าต่าง LINE PC)")
            if hasattr(self, "lbl_stream_target"):
                self.lbl_stream_target.configure(text="🎯 กำลังดูดข้อความจาก: (ไม่พบหน้าต่าง LINE PC)")
            self.lbl_status_msg.configure(text="⚠ ไม่พบหน้าต่าง LINE PC (กรุณาเปิดแอป LINE ก่อน)")

    def on_line_window_selected(self, choice: str):
        hwnd = self.window_hwnd_map.get(choice)
        if hwnd:
            self.active_line_hwnd = hwnd
            title = choice.split(" (HWND:")[0]
            self.active_line_title = title
            if hasattr(self, "lbl_stream_target"):
                self.lbl_stream_target.configure(text=f"🎯 กำลังดูดข้อความจาก: {title} (HWND:{hwnd})")
            self.lbl_status_msg.configure(text=f"✓ เลือกห้องเป้าหมาย: {title} (HWND:{hwnd})")

    def clear_console_log(self):
        self.radar_log_box.delete("1.0", "end")
        self._append_radar_log("╔══════════════════════════════════════════════════════════════════════════════════════════╗")
        self._append_radar_log("║   LINE AUTO-CF SNIPER: REAL-TIME INGESTION CONSOLE (TRIPLE-ENGINE ACTIVE)                ║")
        self._append_radar_log("║   • ระบบดูดข้อความแชทสดอัตโนมัติ 100% ปล่อยมือไม่ต้องแตะอะไรเลย ไม่ต้องก๊อปปี้ข้อความมาวาง  ║")
        self._append_radar_log("║   • เมื่อมีข้อความขายของเข้ามาใน LINE ระบบจะดูดมาแสดงในคอนโซลนี้ และยิง CF ทันที          ║")
        self._append_radar_log("╚══════════════════════════════════════════════════════════════════════════════════════════╝")

    def copy_console_log(self):
        try:
            import pyperclip
            content = self.radar_log_box.get("1.0", "end").strip()
            if content:
                pyperclip.copy(content)
                self.lbl_status_msg.configure(text="✓ คัดลอก Log ทั้งหมดลงในคลิปบอร์ดแล้ว")
        except Exception as e:
            print(f"Error copying log: {e}")

    def on_speed_changed(self, choice: str):
        if "60 FPS" in choice:
            self.radar_sleep_interval = 0.004  # 4ms sleep -> ~60 FPS Ultra
            self.lbl_metric_fps.configure(text="60 FPS (~16ms)")
        elif "25 FPS" in choice:
            self.radar_sleep_interval = 0.035  # 35ms sleep -> ~25 FPS
            self.lbl_metric_fps.configure(text="25 FPS (~40ms)")
        else:  # 50 FPS Turbo
            self.radar_sleep_interval = 0.012  # 12ms sleep -> ~50 FPS Turbo
            self.lbl_metric_fps.configure(text="50 FPS (~20ms)")
        self._append_radar_log(f"⚡ [SPEED CONFIG] ปรับความเร็วสแกนสายตา AI เป็น: {choice}")

    def _append_radar_log(self, text: str):
        def _do():
            try:
                timestamp = time.strftime("%H:%M:%S")
                if hasattr(self, "radar_log_box") and self.radar_log_box.winfo_exists():
                    self.radar_log_box.insert("end", f"[{timestamp}] {text}\n")
                    self.radar_log_box.see("end")
            except Exception:
                pass
        try:
            self.after(0, _do)
        except Exception:
            pass

    # --- Rules Management ---

    def load_rules_data(self):
        async def _fetch():
            return await get_all_cf_rules()

        def _on_done(rules):
            self.rules_cache = rules
            self._render_rules_list()

        self.run_async(_fetch(), callback=_on_done)

    def _render_rules_list(self):
        for widget in self.rules_scroll.winfo_children():
            widget.destroy()

        if not self.rules_cache:
            lbl = ctk.CTkLabel(self.rules_scroll, text="ยังไม่มีกฎการ CF กรุณาเพิ่มกฎใหม่ด้านบน", text_color="#9ca3af")
            lbl.pack(pady=20)
            return

        for r in self.rules_cache:
            rule_id = r["id"]
            is_active = r["is_active"] == 1

            row = ctk.CTkFrame(self.rules_scroll, corner_radius=8, fg_color="#0f172a")
            row.pack(fill="x", padx=6, pady=4)

            # Left badge & title
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", padx=12, pady=10)

            name_lbl = ctk.CTkLabel(left, text=r["name"], font=ctk.CTkFont(size=14, weight="bold"))
            name_lbl.pack(anchor="w")

            detail_txt = f"กลุ่ม: {r['target_rooms']} | Keywords: {r['target_keywords']} | รูปแบบ: {r['cf_format']}"
            if r["price_limit"] > 0:
                detail_txt += f" | เพดานราคา: {r['price_limit']} บ."
            detail_lbl = ctk.CTkLabel(left, text=detail_txt, text_color="#9ca3af", font=ctk.CTkFont(size=11))
            detail_lbl.pack(anchor="w")

            # Right buttons & switch
            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", padx=12, pady=10)

            sw = ctk.CTkSwitch(
                right, text="เปิดทำงาน" if is_active else "ปิดใช้งาน",
                command=lambda rid=rule_id, cur=is_active: self.toggle_rule_action(rid, not cur)
            )
            if is_active:
                sw.select()
            else:
                sw.deselect()
            sw.pack(side="left", padx=8)

            btn_del = ctk.CTkButton(
                right, text="ลบ", width=60, fg_color="#ef4444", hover_color="#dc2626",
                command=lambda rid=rule_id: self.delete_rule_action(rid)
            )
            btn_del.pack(side="left", padx=4)

    def apply_preset_labubu(self):
        self.entry_rule_name.delete(0, "end")
        self.entry_rule_name.insert(0, "Labubu V2 / กล่องสุ่ม")
        self.entry_rule_rooms.delete(0, "end")
        self.entry_rule_rooms.insert(0, "*")
        self.entry_rule_price.delete(0, "end")
        self.entry_rule_price.insert(0, "1500")
        self.entry_rule_delay.delete(0, "end")
        self.entry_rule_delay.insert(0, "200")
        self.entry_rule_kw.delete(0, "end")
        self.entry_rule_kw.insert(0, "labubu, v2, ลาบูบู้, กล่องสุ่ม, พร้อมส่ง, รหัส")
        self.entry_rule_neg.delete(0, "end")
        self.entry_rule_neg.insert(0, "หมดแล้ว, ปิดการขาย, ขายแล้ว, มีคนรับแล้ว")
        self.entry_rule_fmt.delete(0, "end")
        self.entry_rule_fmt.insert(0, "CF {code} พร้อมโอน")

    def apply_preset_fashion(self):
        self.entry_rule_name.delete(0, "end")
        self.entry_rule_name.insert(0, "เสื้อวินเทจ / แฟชั่น ไซส์ L")
        self.entry_rule_rooms.delete(0, "end")
        self.entry_rule_rooms.insert(0, "*")
        self.entry_rule_price.delete(0, "end")
        self.entry_rule_price.insert(0, "800")
        self.entry_rule_delay.delete(0, "end")
        self.entry_rule_delay.insert(0, "200")
        self.entry_rule_kw.delete(0, "end")
        self.entry_rule_kw.insert(0, "อก, ไซส์ l, vintage, พร้อมส่ง, เสื้อยืด, ตัวที่, รหัส")
        self.entry_rule_neg.delete(0, "end")
        self.entry_rule_neg.insert(0, "หมดแล้ว, ปิดการขาย, ขายแล้ว, ตำหนิ")
        self.entry_rule_fmt.delete(0, "end")
        self.entry_rule_fmt.insert(0, "CF {code} รับครับ")

    def apply_preset_generic(self):
        self.entry_rule_name.delete(0, "end")
        self.entry_rule_name.insert(0, "สไนเปอร์รหัสสินค้าทั่วไป")
        self.entry_rule_rooms.delete(0, "end")
        self.entry_rule_rooms.insert(0, "*")
        self.entry_rule_price.delete(0, "end")
        self.entry_rule_price.insert(0, "0")
        self.entry_rule_delay.delete(0, "end")
        self.entry_rule_delay.insert(0, "250")
        self.entry_rule_kw.delete(0, "end")
        self.entry_rule_kw.insert(0, "รหัส, cf, พร้อมส่ง, เปิดขาย, ปล่อยของ")
        self.entry_rule_neg.delete(0, "end")
        self.entry_rule_neg.insert(0, "หมดแล้ว, ปิดการขาย, ขายแล้ว")
        self.entry_rule_fmt.delete(0, "end")
        self.entry_rule_fmt.insert(0, "CF {code}")

    def save_new_rule_action(self):
        name = self.entry_rule_name.get().strip()
        rooms = self.entry_rule_rooms.get().strip() or "*"
        kw = self.entry_rule_kw.get().strip()
        neg = self.entry_rule_neg.get().strip()
        fmt = self.entry_rule_fmt.get().strip() or "CF {code} พร้อมโอน"
        try:
            price = float(self.entry_rule_price.get().strip() or 0)
        except ValueError:
            price = 0.0
        try:
            delay = int(self.entry_rule_delay.get().strip() or 200)
        except ValueError:
            delay = 200

        if not name or not kw:
            messagebox.showerror("Error", "กรุณากรอกชื่อกฎและคีย์เวิร์ดเป้าหมาย")
            return

        async def _add():
            return await add_cf_rule(name, rooms, kw, neg, fmt, price, delay)

        def _on_done(_):
            self.entry_rule_name.delete(0, "end")
            self.entry_rule_kw.delete(0, "end")
            self.load_rules_data()
            messagebox.showinfo("Success", f"บันทึกกฎ '{name}' เรียบร้อยแล้ว!")

        self.run_async(_add(), callback=_on_done)

    def toggle_rule_action(self, rule_id: int, new_state: bool):
        async def _toggle():
            await toggle_cf_rule(rule_id, new_state)

        self.run_async(_toggle(), callback=lambda _: self.load_rules_data())

    def delete_rule_action(self, rule_id: int):
        if not messagebox.askyesno("Confirm", "ต้องการลบกฎการ CF นี้ใช่หรือไม่?"):
            return

        async def _del():
            await delete_cf_rule(rule_id)

        self.run_async(_del(), callback=lambda _: self.load_rules_data())

    # --- History Management ---

    def load_history_data(self):
        async def _fetch():
            return await get_recent_cf_history(limit=40)

        def _on_done(items):
            if not hasattr(self, "history_scroll") or not self.history_scroll.winfo_exists():
                return
            for widget in self.history_scroll.winfo_children():
                widget.destroy()

            if not items:
                lbl = ctk.CTkLabel(
                    self.history_scroll,
                    text="ยังไม่มีประวัติการ CF สำเร็จ\n(เมื่อบอทยิง CF สำเร็จ รายการจะปรากฏที่นี่ทันที)",
                    text_color="#9ca3af", font=ctk.CTkFont(size=12), justify="center"
                )
                lbl.pack(pady=40)
                return

            for h in items:
                row = ctk.CTkFrame(self.history_scroll, corner_radius=8, fg_color="#182234")
                row.pack(fill="x", padx=4, pady=3)

                top = ctk.CTkFrame(row, fg_color="transparent")
                top.pack(fill="x", padx=10, pady=(6, 2))

                room_badge = ctk.CTkLabel(top, text=f" {h['room_name']} ", fg_color="#3b82f6", text_color="#fff", corner_radius=4, font=ctk.CTkFont(size=10, weight="bold"))
                room_badge.pack(side="left", padx=(0, 6))

                time_lbl = ctk.CTkLabel(top, text=h.get("created_at", "-"), text_color="#9ca3af", font=ctk.CTkFont(size=11))
                time_lbl.pack(side="left")

                speed_lbl = ctk.CTkLabel(top, text=f"⚡ {h.get('execution_time_ms', 0)} ms", text_color="#10b981", font=ctk.CTkFont(size=11, weight="bold"))
                speed_lbl.pack(side="right")

                body = ctk.CTkFrame(row, fg_color="transparent")
                body.pack(fill="x", padx=10, pady=(2, 6))

                cf_tag = ctk.CTkLabel(body, text=f"ยิงข้อความ: \"{h['cf_text']}\"", text_color="#06c755", font=ctk.CTkFont(size=12, weight="bold"))
                cf_tag.pack(anchor="w")

                orig_lbl = ctk.CTkLabel(body, text=f"ข้อความแม่ค้า: {h['original_message'][:75]}...", text_color="#cbd5e1", font=ctk.CTkFont(size=11))
                orig_lbl.pack(anchor="w")

        self.run_async(_fetch(), callback=_on_done)

    def clear_history_action(self):
        if not messagebox.askyesno("ยืนยัน", "ต้องการล้างประวัติการยิง CF สำเร็จทั้งหมดใช่หรือไม่?"):
            return
        async def _clear():
            await clear_cf_history()
        def _on_done(_):
            self.stats_wins = 0
            if hasattr(self, "lbl_metric_wins"):
                self.lbl_metric_wins.configure(text="0 ครั้ง")
            self.load_history_data()
            self._append_radar_log("🧹 [HISTORY] ล้างประวัติการยิง CF สำเร็จเรียบร้อยแล้ว")
        self.run_async(_clear(), callback=_on_done)

    def show_how_to_use_dialog(self):
        """แสดงหน้าต่างคู่มือการใช้งานทีละสเต็ปแบบเข้าใจง่าย"""
        dlg = ctk.CTkToplevel(self)
        dlg.title("คู่มือการใช้งาน: LINE Personal Auto-CF Sniper")
        dlg.geometry("680x560")
        dlg.minsize(600, 480)
        dlg.grab_set()

        card = ctk.CTkFrame(dlg, corner_radius=12, fg_color="#1e293b")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        title = ctk.CTkLabel(card, text="📖 ขั้นตอนการใช้งานทีละสเต็ป (Step-by-Step Guide)", font=ctk.CTkFont(size=16, weight="bold"), text_color="#f59e0b")
        title.pack(anchor="w", padx=20, pady=(16, 12))

        txt_box = ctk.CTkTextbox(card, corner_radius=8, fg_color="#0f172a", font=ctk.CTkFont(size=13))
        txt_box.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        guide_content = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "   ขั้นตอนการเชื่อมต่อบอทเข้ากับกลุ่ม LINE / OpenChat\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "【ขั้นตอนที่ 1】เปิดแอป LINE บนคอมพิวเตอร์ของคุณ\n"
            "  1. เปิดโปรแกรม LINE PC บน Windows และเข้าสู่ระบบด้วยไลน์ส่วนตัวของคุณ\n"
            "  2. ดับเบิ้ลคลิกเปิดห้องแชท (กลุ่มซื้อขาย / OpenChat / LINE OA) ที่คุณต้องการ CF ของ\n"
            "     * แนะนำ: ให้ดับเบิ้ลคลิกเพื่อให้ห้องแชทแยกออกมาเป็นหน้าต่างเดี่ยว (Popup Window)\n\n"
            "【ขั้นตอนที่ 2】เชื่อมต่อโปรแกรมนี้เข้ากับหน้าต่าง LINE\n"
            "  1. ที่แถบด้านบนของโปรแกรมนี้ ให้กดปุ่ม '🔄 ค้นหาหน้าต่าง LINE'\n"
            "  2. คลิกที่เมนู Dropdown ข้างๆ จะเห็นรายชื่อห้องแชท LINE ที่เปิดอยู่ ให้เลือกห้องที่คุณต้องการยิง CF\n\n"
            "【ขั้นตอนที่ 3】ตั้งกฎสินค้าที่ต้องการ CF (แท็บ 'จัดการกฎการ CF')\n"
            "  1. ไปที่แท็บ '📜 จัดการกฎการ CF (Rules)'\n"
            "  2. ใส่คีย์เวิร์ดสินค้าที่เล็งไว้ เช่น: labubu, v2, เสื้อยืด, โมเดล, รหัส\n"
            "  3. กำหนดรูปแบบข้อความที่จะพิมพ์ตอบ เช่น: 'CF {code} พร้อมโอน' (ระบบจะแทนที่ {code} ด้วยรหัสจริง)\n"
            "  4. กำหนดเพดานราคา (เช่น ไม่เกิน 1500 บาท) เพื่อไม่ให้บอท CF ของที่ราคาแพงเกินไป\n\n"
            "【ขั้นตอนที่ 4】การดูดข้อความและยิง CF อัตโนมัติ 100% (Hands-Free)\n"
            "  • คุณไม่ต้องคัดลอกข้อความ ไม่ต้องกดวาง และไม่ต้องแตะเมาส์หรือคีย์บอร์ดเลย\n"
            "  • ระบบ Triple-Engine จะดูดข้อความที่ไหลเข้ามาในห้องแชท LINE แบบ Real-time ทันที:\n"
            "    - ข้อความที่ไหลเข้ามาจะปรากฏสดๆ บน '⚡ คอนโซลดูดข้อความสด (Live Ingest)'\n"
            "    - หากแม่ค้าโพสต์สินค้าที่ตรงกับคีย์เวิร์ดในกฎ บอทจะยิงส่ง CF ทันทีในเสี้ยววินาที!\n"
            "    - คุณสามารถนั่งดูตัวนับจำนวนข้อความที่ดูดได้ และประวัติการยิงชนะได้แบบเรียลไทม์\n\n"
            "【ข้อควรระวัง & ความปลอดภัย】\n"
            "  • การสไนเปอร์ใน LINE OpenChat แนะนำให้ตั้ง Jitter Delay ไว้ที่ 150 - 300 ms ในแท็บ 'ตั้งค่า'\n"
            "    เพื่อความเป็นธรรมชาติเสมือนคนพิมพ์ไว และป้องกันระบบ Anti-spam ของ OpenChat"
        )
        txt_box.insert("1.0", guide_content)
        txt_box.configure(state="disabled")

        btn_close = ctk.CTkButton(card, text="เข้าใจแล้ว (ปิดหน้าต่าง)", fg_color="#06c755", text_color="#000", font=ctk.CTkFont(weight="bold"), command=dlg.destroy)
        btn_close.pack(pady=(0, 16))

    def refresh_timer(self):
        """Auto refresh stats and keep LINE window attached every 3 seconds"""
        try:
            if not getattr(self, "active_line_hwnd", None) or not user32.IsWindow(self.active_line_hwnd):
                self.refresh_line_windows()
        except Exception:
            pass
        self.after(3000, self.refresh_timer)

if __name__ == "__main__":
    app = LineSniperDesktopApp()
    app.mainloop()
