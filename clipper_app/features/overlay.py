"""
Overlay - Simple recording status overlay displayed on screen.

Uses a transparent always-on-top window to show:
- Recording status (red dot when capturing)
- Buffer fill level
- Hotkey hint
- FPS counter

Since Tkinter doesn't easily support transparent overlays on games,
we use win32 API for a lightweight overlay window.
"""

import threading
import time
from typing import Optional

try:
    import win32gui
    import win32api
    import win32con
    import win32ui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class Overlay:
    """
    Lightweight overlay window showing recording status.
    Uses a layered window (WS_EX_LAYERED) for transparency.
    """

    def __init__(self):
        self._visible = False
        self._hwnd = None
        self._text = ""
        self._color = (255, 0, 0)  # Red
        self._running = False
        self._thread = None

        # Overlay position (top-right corner)
        self._x = 0
        self._y = 0
        self._width = 250
        self._height = 80

    def show(self):
        """Show the overlay."""
        if not HAS_WIN32:
            print("[Overlay] win32 not available. Overlay disabled.")
            return
        if self._visible:
            return
        self._visible = True
        self._running = True
        self._thread = threading.Thread(target=self._overlay_loop, daemon=True)
        self._thread.start()
        print("[Overlay] Shown")

    def hide(self):
        """Hide the overlay."""
        self._visible = False
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None
        print("[Overlay] Hidden")

    def _create_overlay_window(self):
        """Create a transparent layered window for the overlay."""
        if not HAS_WIN32:
            return

        # Register window class
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._window_proc
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "GameClipperOverlay"
        wc.hbrBackground = win32gui.GetStockObject(win32con.NULL_BRUSH)

        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception:
            # Class already registered
            pass

        # Create layered window
        self._hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST,
            "GameClipperOverlay",
            "GameClipper",
            win32con.WS_POPUP,
            win32api.GetSystemMetrics(0) - self._width - 20,
            20,
            self._width,
            self._height,
            0, 0, 0, None
        )

        if self._hwnd:
            # Set transparency (0 = fully transparent, 255 = opaque)
            # We'll use a semi-transparent background
            win32gui.SetLayeredWindowAttributes(
                self._hwnd,
                0x000000,  # Color key (black)
                180,  # Alpha (0-255)
                win32con.LWA_ALPHA
            )
            win32gui.ShowWindow(self._hwnd, win32con.SW_SHOW)

    def _window_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure for the overlay window."""
        if msg == win32con.WM_PAINT:
            self._on_paint(hwnd)
            return 0
        if msg == win32con.WM_DESTROY:
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _on_paint(self, hwnd):
        """Paint the overlay content."""
        try:
            dc, paint_struct = win32gui.BeginPaint(hwnd)
            # We'll use a simpler approach - just invalidate
            win32gui.EndPaint(hwnd, paint_struct)
        except Exception:
            pass

    def _overlay_loop(self):
        """Main overlay update loop."""
        self._create_overlay_window()
        if not self._hwnd:
            self._running = False
            return

        while self._running and self._visible:
            try:
                self._update_overlay()
                time.sleep(0.5)  # Update every 500ms
            except Exception as e:
                print(f"[Overlay] Error: {e}")
                time.sleep(1)

    def _update_overlay(self):
        """Update the overlay display."""
        if not self._hwnd:
            return

        try:
            # Use a simple approach: paint text on the window
            dc = win32gui.GetDC(self._hwnd)
            if dc:
                rect = win32gui.GetClientRect(self._hwnd)
                # Draw background
                win32gui.FillRect(dc, rect, win32gui.GetStockObject(win32con.BLACK_BRUSH))
                # Draw text
                win32gui.SetTextColor(dc, win32api.RGB(*self._color))
                win32gui.SetBkMode(dc, win32con.TRANSPARENT)
                win32gui.DrawText(
                    dc, self._text,
                    -1,
                    rect,
                    win32con.DT_CENTER | win32con.DT_VCENTER | win32con.DT_SINGLELINE
                )
                win32gui.ReleaseDC(self._hwnd, dc)
        except Exception:
            pass

    def update_status(self, is_recording: bool, fps: float = 0,
                      buffer_fill: float = 0.0, game_name: str = ""):
        """Update the overlay text."""
        status = "● REC" if is_recording else "○ IDLE"
        if is_recording:
            self._color = (255, 0, 0)  # Red when recording
        else:
            self._color = (0, 255, 0)  # Green when idle

        lines = [f"{status}  {fps:.0f} FPS"]
        if is_recording:
            lines.append(f"Buffer: {buffer_fill*100:.0f}%")
        if game_name:
            lines.append(f"Game: {game_name[:20]}")
        lines.append("F8: Save Clip")

        self._text = "\n".join(lines)

    def move_to_corner(self, corner="top-right"):
        """Move overlay to a screen corner."""
        if not self._hwnd:
            return
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
        positions = {
            "top-right": (sw - self._width - 20, 20),
            "top-left": (20, 20),
            "bottom-right": (sw - self._width - 20, sh - self._height - 40),
            "bottom-left": (20, sh - self._height - 40),
        }
        x, y = positions.get(corner, positions["top-right"])
        win32gui.SetWindowPos(
            self._hwnd, win32con.HWND_TOPMOST,
            x, y, self._width, self._height,
            win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
        )
