"""
System Tray Icon - Minimized application tray icon.

Using pystray to create a system tray icon with a context menu
for quick actions (show, settings, quit).
"""

import threading

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


class TrayIcon:
    """
    System tray icon for the Game Clipper.

    Provides a context menu with:
    - Show/Hide main window
    - Open Settings
    - Start/Stop recording
    - Quit
    """

    def __init__(self, on_show=None, on_settings=None,
                 on_quit=None, on_toggle_recording=None):
        self.on_show = on_show
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.on_toggle_recording = on_toggle_recording

        self._icon = None
        self._running = False
        self._recording = False

        self._thread = None

    def _create_image(self, recording=False):
        """Create a simple tray icon image."""
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)

        if recording:
            # Red recording dot
            dc.ellipse([8, 8, 56, 56], fill=(255, 0, 0, 255))
            dc.ellipse([18, 18, 46, 46], fill=(200, 0, 0, 255))
        else:
            # Green idle
            dc.ellipse([8, 8, 56, 56], fill=(0, 150, 0, 255))
            dc.ellipse([18, 18, 46, 46], fill=(0, 200, 0, 255))

        # Letter G
        dc.text((22, 20), "GC", fill=(255, 255, 255, 255))

        return image

    def run(self):
        """Run the tray icon (blocks until quit)."""
        if not HAS_PYSTRAY:
            print("[TrayIcon] pystray not available.")
            return

        menu = pystray.Menu(
            pystray.MenuItem("Show", self._on_show),
            pystray.MenuItem("Settings", self._on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Toggle Recording", self._on_toggle_recording,
                checked=lambda item: self._recording
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

        icon = pystray.Icon(
            "game_clipper",
            self._create_image(),
            "Game Clipper",
            menu
        )
        self._icon = icon
        self._running = True

        self._thread = threading.Thread(target=icon.run, daemon=True)
        self._thread.start()
        print("[TrayIcon] Running")

    def stop(self):
        """Stop the tray icon."""
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def set_recording_status(self, is_recording: bool):
        """Update icon to show recording status."""
        self._recording = is_recording
        if self._icon:
            try:
                self._icon.icon = self._create_image(is_recording)
            except Exception:
                pass

    def _on_show(self):
        if self.on_show:
            self.on_show()

    def _on_settings(self):
        if self.on_settings:
            self.on_settings()

    def _on_toggle_recording(self):
        if self.on_toggle_recording:
            self.on_toggle_recording()

    def _on_quit(self):
        if self.on_quit:
            self.on_quit()
        self.stop()