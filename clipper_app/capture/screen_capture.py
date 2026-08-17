"""
Screen Capture Engine - DirectX (DXGI) via Desktop Duplication API.

Uses the Windows Desktop Duplication API for high-performance
GPU-accelerated screen capture. Falls back if DXGI is unavailable.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import dxcam
    HAS_DXCAM = True
except ImportError:
    HAS_DXCAM = False


@dataclass
class Frame:
    """A single captured frame with timestamp and metadata."""
    data: np.ndarray
    timestamp: float
    index: int


class ScreenCapture:
    """
    Captures the screen using DXGI Desktop Duplication API via dxcam.
    Provides continuous capture into a ring buffer.
    """

    def __init__(self, config_manager, fps=30, region=None):
        self.config = config_manager
        self.fps = fps
        self.region = region
        self.target_width = self.config.resolution_width
        self.target_height = self.config.resolution_height

        self._camera = None
        self._running = False
        self._capture_thread = None
        self._frame_count = 0
        self._lock = threading.Lock()

        buffer_seconds = self.config.get("buffer_duration_seconds", 30)
        max_frames = buffer_seconds * fps
        self.frame_buffer = deque(maxlen=max_frames)

        self._start_time = None
        self._current_fps = 0.0

    def start(self):
        """Start the capture loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._frame_count = 0
        self._start_time = time.time()
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        print(f"[ScreenCapture] Started at {self.fps} FPS")

    def stop(self):
        """Stop the capture loop."""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        if self._camera:
            try:
                self._camera.stop()
            except Exception:
                pass
        print("[ScreenCapture] Stopped")

    def _init_camera(self):
        """Initialize the dxcam camera."""
        if not HAS_DXCAM:
            print("[ScreenCapture] WARNING: dxcam not installed.")
            return None
        try:
            camera = dxcam.create(region=self.region, output_idx=0)
            return camera
        except Exception as e:
            print(f"[ScreenCapture] Failed to init dxcam: {e}")
            return None

    def _capture_loop(self):
        """Main capture loop running in background thread."""
        self._camera = self._init_camera()
        if not self._camera:
            self._running = False
            return

        self._camera.start(target_fps=self.fps, video_mode=True)

        frame_interval = 1.0 / self.fps
        next_frame_time = time.time()
        fps_counter = 0
        fps_timer = time.time()

        while self._running:
            try:
                now = time.time()
                if now < next_frame_time:
                    time.sleep(max(0, next_frame_time - time.time() - 0.001))
                    continue

                frame = self._camera.grab()

                if frame is not None:
                    self._frame_count += 1
                    fps_counter += 1

                    # Resize if needed
                    if HAS_CV2 and (frame.shape[1] != self.target_width or
                        frame.shape[0] != self.target_height):
                        frame = cv2.resize(frame,
                                           (self.target_width, self.target_height),
                                           interpolation=cv2.INTER_LINEAR)

                    with self._lock:
                        self.frame_buffer.appendleft(
                            Frame(
                                data=frame,
                                timestamp=time.time(),
                                index=self._frame_count
                            )
                        )

                    if time.time() - fps_timer >= 1.0:
                        self._current_fps = fps_counter
                        fps_counter = 0
                        fps_timer = time.time()

                next_frame_time += frame_interval

                if next_frame_time < time.time() - 0.1:
                    next_frame_time = time.time()

            except Exception as e:
                print(f"[ScreenCapture] Error: {e}")
                time.sleep(0.01)

    def get_buffer_snapshot(self):
        """Get ring buffer contents in chronological order (oldest first)."""
        with self._lock:
            frames = list(self.frame_buffer)
        frames.reverse()
        return frames

    @property
    def buffer_frame_count(self):
        with self._lock:
            return len(self.frame_buffer)

    @property
    def current_fps(self):
        return self._current_fps

    def update_settings(self):
        """Update settings from config (resolution change, etc.)."""
        self.target_width = self.config.resolution_width
        self.target_height = self.config.resolution_height
        self.fps = self.config.get("fps", 30)

        buffer_seconds = self.config.get("buffer_duration_seconds", 30)
        max_frames = buffer_seconds * self.fps
        with self._lock:
            new_buffer = deque(maxlen=max_frames)
            for f in self.frame_buffer:
                new_buffer.append(f)
            self.frame_buffer = new_buffer
