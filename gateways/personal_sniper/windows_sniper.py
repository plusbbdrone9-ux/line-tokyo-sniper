"""
Windows LINE PC Auto-CF Sniper Client
-------------------------------------
สคริปต์สไนเปอร์ความเร็วสูงสำหรับ LINE บน Windows
ค้นหาหน้าต่าง LINE PC และส่งคำสั่ง CF เข้าช่องพิมพ์ข้อความโดยอัตโนมัติ
"""

import time
import ctypes
from ctypes import wintypes
import pyperclip
import logging
import asyncio
from typing import Optional, List, Tuple
from database.db import log_cf_action

logger = logging.getLogger("WindowsCFSniper")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

class WindowsLineSniper:
    @classmethod
    def get_all_line_windows(cls) -> List[Tuple[int, str]]:
        """
        ค้นหาหน้าต่าง LINE PC ทั้งหมดที่กำลังเปิดอยู่บน Windows ด้วย ctypes
        (แก้ปัญหา pywin32 Error 122 และรองรับชื่อภาษาไทย/Emoji 100%)
        """
        windows = []
        desk = user32.OpenDesktopW('Default', 0, False, 0x01FF)

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()

                    cls_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cls_buff, 256)
                    cls_name = cls_buff.value

                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                    # ตรวจสอบว่าเป็นหน้าต่างของ LINE หรือมีคำว่า LINE/Chat
                    # หรือหน้าต่างแชททั่วไปของ LINE (มักไม่มีคำว่า LINE ใน Title แต่เป็นชื่อกลุ่ม/คน)
                    is_line = False
                    if "line" in title.lower() or "line" in cls_name.lower() or "chat" in cls_name.lower():
                        is_line = True
                    else:
                        # ตรวจสอบ Process Name ผ่าน psutil
                        try:
                            import psutil
                            pname = psutil.Process(pid.value).name().lower()
                            if "line" in pname:
                                is_line = True
                        except Exception:
                            pass

                    # กรองหน้าต่างที่ไม่เกี่ยวข้อง และไม่รวมหน้าต่างของตัวสไนเปอร์เอง
                    ex_list = ["antigravity", "visual studio", "python", "cmd", "sniper", "auto-cf", "terminal"]
                    if is_line and not any(ex in title.lower() for ex in ex_list):
                        windows.append((hwnd, title))
            return 1

        try:
            if desk:
                user32.EnumDesktopWindows(desk, WNDENUMPROC(enum_cb), 0)
            else:
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception as e:
            logger.error(f"Error enumerating windows: {e}")

        # จัดลำดับ: ให้หน้าต่างแชท (ที่ไม่ใช่หน้าต่างหลัก 'LINE') อยู่ด้านบนสุด
        windows.sort(key=lambda item: 1 if item[1] == "LINE" else 0)
        return windows

    @classmethod
    def find_chat_window(cls, room_title_keyword: Optional[str] = None) -> Optional[int]:
        """ค้นหา HWND ของหน้าต่างแชท LINE ที่ระบุ"""
        all_wins = cls.get_all_line_windows()
        if not all_wins:
            return None

        if room_title_keyword and room_title_keyword != "*":
            kw = room_title_keyword.lower().strip()
            for hwnd, title in all_wins:
                if kw in title.lower():
                    return hwnd

        # คืนค่าหน้าต่างแชทแรกที่ไม่ใช่หน้าต่างหลัก
        return all_wins[0][0]

    @classmethod
    async def execute_cf(
        cls,
        cf_message: str,
        target_hwnd: Optional[int] = None,
        room_name: str = "LINE Group/OpenChat",
        sender_name: str = "แม่ค้า",
        original_message: str = "",
        rule_id: Optional[int] = None,
        rule_name: str = "Auto Rule",
        delay_ms: int = 200
    ) -> bool:
        """
        สลับหน้าจอไปที่หน้าต่าง LINE PC, คลิกที่ช่องพิมพ์ข้อความ, วางข้อความ CF และกด Enter
        """
        start_time = time.time()

        # 1. หาหน้าต่างเป้าหมาย
        hwnd = target_hwnd
        if not hwnd or not user32.IsWindow(hwnd):
            hwnd = cls.find_chat_window(room_name)

        if not hwnd:
            logger.error("No target LINE chat window found to send CF!")
            return False

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        try:
            # 2. นำหน้าต่างแชทขึ้นมาด้านหน้า (Force Foreground Focus)
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.BringWindowToTop(hwnd)

            fore_hwnd = user32.GetForegroundWindow()
            fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
            cur_thread = kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)

            user32.AttachThreadInput(cur_thread, fore_thread, True)
            user32.AttachThreadInput(cur_thread, target_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
            user32.AttachThreadInput(cur_thread, target_thread, False)
            user32.AttachThreadInput(cur_thread, fore_thread, False)

            # 3. คำนวณพิกัดและคลิกที่ช่องพิมพ์ข้อความด้านล่าง (Click into 'Enter a message')
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            click_x = rect.left + int(w * 0.35)
            click_y = rect.bottom - 45  # ช่องพิมพ์ข้อความอยู่สูงจากขอบล่างประมาณ 40-50 px

            user32.SetCursorPos(click_x, click_y)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            user32.mouse_event(0x0004, 0, 0, 0, 0)

            # 4. วางข้อความภาษาไทยผ่าน Clipboard (Ctrl + V)
            pyperclip.copy(cf_message)

            # VK_CONTROL = 0x11, 'V' = 0x56, VK_RETURN = 0x0D
            user32.keybd_event(0x11, 0, 0, 0)
            user32.keybd_event(0x56, 0, 0, 0)
            user32.keybd_event(0x56, 0, 2, 0)
            user32.keybd_event(0x11, 0, 2, 0)

            # 5. กด Enter เพื่อส่งข้อความ
            user32.keybd_event(0x0D, 0, 0, 0)
            user32.keybd_event(0x0D, 0, 2, 0)

            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(f"⚡ [SNIPER WIN] Sent '{cf_message}' to LINE window (HWND:{hwnd}) in {duration_ms}ms!")

            # 6. บันทึกลงฐานข้อมูล
            await log_cf_action(
                rule_id=rule_id,
                rule_name=rule_name,
                room_name=room_name,
                sender_name=sender_name,
                original_message=original_message,
                cf_text=cf_message,
                status="SUCCESS",
                execution_time_ms=duration_ms
            )
            return True

        except Exception as e:
            logger.error(f"Error executing sniper on Windows: {e}")
            duration_ms = round((time.time() - start_time) * 1000, 2)
            await log_cf_action(
                rule_id=rule_id,
                rule_name=rule_name,
                room_name=room_name,
                sender_name=sender_name,
                original_message=original_message,
                cf_text=cf_message,
                status=f"FAILED: {e}",
                execution_time_ms=duration_ms
            )
            return False
