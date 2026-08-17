"""
Audio Capture Engine - Captures system audio (WASAPI loopback)
and microphone input using PyAudio.

Supports configurable audio sources:
- "game_only" : System output audio only (what you hear)
- "mic_and_game" : Microphone + system output
- "all_audio" : Microphone + system output + any other audio
"""

import queue
import threading
import time
from typing import Optional

from .frame_buffer import AudioChunk

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False


class AudioCapture:
    """
    Captures audio from system output (WASAPI loopback on Windows)
    and/or microphone input.

    On Windows:
    - System audio: uses WASAPI loopback via PyAudio (requires
      appropriate host API support)
    - Microphone: standard PyAudio input
    """

    # These are set in __init__ after checking HAS_PYAUDIO
    FORMAT = None
    CHANNELS = 2
    RATE = 48000
    CHUNK_SIZE = 1024

    def __init__(self, config_manager):
        self.config = config_manager
        self._running = False
        self._threads = []
        self._audio_queue = queue.Queue()

        self._pa_instance = None
        self._system_stream = None
        self._mic_stream = None

        # Buffer of audio chunks
        self.audio_buffer = []
        self._buffer_lock = threading.Lock()

        # Chunk index for unique IDs
        self._chunk_index = 0

        # Set audio format constants if pyaudio is available
        if HAS_PYAUDIO:
            AudioCapture.FORMAT = pyaudio.paInt16

    def start(self):
        """Start audio capture."""
        if self._running:
            return
        self._running = True

        if not HAS_PYAUDIO:
            print("[AudioCapture] WARNING: pyaudio not installed. Audio capture unavailable.")
            return

        try:
            self._pa_instance = pyaudio.PyAudio()
        except Exception as e:
            print(f"[AudioCapture] Failed to init PyAudio: {e}")
            self._running = False
            return

        source = self.config.get("audio_source", "game_only")

        # Always try to capture system audio (output)
        sys_thread = threading.Thread(
            target=self._capture_system_audio, daemon=True
        )
        sys_thread.start()
        self._threads.append(sys_thread)

        # Capture microphone if needed
        if source in ("mic_and_game", "all_audio"):
            mic_thread = threading.Thread(
                target=self._capture_microphone, daemon=True
            )
            mic_thread.start()
            self._threads.append(mic_thread)

        print(f"[AudioCapture] Started (source: {source})")

    def stop(self):
        """Stop audio capture."""
        self._running = False
        for t in self._threads:
            t.join(timeout=2)

        if self._system_stream:
            try:
                self._system_stream.stop_stream()
                self._system_stream.close()
            except Exception:
                pass
        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
        if self._pa_instance:
            try:
                self._pa_instance.terminate()
            except Exception:
                pass

        self._threads.clear()
        print("[AudioCapture] Stopped")

    def _find_loopback_device(self):
        """Find WASAPI loopback device for system audio capture."""
        if not self._pa_instance:
            return None

        for i in range(self._pa_instance.get_device_count()):
            try:
                info = self._pa_instance.get_device_info_by_index(i)
                name = info.get("name", "").lower()
                if "loopback" in name or "stereo mix" in name:
                    if info.get("maxInputChannels", 0) > 0:
                        print(f"[AudioCapture] Found loopback: {info['name']}")
                        return i
                if info.get("hostApi", 0) == 0 and ("speaker" in name or "output" in name):
                    if info.get("maxInputChannels", 0) > 0:
                        print(f"[AudioCapture] Found output device: {info['name']}")
                        return i
            except Exception:
                continue

        try:
            default = self._pa_instance.get_default_input_device_info()
            print(f"[AudioCapture] Fallback to default input: {default['name']}")
            return default["index"]
        except Exception:
            pass

        return None

    def _capture_system_audio(self):
        """Capture system output audio (WASAPI loopback)."""
        if not self._pa_instance:
            return

        device_index = self._find_loopback_device()

        try:
            self._system_stream = self._pa_instance.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self._system_audio_callback,
            )
            self._system_stream.start_stream()

            while self._running and self._system_stream.is_active():
                time.sleep(0.1)

        except Exception as e:
            print(f"[AudioCapture] System audio error: {e}")

    def _system_audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for system audio stream."""
        if self._running:
            self._chunk_index += 1
            chunk = AudioChunk(
                data=in_data,
                timestamp=time.time(),
                sample_rate=self.RATE,
                channels=self.CHANNELS,
            )
            with self._buffer_lock:
                self.audio_buffer.append(chunk)
                max_chunks = self.config.get("buffer_duration_seconds", 30) * 10
                if len(self.audio_buffer) > max_chunks:
                    self.audio_buffer = self.audio_buffer[-max_chunks:]
        return (None, pyaudio.paContinue)

    def _capture_microphone(self):
        """Capture microphone input."""
        if not self._pa_instance:
            return

        try:
            self._mic_stream = self._pa_instance.open(
                format=self.FORMAT,
                channels=1,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self._mic_audio_callback,
            )
            self._mic_stream.start_stream()

            while self._running and self._mic_stream.is_active():
                time.sleep(0.1)

        except Exception as e:
            print(f"[AudioCapture] Mic audio error: {e}")

    def _mic_audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for microphone stream."""
        if self._running:
            self._chunk_index += 1
            chunk = AudioChunk(
                data=in_data,
                timestamp=time.time(),
                sample_rate=self.RATE,
                channels=1,
            )
            with self._buffer_lock:
                self.audio_buffer.append(chunk)
                max_chunks = self.config.get("buffer_duration_seconds", 30) * 10
                if len(self.audio_buffer) > max_chunks:
                    self.audio_buffer = self.audio_buffer[-max_chunks:]
        return (None, pyaudio.paContinue)

    def get_audio_data(self, oldest_first=True):
        """Get all audio chunks from the buffer."""
        with self._buffer_lock:
            chunks = list(self.audio_buffer)
        if oldest_first:
            chunks.reverse()
        return chunks

    def clear_buffer(self):
        """Clear the audio buffer."""
        with self._buffer_lock:
            self.audio_buffer.clear()

    @property
    def is_capturing(self):
        return self._running