"""
Game Clipper - Main Application Entry Point

Lightweight, open-source video game clipping tool with
a 30-second pre-recording buffer (configurable).

Usage:
    python main.py              # Normal mode
    python main.py --debug      # Verbose logging + console
"""

import argparse
import os
import sys
import threading
import time

# Install global handlers FIRST so nothing crashes silently
from clipper_app.logger import (
    get_logger, install_global_handlers, get_log_file_path
)
from clipper_app.config_manager import ConfigManager

# Top-level imports so PyInstaller includes them in the frozen exe.
# We wrap each in try/except so a missing dependency doesn't crash
# the whole app before it even starts.
try:
    from clipper_app.capture.screen_capture import ScreenCapture
except ImportError:
    ScreenCapture = None

try:
    from clipper_app.capture.audio_capture import AudioCapture
except ImportError:
    AudioCapture = None

try:
    from clipper_app.capture.frame_buffer import RingBuffer, AudioChunk
except ImportError:
    RingBuffer = None
    AudioChunk = None

try:
    from clipper_app.encoding.encoder import ClipEncoder
except ImportError:
    ClipEncoder = None

try:
    from clipper_app.gui.settings_window import SettingsWindow
except ImportError:
    SettingsWindow = None

try:
    from clipper_app.gui.tray_icon import TrayIcon
except ImportError:
    TrayIcon = None

try:
    from clipper_app.features.game_detection import GameDetector
except ImportError:
    GameDetector = None

try:
    from clipper_app.features.overlay import Overlay
except ImportError:
    Overlay = None

try:
    from clipper_app.utils.hotkey_listener import HotkeyListener
except ImportError:
    HotkeyListener = None

install_global_handlers()
log = get_logger()

log.info("=" * 60)
log.info("Game Clipper starting")
log.info(f"Python: {sys.version}")
log.info(f"Platform: {sys.platform}")
log.info(f"Frozen exe: {getattr(sys, 'frozen', False)}")
log.info(f"Log file: {get_log_file_path()}")
log.info("=" * 60)


class GameClipperApp:
    """
    Main application class that coordinates all components.
    Each subsystem is wrapped in try/except so one failure
    doesn't take down the whole app.
    """

    def __init__(self, config):
        self.config = config
        self._running = False
        self._recording = False

        self.screen_capture = None
        self.audio_capture = None
        self.encoder = None
        self.settings_window = None
        self.tray_icon = None
        self.game_detector = None
        self.overlay = None
        self.hotkey_listener = None

    def start(self):
        """Start all components safely."""
        if self._running:
            return
        self._running = True
        log.info("[App] Starting components")

        # 1. Encoder (no background thread - just creates instance)
        if ClipEncoder is not None:
            try:
                self.encoder = ClipEncoder(self.config)
                log.info("[App] Encoder ready")
            except Exception:
                log.exception("[App] Encoder init FAILED")
        else:
            log.warning("[App] ClipEncoder not available (missing dependency)")

        # 2. Screen capture
        if ScreenCapture is not None:
            try:
                self.screen_capture = ScreenCapture(
                    self.config, fps=self.config.get("fps", 30)
                )
                self.screen_capture.start()
                log.info("[App] ScreenCapture started")
            except Exception:
                log.exception("[App] ScreenCapture FAILED")
        else:
            log.warning("[App] ScreenCapture not available (missing dependency)")

        # 3. Audio capture
        if AudioCapture is not None:
            try:
                self.audio_capture = AudioCapture(self.config)
                self.audio_capture.start()
                log.info("[App] AudioCapture started")
            except Exception:
                log.exception("[App] AudioCapture FAILED")
        else:
            log.warning("[App] AudioCapture not available (missing dependency)")

        # 4. Hotkey listener
        if HotkeyListener is not None:
            try:
                self.hotkey_listener = HotkeyListener()
                hotkey = self.config.get("hotkey", "F8")
                registered = self.hotkey_listener.register_hotkey(hotkey, self._on_clip_hotkey)
                if registered:
                    self.hotkey_listener.start()
                    log.info(f"[App] Hotkey registered: {hotkey}")
                else:
                    log.warning(f"[App] Hotkey '{hotkey}' FAILED to register")
            except Exception:
                log.exception("[App] Hotkey init FAILED")
        else:
            log.warning("[App] HotkeyListener not available (missing dependency)")

        # 5. Game detection
        if GameDetector is not None:
            try:
                if self.config.get("enable_game_detection", True):
                    self.game_detector = GameDetector()
                    self.game_detector.add_listener(self._on_game_change)
                    self.game_detector.start()
                    log.info("[App] GameDetector started")
            except Exception:
                log.exception("[App] GameDetector FAILED")
        else:
            log.warning("[App] GameDetector not available (missing dependency)")

        # 6. Overlay
        if Overlay is not None:
            try:
                if self.config.get("enable_overlay", True):
                    self.overlay = Overlay()
                    self.overlay.show()
                    log.info("[App] Overlay shown")
            except Exception:
                log.exception("[App] Overlay init FAILED")
        else:
            log.warning("[App] Overlay not available (missing dependency)")

        # 7. System tray
        if TrayIcon is not None:
            try:
                self.tray_icon = TrayIcon(
                    on_show=self._on_tray_show,
                    on_settings=self._on_tray_settings,
                    on_quit=self._on_tray_quit,
                    on_toggle_recording=self._toggle_recording,
                )
                self.tray_icon.run()
                log.info("[App] Tray icon running")
            except Exception:
                log.exception("[App] Tray icon FAILED")
        else:
            log.warning("[App] TrayIcon not available (missing dependency)")

        # Summary
        log.info("[App] === Started ===")
        log.info(f"  Screen capture: {self.screen_capture is not None}")
        log.info(f"  Audio capture:  {self.audio_capture is not None}")
        log.info(f"  Hotkey:         {self.hotkey_listener is not None}")
        log.info(f"  Game detector:  {self.game_detector is not None}")
        log.info(f"  Overlay:        {self.overlay is not None}")
        log.info(f"  Tray icon:      {self.tray_icon is not None}")
        log.info(f"  Encoder:        {self.encoder is not None}")
        log.info(f"  Hotkey:         {self.config.get('hotkey','F8')}")
        log.info(f"  Resolution:     {self.config.resolution_string}")
        log.info(f"  FPS:            {self.config.get('fps', 30)}")
        log.info(f"  Audio source:   {self.config.get('audio_source','game_only')}")
        log.info(f"  Log file:       {get_log_file_path()}")

        # Open the log file in the user's editor so they can see status
        self._maybe_open_log_once()

    def _maybe_open_log_once(self):
        """Helper for users running the packaged exe -- show the log
        file path in console / taskbar hint so they can find it."""
        pass  # No-op for now; the log path is printed in start()

    def stop(self):
        """Stop all components safely."""
        log.info("[App] Shutting down...")
        self._running = False

        for name, obj, method in [
            ("TrayIcon", self.tray_icon, "stop"),
            ("Overlay", self.overlay, "hide"),
            ("HotkeyListener", self.hotkey_listener, "stop"),
            ("GameDetector", self.game_detector, "stop"),
            ("AudioCapture", self.audio_capture, "stop"),
            ("ScreenCapture", self.screen_capture, "stop"),
        ]:
            try:
                if obj and hasattr(obj, method):
                    getattr(obj, method)()
                    log.debug(f"[App] {name} stopped")
            except Exception:
                log.exception(f"[App] Error stopping {name}")

        log.info("[App] Shutdown complete")

    def _on_clip_hotkey(self):
        """Called when save hotkey is pressed."""
        if not self.screen_capture:
            log.warning("[Hotkey] Screen capture not running")
            return
        log.info("[Hotkey] Save clip requested")
        self._save_clip()

    def _save_clip(self):
        if not self.screen_capture or not self.encoder:
            log.warning("[Save] No screen_capture or encoder")
            return
        frames = self.screen_capture.get_buffer_snapshot()
        if not frames:
            log.warning("[Save] No frames in buffer")
            return
        log.info(f"[Save] Encoding {len(frames)} frames")
        audio_chunks = None
        if self.audio_capture:
            audio_chunks = self.audio_capture.get_audio_data()
        self.encoder.save_clip(frames, audio_chunks=audio_chunks,
                               callback=self._on_clip_saved)

    def _on_clip_saved(self, path):
        if path:
            log.info(f"[Save] OK -> {path}")
        else:
            log.error("[Save] FAILED")

    def _toggle_recording(self):
        self._recording = not self._recording
        log.info(f"[App] recording={self._recording}")
        if self.tray_icon:
            try:
                self.tray_icon.set_recording_status(self._recording)
            except Exception:
                log.exception("[App] tray set status FAILED")

    def _on_game_change(self, game_name):
        log.info(f"[Game] {game_name or '<none>'}")

    def _on_tray_show(self):
        log.debug("[Tray] Show")

    def _on_tray_settings(self):
        log.debug("[Tray] Settings")
        try:
            if not self.settings_window:
                self.settings_window = SettingsWindow(self.config, on_save=self._on_settings_saved)
            self.settings_window.show()
        except Exception:
            log.exception("[Tray] Settings open FAILED")

    def _on_tray_quit(self):
        log.info("[Tray] Quit")
        self.stop()
        os._exit(0)

    def _on_settings_saved(self, config):
        log.info("[Settings] saved, applying")
        try:
            if self.hotkey_listener:
                # Read the NEW hotkey from the already-updated config
                new_hotkey = self.config.get("hotkey", "F8")
                # Unregister ALL previously registered hotkeys
                for old_key in list(self.hotkey_listener._key_names.values()):
                    self.hotkey_listener.unregister_hotkey(old_key)
                # Register the new hotkey
                self.hotkey_listener.register_hotkey(new_hotkey, self._on_clip_hotkey)
                log.info(f"[Settings] Hotkey changed to: {new_hotkey}")
        except Exception:
            log.exception("[Settings] hotkey re-register FAILED")
        try:
            if self.screen_capture:
                self.screen_capture.update_settings()
        except Exception:
            log.exception("[Settings] screen_capture update FAILED")


def main():
    parser = argparse.ArgumentParser(description="Game Clipper")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose console logging")
    args = parser.parse_args()

    if args.debug:
        log.setLevel(10)
        for h in log.handlers:
            if hasattr(h, 'setLevel'):
                h.setLevel(10)

    try:
        config = ConfigManager()
        log.info(f"[Main] Config loaded from {config.config_path}")
    except Exception:
        log.exception("[Main] Config load FAILED")
        config = ConfigManager.__new__(ConfigManager)
        from clipper_app.config_manager import ConfigManager as _CM
        config.data = dict(_CM.DEFAULTS)
        sys.path.insert(0, os.path.dirname(os.path.abspath("config.json")))
        config.config_path = os.path.join(os.getcwd(), "config.json")

    app = GameClipperApp(config)

    try:
        app.start()
        print()
        print("Game Clipper is running!")
        print("Press Ctrl+C to quit")
        print(f"Log file: {get_log_file_path()}")
        print()

        while app._running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    except Exception:
        log.exception("[Main] UNCAUGHT EXCEPTION IN MAIN LOOP")
    finally:
        app.stop()


if __name__ == "__main__":
    main()
