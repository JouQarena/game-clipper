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

from clipper_app.logger import get_logger, install_global_handlers, get_log_file_path
from clipper_app.config_manager import ConfigManager

# Install global handlers FIRST so nothing crashes silently
install_global_handlers()
log = get_logger()

log.info("=" * 60)
log.info("Game Clipper starting")
log.info(f"Python: {sys.version}")
log.info(f"Platform: {sys.platform}")
log.info(f"Frozen exe: {getattr(sys, 'frozen', False)}")
log.info(f"Log file: {get_log_file_path()}")
log.info("=" * 60)


# Lazy imports so a single broken module doesn't kill startup
def _try_import(module_path, class_name=None):
    """Try to import a module/class, return None on failure."""
    try:
        mod_parts = module_path.rsplit(".", 1)
        if class_name:
            mod = __import__(module_path, fromlist=[class_name])
            return getattr(mod, class_name)
        return __import__(module_path)
    except Exception:
        log.exception(f"IMPORT FAILED: {module_path}.{class_name or ''}")
        if class_name:
            log.info(f"{class_name} will be DEGRADED")
        return None


ScreenCapture = _try_import("clipper_app.capture.screen_capture", "ScreenCapture")
AudioCapture = _try_import("clipper_app.capture.audio_capture", "AudioCapture")
ClipEncoder = _try_import("clipper_app.encoding.encoder", "ClipEncoder")
SettingsWindow = _try_import("clipper_app.gui.settings_window", "SettingsWindow")
TrayIcon = _try_import("clipper_app.gui.tray_icon", "TrayIcon")
GameDetector = _try_import("clipper_app.features.game_detection", "GameDetector")
Overlay = _try_import("clipper_app.features.overlay", "Overlay")
HotkeyListener = _try_import("clipper_app.utils.hotkey_listener", "HotkeyListener")


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

        # Components - all lazy-initialized to None
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
        try:
            self.encoder = ClipEncoder(self.config)
            log.info("[App] Encoder ready")
        except Exception:
            log.exception("[App] Encoder init FAILED")

        # 2. Screen capture
        try:
            if ScreenCapture:
                self.screen_capture = ScreenCapture(
                    self.config,
                    fps=self.config.get("fps", 30)
                )
                self.screen_capture.start()
                log.info("[App] ScreenCapture started")
        except Exception:
            log.exception("[App] ScreenCapture FAILED")

        # 3. Audio capture
        try:
            if AudioCapture:
                self.audio_capture = AudioCapture(self.config)
                self.audio_capture.start()
                log.info("[App] AudioCapture started")
        except Exception:
            log.exception("[App] AudioCapture FAILED")

        # 4. Hotkey listener
        try:
            if HotkeyListener:
                self.hotkey_listener = HotkeyListener()
                hotkey = self.config.get("hotkey", "F8")
                self.hotkey_listener.register_hotkey(hotkey, self._on_clip_hotkey)
                self.hotkey_listener.start()
                log.info(f"[App] Hotkey registered: {hotkey}")
        except Exception:
            log.exception("[App] Hotkey init FAILED")

        # 5. Game detection
        try:
            if GameDetector and self.config.get("enable_game_detection", True):
                self.game_detector = GameDetector()
                self.game_detector.add_listener(self._on_game_change)
                self.game_detector.start()
                log.info("[App] GameDetector started")
        except Exception:
            log.exception("[App] GameDetector FAILED")

        # 6. Overlay (often problematic on Windows - wrap especially)
        try:
            if Overlay and self.config.get("enable_overlay", True):
                self.overlay = Overlay()
                self.overlay.show()
                log.info("[App] Overlay shown")
        except Exception:
            log.exception("[App] Overlay init FAILED")

        # 7. System tray
        try:
            if TrayIcon:
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

    def stop(self):
        """Stop all components safely."""
        log.info("[App] Shutting down...")
        self._running = False

        for name, obj, method in [
            ("Overlay", self.overlay, "hide"),
            ("TrayIcon", self.tray_icon, "stop"),
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
        """Save the current buffer as a clip."""
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
        """Called when encoding done."""
        if path:
            log.info(f"[Save] OK -> {path}")
        else:
            log.error(f"[Save] FAILED")

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
            if not self.settings_window and SettingsWindow:
                self.settings_window = SettingsWindow(self.config, on_save=self._on_settings_saved)
            if self.settings_window:
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
                old = self.config.get("hotkey", "F8")
                self.hotkey_listener.unregister_hotkey(old)
                new = self.config.get("hotkey", "F8")
                self.hotkey_listener.register_hotkey(new, self._on_clip_hotkey)
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
        log.setLevel(10)  # DEBUG
        for h in log.handlers:
            if hasattr(h, 'setLevel'):
                h.setLevel(10)

    # Load config (with error handling)
    try:
        config = ConfigManager()
        log.info(f"[Main] Config loaded from {config.config_path}")
    except Exception:
        log.exception("[Main] Config load FAILED")
        config = ConfigManager.__new__(ConfigManager)
        config.data = dict(ConfigManager.DEFAULTS)
        from clipper_app.config_manager import ConfigManager as _CM
        config.config_path = os.path.join(os.getcwd(), "config.json")

    app = GameClipperApp(config)

    try:
        app.start()
        print()
        print("Game Clipper is running!")
        print("Press Ctrl+C to quit")
        print(f"Log file: {get_log_file_path()}")
        print()

        # Main thread just sleeps and watches for exit
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