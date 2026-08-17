# 🎮 Game Clipper - Lightweight 30-Second Instant Replay Tool

A lightweight, open-source video game clipping tool inspired by Rage Replay, featuring a 30-second pre-recording buffer (configurable) and completely free with no premium tiers.

## Features

- ⚡ **30-Second Instant Replay** — Continuous ring buffer captures the last 30 seconds (configurable)
- 🎬 **DirectX (DXGI) Screen Capture** — High-performance GPU-accelerated capture
- 🎵 **Dual Audio Recording** — System audio + microphone (configurable sources)
- 🖥️ **Adjustable Quality** — Resolution (360p-1080p) and FPS (30-60) settings
- ⌨️ **Customizable Hotkeys** — Bind any key to trigger clip saving
- 🎯 **Game Detection** — Automatically detects fullscreen games
- 💻 **System Tray** — Runs minimized with tray icon
- 🔧 **Zero Premium Tiers** — No watermarks, no limitations, 100% free

## System Requirements

- **OS:** Windows 10 (64-bit)
- **CPU:** Intel Core i5 or equivalent
- **RAM:** 16GB
- **GPU:** Any DirectX 11 compatible GPU
- **Storage:** SSD recommended for temporary buffer

## Installation

### 1. Install dependencies (core — no audio)

```bash
pip install -r clipper_app/requirements.txt
```

### 2. (Optional) Audio support

The app runs fine WITHOUT audio. To enable audio recording, install pyaudio using ONE of these methods:

**Method 1 — pipwin (easiest):**
```bash
pip install pipwin
pipwin install pyaudio
```

**Method 2 — C++ Build Tools** (if Method 1 fails):
Download and install from https://visualstudio.microsoft.com/visual-cpp-build-tools/
then:
```bash
pip install pyaudio
```

**Method 3 — Use Python 3.11 or 3.12:**
Python 3.14 is very new and has no pre-built pyaudio wheels yet.
Install Python 3.11/3.12 from python.org and use it for this project:
```bash
python3.12 -m venv venv
source venv/Scripts/activate
pip install -r clipper_app/requirements.txt
pip install pyaudio
```

### 3. Make sure FFmpeg is installed
Download from https://ffmpeg.org/download.html and add to PATH.

## Usage

```bash
python main.py
```

The application will start minimized to the system tray. Press the default hotkey (F8) to save the last 30 seconds of gameplay as an MP4 file.

## Configuration

All settings can be adjusted via the GUI settings window:
- **Buffer Duration:** 10-120 seconds
- **Resolution:** 360p / 480p / 720p / 1080p
- **FPS:** 30-60 FPS
- **Audio Sources:** Game only / Microphone + Game / All system audio
- **Hotkey:** Customizable key binding
- **Save Location:** Choose where clips are saved
- **Buffer Storage:** In-memory (faster) or Temp files (lower RAM)

## Performance Notes

- Higher settings (1080p @ 60 FPS) will consume significant CPU resources
- The GTX 550 Ti does NOT support NVENC hardware encoding — software encoding is used
- Recommended: 720p @ 30 FPS for balanced quality and performance

## Building the .exe

```bash
pip install pyinstaller
# Standalone exe:
pyinstaller --onefile --windowed --name "GameClipper" main.py
# Installer-ready folder:
pyinstaller --onedir --windowed --name "GameClipper" main.py
```

## License

MIT License - Free and open source for everyone.
