"""
Encoding Engine - Takes frames from the ring buffer and encodes them
into an MP4 file using FFmpeg (software encoding with libx264).

Since the GTX 550 Ti does NOT support NVENC, we use CPU-based software encoding.
"""

import os
import subprocess
import threading
import time
from datetime import datetime
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


class ClipEncoder:
    """
    Encodes buffered frames into an MP4 video file using FFmpeg.

    Features:
    - Software encoding via libx264 (CPU-based)
    - Configurable quality/CRF
    - Audio muxing (if available)
    - Timestamped output filenames
    - Encoding runs in a background thread
    """

    def __init__(self, config_manager):
        self.config = config_manager
        self._encoding = False
        self._last_save_path = None
        self._ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self):
        """Find FFmpeg executable in PATH or common locations."""
        # 1. Bundled with PyInstaller exe (sys._MEIPASS/bin/ffmpeg.exe)
        try:
            import sys
            if getattr(sys, "frozen", False):
                bundled = os.path.join(sys._MEIPASS, "bin", "ffmpeg.exe")
                if os.path.exists(bundled):
                    print(f"[Encoder] Using bundled FFmpeg: {bundled}")
                    return bundled
        except Exception:
            pass

        # 2. Next to the exe (onedir build: dist/GameClipper/bin/ffmpeg.exe)
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            candidate = os.path.join(exe_dir, "bin", "ffmpeg.exe")
            if os.path.exists(candidate):
                return candidate

        # Check PATH first
        try:
            result = subprocess.run(
                ["where", "ffmpeg"] if os.name == "nt" else ["which", "ffmpeg"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0].strip()
        except Exception:
            pass

        # Common locations
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            os.path.expanduser("~/ffmpeg/bin/ffmpeg.exe"),
            "ffmpeg",  # Last resort, hope it's in PATH
        ]
        for c in candidates:
            if os.path.exists(c) or c == "ffmpeg":
                return c
        return "ffmpeg"

    def save_clip(self, frames, audio_chunks=None, callback=None):
        """
        Save the buffered frames as an MP4 clip.

        Args:
            frames: List of Frame objects (oldest first)
            audio_chunks: Optional list of AudioChunk objects
            callback: Optional callback when encoding is done

        Returns:
            Path to the saved file, or None on failure
        """
        if self._encoding:
            print("[Encoder] Already encoding, please wait...")
            return None

        if not frames:
            print("[Encoder] No frames to save!")
            return None

        thread = threading.Thread(
            target=self._encode_thread,
            args=(frames, audio_chunks, callback),
            daemon=True
        )
        thread.start()
        return "encoding_started"

    def _encode_thread(self, frames, audio_chunks, callback):
        """Background encoding thread."""
        self._encoding = True
        try:
            save_dir = self.config.get("save_location",
                                       os.path.expanduser("~/Videos/GameClipper"))
            os.makedirs(save_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"clip_{timestamp}.mp4"
            output_path = os.path.join(save_dir, filename)

            fps = self.config.get("fps", 30)
            quality = self.config.get("video_quality", 23)

            # Write frames to a temporary raw video file for FFmpeg
            temp_raw = os.path.join(save_dir, f"_temp_{timestamp}.raw")

            height, width = frames[0].data.shape[:2]

            # Write raw video data (BGR format)
            with open(temp_raw, "wb") as f:
                for frame in frames:
                    f.write(frame.data.tobytes())

            # Build FFmpeg command
            cmd = [
                self._ffmpeg_path,
                "-y",  # Overwrite output
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-s", f"{width}x{height}",
                "-pix_fmt", "bgr24",
                "-r", str(fps),
                "-i", temp_raw,
            ]

            # Add audio input if provided
            temp_audio = None
            if audio_chunks:
                audio_sr = audio_chunks[0].sample_rate
                audio_ch = audio_chunks[0].channels
                temp_audio = os.path.join(save_dir, f"_audio_{timestamp}.raw")
                with open(temp_audio, "wb") as f:
                    for chunk in audio_chunks:
                        f.write(chunk.data)

                cmd.extend([
                    "-f", "s16le",
                    "-acodec", "pcm_s16le",
                    "-ar", str(audio_sr),
                    "-ac", str(audio_ch),
                    "-i", temp_audio,
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                ])

            # Video encoding settings
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", str(quality),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path,
            ])

            print(f"[Encoder] Encoding to: {output_path}")
            print(f"[Encoder] FFmpeg cmd: {' '.join(cmd)}")

            # Run FFmpeg
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min max
            )

            if process.returncode != 0:
                print(f"[Encoder] FFmpeg error: {process.stderr[:500]}")
                self._last_save_path = None
            else:
                print(f"[Encoder] Saved: {output_path}")
                self._last_save_path = output_path

            # Cleanup temp files
            try:
                os.unlink(temp_raw)
                if temp_audio:
                    os.unlink(temp_audio)
            except Exception:
                pass

            if callback:
                callback(self._last_save_path)

        except subprocess.TimeoutExpired:
            print("[Encoder] Encoding timed out!")
            self._last_save_path = None
        except Exception as e:
            print(f"[Encoder] Encoding failed: {e}")
            self._last_save_path = None
        finally:
            self._encoding = False

    @property
    def is_encoding(self):
        return self._encoding

    @property
    def last_save_path(self):
        return self._last_save_path
