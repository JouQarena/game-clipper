"""
Game Clipper - Main Application Entry Point

Lightweight, open-source video game clipping tool with
a 30-second pre-recording buffer (configurable).

Usage:
    python main.py
"""

import os
import sys
import threading
import time

# ===== Make sure we can find the clipper_app package =====
# This script sits at the same level as the package dir
_BASE = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

# Import all components from the clipper_app package
from clipper_app.config_manager import ConfigManager
from clipper_app.capture.screen_capture import ScreenCapture
from clipper_app.capture.audio_capture import AudioCapture
from clipper_app.encoding.encoder import ClipEncoder
from clipper_app.gui.settings_window import SettingsWindow
from clipper_app.gui.tray_icon import TrayIcon
from clipper_app.features.game_detection import GameDetector
from clipper_app.features.overlay import Overlay
from clipper_app.utils.hotkey_listener import HotkeyListener


class GameClipperApp:
    """
    Main application class that coordinates all components.

    Manages the capture pipeline, ring buffer, encoding,
    GUI, hotkeys, and special features.
    """

    def __init__(self):
        print("=" * 50)
        print("Game Clipper - Starting up...")
        print("=" * 50)

        self.config = ConfigManager()

        # Core capture components
        self.screen_capture = None
        self.audio_capture = None
        self.encoder = ClipEncoder(self.config)

        # GUI components
        self.settings_window = None
        self.tray_icon = None

        # Features
        self.game_detector = GameDetector()
        self.overlay = Overlay()
        self.hotkey_listener = HotkeyListener()

        # State
        self._running = False
        self._recording = False
        self._main_window = None

        print("[Main] Initialized")

    def start(self):
        """Start all components."""
        if self._running:
            return

        self._running = True

        # Register hotkey
        hotkey = self.config.get("hotkey", "F8")
        self.hotkey_listener.register_hotkey(hotkey, self._on_clip_hotkey)

        # Start screen capture
        self.screen_capture = ScreenCapture(
            self.config,
            fps=self.config.get("fps", 30)
        )
        self.screen_capture.start()

        # Start audio capture
        self.audio_capture = AudioCapture(self.config)
        self.audio_capture.start()

        # Start game detection
        if self.config.get("enable_game_detection", True):
            self.game_detector.add_listener(self._on_game_change)
            self.game_detector.start()

        # Start hotkey listener
        self.hotkey_listener.start()

        # Show overlay if enabled
        if self.config.get("enable_overlay", True):
            self.overlay.show()

        # Start system tray
        self.tray_icon = TrayIcon(
            on_show=self._on_tray_show,
            on_settings=self._on_tray_settings,
            on_quit=self._on_tray_quit,
            on_toggle_recording=self._toggle_recording,
        )
        self.tray_icon.run()

        print("[Main] All components started")
        print(f"[Main] Hotkey: {hotkey} to save clip")
        print(f"[Main] Resolution: {self.config.resolution_string}")
        print(f"[Main] FPS: {self.config.get('fps', 30)}")
        print(f"[Main] Audio: {self.config.get('audio_source', 'game_only')}")

    def stop(self):
        """Stop all components gracefully."""
        print("[Main] Shutting down...")
        self._running = False

        if self.overlay:
            self.overlay.hide()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.game_detector:
            self.game_detector.stop()
        if self.audio_capture:
            self.audio_capture.stop()
        if self.screen_capture:
            self.screen_capture.stop()
        if self.tray_icon:
            self.tray_icon.stop()

        print("[Main] Shutdown complete")

    def _on_clip_hotkey(self):
        """Called when the save clip hotkey is pressed."""
        print("[Main] Hotkey pressed! Saving clip...")
        self._save_clip()

    def _save_clip(self):
        """Save the current buffer as a clip."""
        if not self.screen_capture:
            print("[Main] Screen capture not running")
            return

        # Get frames from buffer
        frames = self.screen_capture.get_buffer_snapshot()
        if not frames:
            print("[Main] No frames in buffer - nothing to save!")
            return

        print(f"[Main] Saving clip with {len(frames)} frames...")

        # Get audio chunks if available
        audio_chunks = None
        if self.audio_capture:
            audio_chunks = self.audio_capture.get_audio_data()

        # Start encoding
        self.encoder.save_clip(
            frames,
            audio_chunks=audio_chunks,
            callback=self._on_clip_saved
        )

    def _on_clip_saved(self, path):
        """Callback when clip encoding is complete."""
        if path:
            print(f"[Main] Clip saved: {path}")
        else:
            print("[Main] Failed to save clip!")

    def _get_buffer_fill(self):
        """Calculate buffer fill percentage."""
        if not self.screen_capture:
            return 0.0
        fps = self.config.get("fps", 30)
        duration = self.config.get("buffer_duration_seconds", 30)
        max_frames = fps * duration
        if max_frames == 0:
            return 0.0
        return min(1.0, self.screen_capture.buffer_frame_count / max_frames)

    def _update_overlay(self):
        """Update overlay with current status."""
        if self.overlay and self._running:
            self.overlay.update_status(
                is_recording=self._recording,
                fps=self.screen_capture.current_fps if self.screen_capture else 0,
                buffer_fill=self._get_buffer_fill(),
                game_name=self.game_detector.current_game or "",
            )

    def _toggle_recording(self):
        """Toggle recording state."""
        self._recording = not self._recording
        print(f"[Main] Recording: {self._recording}")

        if self.tray_icon:
            self.tray_icon.set_recording_status(self._recording)

        if self.overlay:
            self._update_overlay()

    def _on_game_change(self, game_name):
        """Called when a game starts/ends."""
        if game_name:
            print(f"[Main] Game detected: {game_name}")
        else:
            print("[Main] No game in focus")

        if self.overlay:
            self._update_overlay()

    def _on_tray_show(self):
        """Show main window."""
        pass

    def _on_tray_settings(self):
        """Open settings window."""
        if not self.settings_window:
            self.settings_window = SettingsWindow(
                self.config,
                on_save=self._on_settings_saved
            )
        self.settings_window.show()

    def _on_tray_quit(self):
        """Quit the application."""
        print("[Main] Quit requested via tray")
        self.stop()
        os._exit(0)

    def _on_settings_saved(self, config):
        """Called when settings are saved."""
        print("[Main] Settings updated, applying changes...")

        # Re-register hotkey if changed
        old_hotkey = self.config.get("hotkey", "F8")
        self.hotkey_listener.unregister_hotkey(old_hotkey)
        new_hotkey = self.config.get("hotkey", "F8")
        self.hotkey_listener.register_hotkey(new_hotkey, self._on_clip_hotkey)

        # Update screen capture settings
        if self.screen_capture:
            self.screen_capture.update_settings()

        # Update overlay
        if self.overlay:
            if self.config.get("enable_overlay", True):
                self.overlay.show()
            else:
                self.overlay.hide()

        # Update game detection
        if self.game_detector:
            if self.config.get("enable_game_detection", True):
                self.game_detector.start()
            else:
                self.game_detector.stop()


def main():
    """Application entry point."""
    app = GameClipperApp()

    try:
        app.start()
        print()
        print("Game Clipper is running!")
        print("Press Ctrl+C to quit")
        print()

        while app._running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        app.stop()


if __name__ == "__main__":
    main()