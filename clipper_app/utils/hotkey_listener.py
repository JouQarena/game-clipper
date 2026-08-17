"""
Hotkey Listener - Global hotkey registration for Windows.

Uses RegisterHotKey API (via pywin32) to listen for hotkeys
even when the application is not in focus.

This version is hardened for PyInstaller --windowed exe use.
"""

import threading
import time
from typing import Callable, Dict, Optional

try:
    import win32con
    import win32gui
    import win32api
    from win32con import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


VK_CODES = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
    "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
    "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
    "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59,
    "Z": 0x5A,
    "SPACE": 0x20, "ENTER": 0x0D, "ESC": 0x1B, "TAB": 0x09,
    "BACK": 0x08, "DELETE": 0x2E, "INSERT": 0x2D,
    "HOME": 0x24, "END": 0x23, "PGUP": 0x21, "PGDN": 0x22,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
}


class HotkeyListener:
    """
    Listens for global hotkeys using Windows RegisterHotKey API.

    The hotkey message window is created on the main thread (in start())
    so message dispatch works reliably. The listener only calls
    PumpWaitingMessages in its worker thread.
    """

    _next_id = 1000

    def __init__(self):
        self._callbacks: Dict[int, Callable] = {}
        self._key_names: Dict[int, str] = {}
        self._running = False
        self._thread = None
        self._hwnd = None
        self._hotkey_map = {}

    def register_hotkey(self, hotkey_str, callback) -> bool:
        """Register a hotkey combination like 'F8' or 'CTRL+SHIFT+F8'."""
        if not HAS_WIN32:
            return False
        if not self._hwnd:
            return False

        parts = hotkey_str.upper().split("+")
        key_name = parts[-1]
        modifiers = parts[:-1]

        mod_flags = 0
        for mod in modifiers:
            if mod == "CTRL":
                mod_flags |= win32con.MOD_CONTROL
            elif mod == "ALT":
                mod_flags |= win32con.MOD_ALT
            elif mod == "SHIFT":
                mod_flags |= win32con.MOD_SHIFT
            elif mod == "WIN":
                mod_flags |= win32con.MOD_WIN

        vk = VK_CODES.get(key_name)
        if vk is None:
            return False

        callback_id = self._next_id
        self._next_id += 2

        try:
            success = win32api.RegisterHotKey(self._hwnd, callback_id, mod_flags, vk)
            if success:
                self._callbacks[callback_id] = callback
                self._key_names[callback_id] = hotkey_str
                self._hotkey_map[(mod_flags, vk)] = callback_id
                return True
        except Exception:
            pass
        return False

    def unregister_hotkey(self, hotkey_str):
        """Unregister a previously registered hotkey."""
        parts = hotkey_str.upper().split("+")
        key_name = parts[-1]
        modifiers = parts[:-1]
        mod_flags = 0
        for mod in modifiers:
            if mod == "CTRL":
                mod_flags |= win32con.MOD_CONTROL
            elif mod == "ALT":
                mod_flags |= win32con.MOD_ALT
            elif mod == "SHIFT":
                mod_flags |= win32con.MOD_SHIFT
            elif mod == "WIN":
                mod_flags |= win32con.MOD_WIN
        vk = VK_CODES.get(key_name)
        if vk is None or not self._hwnd:
            return
        cid = self._hotkey_map.pop((mod_flags, vk), None)
        if cid:
            try:
                win32api.UnregisterHotKey(self._hwnd, cid)
                self._callbacks.pop(cid, None)
                self._key_names.pop(cid, None)
            except Exception:
                pass

    def start(self):
        """Create the message window (must be called from main thread)
        and start the listener loop in a worker thread."""
        if not HAS_WIN32:
            return
        if self._running:
            return
        # Create window on the CALLING thread (main thread) for safety
        self._create_message_window()
        if not self._hwnd:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._listener_loop, daemon=True, name="HotkeyListener"
        )
        self._thread.start()

    def stop(self):
        """Stop the listener and clean up."""
        self._running = False
        if self._hwnd:
            try:
                # Unregister all
                for cid in list(self._callbacks.keys()):
                    try:
                        win32api.UnregisterHotKey(self._hwnd, cid)
                    except Exception:
                        pass
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None
        if self._thread:
            self._thread.join(timeout=2)
        self._callbacks.clear()
        self._hotkey_map.clear()

    def _create_message_window(self):
        """Create a hidden message-only window to receive WM_HOTKEY."""
        try:
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = self._window_proc
            wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpszClassName = "GameClipperHotkeyWindow"
            try:
                win32gui.RegisterClass(wc)
            except Exception:
                pass
            self._hwnd = win32gui.CreateWindow(
                "GameClipperHotkeyWindow", "GameClipperHotkey",
                0, 0, 0, 0, 0,
                0, 0, wc.hInstance, None
            )
        except Exception:
            self._hwnd = None

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_HOTKEY:
            callback_id = wparam
            callback = self._callbacks.get(callback_id)
            if callback:
                try:
                    callback()
                except Exception:
                    pass
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _listener_loop(self):
        """Pump messages in this thread."""
        while self._running:
            try:
                win32gui.PumpWaitingMessages()
                time.sleep(0.02)
            except Exception:
                time.sleep(0.1)
