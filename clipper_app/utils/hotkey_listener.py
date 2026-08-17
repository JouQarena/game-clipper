"""
Hotkey Listener - Global hotkey registration for Windows.

Uses RegisterHotKey API (via pywin32) to listen for hotkeys
even when the application is not in focus.
"""

import threading
from typing import Callable, Dict, Optional

try:
    import win32con
    import win32gui
    import win32api
    import win32ui
    from win32con import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

    # Mock constants for development
    class MOD_ALT: pass
    class MOD_CONTROL: pass
    class MOD_SHIFT: pass
    class MOD_WIN: pass


# Virtual key codes for common keys
VK_CODES = {
    # Function keys
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    # Numbers
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    # Letters
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
    "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
    "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
    "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59,
    "Z": 0x5A,
    # Special keys
    "SPACE": 0x20, "ENTER": 0x0D, "ESC": 0x1B, "TAB": 0x09,
    "BACK": 0x08, "DELETE": 0x2E, "INSERT": 0x2D,
    "HOME": 0x24, "END": 0x23, "PGUP": 0x21, "PGDN": 0x22,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    # Modifiers
    "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10, "WIN": 0x5B,
}


class HotkeyListener:
    """
    Global hotkey listener using Windows RegisterHotKey API.

    Listens for hotkeys even when the application is in the background.
    """

    # We need unique IDs for each hotkey registration
    _next_id = 1000

    def __init__(self):
        self._callbacks: Dict[int, Callable] = {}
        self._key_names: Dict[int, str] = {}
        self._running = False
        self._thread = None
        self._hwnd = None
        self._hotkey_map = {}  # (modifiers, vk) -> callback_id

    def register_hotkey(self, hotkey_str: str, callback: Callable) -> bool:
        """
        Register a hotkey combination.

        Format: "F8" or "CTRL+F8" or "CTRL+SHIFT+F8"
        Modifiers: CTRL, ALT, SHIFT, WIN (optional)
        """
        if not HAS_WIN32:
            print(f"[Hotkey] win32 not available. Can't register hotkey: {hotkey_str}")
            return False

        parts = hotkey_str.upper().split("+")
        key_name = parts[-1]
        modifiers = parts[:-1]

        # Convert modifiers to Windows modifier flags
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

        # Get virtual key code
        vk = VK_CODES.get(key_name)
        if vk is None:
            print(f"[Hotkey] Unknown key: {key_name}")
            return False

        callback_id = self._next_id
        self._next_id += 2  # Increment by 2 (odd numbers sometimes reserved)

        try:
            if not self._hwnd:
                return False

            success = win32api.RegisterHotKey(self._hwnd, callback_id, mod_flags, vk)
            if success:
                self._callbacks[callback_id] = callback
                self._key_names[callback_id] = hotkey_str
                self._hotkey_map[(mod_flags, vk)] = callback_id
                print(f"[Hotkey] Registered: {hotkey_str} (id={callback_id})")
                return True
            else:
                print(f"[Hotkey] Failed to register: {hotkey_str}")
                return False
        except Exception as e:
            print(f"[Hotkey] Error registering {hotkey_str}: {e}")
            return False

    def unregister_hotkey(self, hotkey_str: str):
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

        callback_id = self._hotkey_map.pop((mod_flags, vk), None)
        if callback_id:
            try:
                win32api.UnregisterHotKey(self._hwnd, callback_id)
                self._callbacks.pop(callback_id, None)
                self._key_names.pop(callback_id, None)
                print(f"[Hotkey] Unregistered: {hotkey_str}")
            except Exception:
                pass

    def start(self):
        """Start the hotkey listener."""
        if not HAS_WIN32:
            print("[Hotkey] win32 not available.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._thread.start()
        print("[Hotkey] Listener started")

    def stop(self):
        """Stop the hotkey listener."""
        self._running = False
        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None
        if self._thread:
            self._thread.join(timeout=2)
        self._callbacks.clear()
        self._hotkey_map.clear()
        print("[Hotkey] Listener stopped")

    def _create_message_window(self):
        """Create a hidden window to receive hotkey messages."""
        if not HAS_WIN32:
            return

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._window_proc
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "GameClipperHotkeyWindow"

        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass

        self._hwnd = win32gui.CreateWindow(
            "GameClipperHotkeyWindow",
            "GameClipper Hotkey Listener",
            0, 0, 0, 0, 0,
            0, 0, wc.hInstance, None
        )

    def _window_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure for hotkey messages."""
        if msg == win32con.WM_HOTKEY:
            callback_id = wparam
            callback = self._callbacks.get(callback_id)
            if callback:
                try:
                    callback()
                except Exception as e:
                    print(f"[Hotkey] Callback error: {e}")
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _listener_loop(self):
        """Main message loop for hotkey processing."""
        self._create_message_window()
        if not self._hwnd:
            self._running = False
            return

        while self._running:
            try:
                win32gui.PumpWaitingMessages()
                time.sleep(0.01)
            except Exception as e:
                print(f"[Hotkey] Loop error: {e}")
                time.sleep(0.1)
