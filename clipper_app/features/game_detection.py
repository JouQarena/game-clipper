"""
Game Detection - Monitors active windows and detects running games.

Uses Windows API (via pywin32) to detect fullscreen applications
and identify games by process name / window title.
"""

import os
import re
import threading
import time
from typing import Optional, Set

try:
    import win32gui
    import win32process
    import win32api
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# Common game process names (non-exhaustive)
GAME_PROCESSES: Set[str] = {
    # Common game launchers and engines
    "steam.exe", "epicgameslauncher.exe", "battle.net.exe",
    "origin.exe", "uplay.exe", "goggalaxy.exe",
    "discord.exe",  # Not a game but often fullscreen
    # Game engines
    "unity.exe", "unrealcefsubprocess.exe",
}

# Known non-game fullscreen processes to ignore
IGNORE_PROCESSES: Set[str] = {
    "explorer.exe", "taskmgr.exe", "devenv.exe",
    "chrome.exe", "firefox.exe", "msedge.exe",
    "notepad.exe", "cmd.exe", "powershell.exe",
    "python.exe", "code.exe",  # VS Code
}


class GameDetector:
    """
    Detects if a game is currently running and in focus.

    Uses multiple heuristics:
    1. Window is fullscreen (no borders, covers entire screen)
    2. Process name matches known game patterns
    3. Window class matches game engines
    """

    def __init__(self, check_interval=1.0):
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._current_game = None
        self._lock = threading.Lock()
        self._listeners = []

        # Screen dimensions (for fullscreen detection)
        if HAS_WIN32:
            self._screen_width = win32api.GetSystemMetrics(0)
            self._screen_height = win32api.GetSystemMetrics(1)
        else:
            self._screen_width = 1920
            self._screen_height = 1080

    def start(self):
        """Start the detection loop."""
        if not HAS_WIN32:
            print("[GameDetector] win32 not available. Game detection disabled.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        print("[GameDetector] Started")

    def stop(self):
        """Stop the detection loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        print("[GameDetector] Stopped")

    def _detection_loop(self):
        """Main detection loop."""
        while self._running:
            try:
                game = self._detect_current_game()
                with self._lock:
                    if game != self._current_game:
                        self._current_game = game
                        for listener in self._listeners:
                            try:
                                listener(game)
                            except Exception:
                                pass
            except Exception as e:
                pass
            time.sleep(self.check_interval)

    def _detect_current_game(self) -> Optional[str]:
        """Detect if a game is currently in focus."""
        if not HAS_WIN32:
            return None

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None

            # Check if window is visible
            if not win32gui.IsWindowVisible(hwnd):
                return None

            # Get window info
            window_text = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = self._get_process_name(pid)

            # Skip known non-game processes
            if process_name.lower() in IGNORE_PROCESSES:
                return None

            # Check if window is fullscreen
            rect = win32gui.GetWindowRect(hwnd)
            is_fullscreen = (
                rect[2] - rect[0] >= self._screen_width - 10 and
                rect[3] - rect[1] >= self._screen_height - 10
            )

            # Heuristics for game detection
            if is_fullscreen or self._is_game_process(process_name):
                return window_text or process_name

            return None

        except Exception:
            return None

    def _get_process_name(self, pid) -> str:
        """Get the executable name for a PID."""
        try:
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, pid
            )
            exe = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            return os.path.basename(exe) if exe else ""
        except Exception:
            return ""

    def _is_game_process(self, process_name: str) -> bool:
        """Check if a process name looks like a game."""
        name = process_name.lower()
        if name in GAME_PROCESSES:
            return False  # Launchers are not games themselves
        # Game executables often have specific patterns
        if name.endswith(".exe") and name not in IGNORE_PROCESSES:
            return True
        return False

    def add_listener(self, callback):
        """Add a listener that gets called when the game changes.
        Callback receives: game_name (str) or None if no game."""
        self._listeners.append(callback)

    @property
    def current_game(self):
        with self._lock:
            return self._current_game

    @property
    def is_in_game(self):
        return self.current_game is not None


