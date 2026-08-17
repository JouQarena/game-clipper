"""
Ring Buffer - Circular buffer for storing video frames and audio data.

Provides a configurable circular buffer that continuously stores
the last N seconds of captured media in memory or temp files.
"""

import os
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

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


@dataclass
class AudioChunk:
    """A chunk of audio data with timestamp."""
    data: bytes
    timestamp: float
    sample_rate: int
    channels: int


class RingBuffer:
    """
    Circular ring buffer for video frames and audio chunks.

    Supports:
    - Configurable duration (default 30 seconds)
    - In-memory or temp-file storage
    - Thread-safe read/write
    """

    def __init__(self, duration_seconds=30, fps=30, storage="memory",
                 temp_dir=None, audio_sample_rate=48000):
        self.duration_seconds = duration_seconds
        self.fps = fps
        self.storage = storage
        self.audio_sample_rate = audio_sample_rate

        self._lock = threading.Lock()

        # Video frame buffer
        max_frames = duration_seconds * fps
        self.video_buffer = deque(maxlen=max_frames)

        # Audio buffer (each chunk ~0.1s of audio)
        self.audio_buffer = deque(maxlen=duration_seconds * 10)

        # Temp file storage
        self._temp_dir = temp_dir or tempfile.gettempdir()
        self._temp_file = None
        self._temp_file_size = 0
        self._frame_count = 0

        if storage == "temp_files":
            self._init_temp_file()

    def _init_temp_file(self):
        """Initialize temporary file for disk-backed storage."""
        try:
            self._temp_file = tempfile.NamedTemporaryFile(
                dir=self._temp_dir,
                prefix="gc_buffer_",
                suffix=".raw",
                delete=False
            )
            self._temp_file_path = self._temp_file.name
            print(f"[RingBuffer] Temp file: {self._temp_file_path}")
        except Exception as e:
            print(f"[RingBuffer] Failed to create temp file: {e}. Falling back to memory.")
            self.storage = "memory"

    def add_frame(self, frame):
        """Add a video frame to the buffer."""
        with self._lock:
            if self.storage == "temp_files" and self._temp_file:
                self._write_frame_to_disk(frame)
            self.video_buffer.append(frame)
            self._frame_count += 1

    def add_audio(self, audio_chunk):
        """Add an audio chunk to the buffer."""
        with self._lock:
            self.audio_buffer.append(audio_chunk)

    def _write_frame_to_disk(self, frame):
        """Write frame data to temp file (for disk-backed storage)."""
        if not HAS_CV2:
            return
        try:
            encoded = cv2.imencode('.jpg', frame.data, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
            size_bytes = len(encoded)
            # Write: timestamp(float) + data_length(int) + data
            header = f"{frame.timestamp},{size_bytes},{frame.index}\n".encode()
            self._temp_file.write(header + encoded.tobytes())
            self._temp_file.flush()
            self._temp_file_size += len(header) + size_bytes
        except Exception as e:
            print(f"[RingBuffer] Disk write error: {e}")

    def get_video_frames(self, oldest_first=True):
        """Get all video frames currently in the buffer."""
        with self._lock:
            frames = list(self.video_buffer)
        if oldest_first:
            frames.reverse()
        return frames

    def get_audio_chunks(self, oldest_first=True):
        """Get all audio chunks currently in the buffer."""
        with self._lock:
            chunks = list(self.audio_buffer)
        if oldest_first:
            chunks.reverse()
        return chunks

    def clear(self):
        """Clear the buffer and reset."""
        with self._lock:
            self.video_buffer.clear()
            self.audio_buffer.clear()
            self._frame_count = 0

    def resize(self, new_duration_seconds, new_fps=None):
        """Resize the buffer to a new duration."""
        if new_fps is None:
            new_fps = self.fps
        self.duration_seconds = new_duration_seconds
        self.fps = new_fps

        max_frames = new_duration_seconds * new_fps
        max_audio = new_duration_seconds * 10

        with self._lock:
            old_frames = list(self.video_buffer)
            old_audio = list(self.audio_buffer)
            self.video_buffer = deque(maxlen=max_frames)
            self.audio_buffer = deque(maxlen=max_audio)
            # Re-add frames (new buffer will only keep the latest)
            for f in reversed(old_frames):
                self.video_buffer.append(f)
            for a in reversed(old_audio):
                self.audio_buffer.append(a)

    @property
    def video_frame_count(self):
        with self._lock:
            return len(self.video_buffer)

    @property
    def audio_chunk_count(self):
        with self._lock:
            return len(self.audio_buffer)

    @property
    def memory_usage_estimate(self):
        """Estimate current memory usage in MB."""
        with self._lock:
            video_mb = len(self.video_buffer) * (self.video_buffer[0].data.nbytes
                                                  if self.video_buffer else 0) / (1024 * 1024)
            audio_mb = sum(len(c.data) for c in self.audio_buffer) / (1024 * 1024)
        return video_mb + audio_mb

    def cleanup(self):
        """Clean up temporary files."""
        if self._temp_file:
            try:
                self._temp_file.close()
                if os.path.exists(self._temp_file_path):
                    os.unlink(self._temp_file_path)
            except Exception:
                pass
            self._temp_file = None
            self._temp_file_size = 0
