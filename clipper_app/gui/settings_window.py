"""
Settings Window - Tkinter-based GUI for configuring the clipper.

Features:
- Buffer duration slider (10-120 seconds)
- Resolution selector (360p/480p/720p/1080p)
- FPS slider (30-60)
- Audio source selector
- Hotkey configuration
- Save location picker
- Buffer storage mode
- Performance warning for high settings
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class SettingsWindow:
    """
    Tkinter settings window for configuring the Game Clipper.
    """

    def __init__(self, config_manager, on_save=None):
        self.config = config_manager
        self.on_save = on_save
        self.window = None
        self._widgets = {}

    def show(self):
        """Create and show the settings window."""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        self.window = tk.Toplevel()
        self.window.title("Game Clipper Settings")
        self.window.geometry("500x600")
        self.window.resizable(False, False)
        self.window.configure(bg="#2b2b2b")

        self.window.grab_set()
        self._build_ui()

    def _build_ui(self):
        """Build the settings UI."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#2b2b2b", foreground="white")
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TButton", background="#444", foreground="white")
        style.map("TButton", background=[("active", "#555")])

        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # BUFFER DURATION
        ttk.Label(main_frame, text="Buffer Duration (seconds):").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        dur_frame = ttk.Frame(main_frame)
        dur_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        duration = tk.IntVar(value=self.config.get("buffer_duration_seconds", 30))
        dur_slider = ttk.Scale(
            dur_frame, from_=10, to=120, variable=duration,
            orient=tk.HORIZONTAL, length=350
        )
        dur_slider.pack(side=tk.LEFT, padx=(0, 10))
        dur_label = ttk.Label(dur_frame, text=f"{duration.get()}s")
        dur_label.pack(side=tk.LEFT)

        def update_dur_label(*args):
            dur_label.config(text=f"{int(duration.get())}s")
        duration.trace_add("write", update_dur_label)

        self._widgets["duration"] = duration
        row += 1

        # RESOLUTION
        ttk.Label(main_frame, text="Resolution:").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        resolution = tk.StringVar(value=self.config.get("resolution", "720p"))
        res_combo = ttk.Combobox(
            main_frame, textvariable=resolution,
            values=["360p (640x360)", "480p (854x480)", "720p (1280x720)", "1080p (1920x1080)"],
            state="readonly", width=25
        )
        res_combo.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        def clean_res(*args):
            val = resolution.get()
            for r in ["360p", "480p", "720p", "1080p"]:
                if r in val:
                    resolution.set(r)
                    break
        resolution.trace_add("write", clean_res)

        self._widgets["resolution"] = resolution
        row += 1

        # FPS
        ttk.Label(main_frame, text="Frame Rate (FPS):").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        fps_frame = ttk.Frame(main_frame)
        fps_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        fps = tk.IntVar(value=self.config.get("fps", 30))
        fps_slider = ttk.Scale(
            fps_frame, from_=30, to=60, variable=fps,
            orient=tk.HORIZONTAL, length=350
        )
        fps_slider.pack(side=tk.LEFT, padx=(0, 10))
        fps_label = ttk.Label(fps_frame, text=f"{fps.get()} FPS")
        fps_label.pack(side=tk.LEFT)

        def update_fps_label(*args):
            fps_label.config(text=f"{int(fps.get())} FPS")
        fps.trace_add("write", update_fps_label)

        self._widgets["fps"] = fps
        row += 1

        # AUDIO SOURCE
        ttk.Label(main_frame, text="Audio Source:").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        audio_source = tk.StringVar(value=self.config.get("audio_source", "game_only"))
        audio_combo = ttk.Combobox(
            main_frame, textvariable=audio_source,
            values=[
                "game_only (Game audio only)",
                "mic_and_game (Mic + Game audio)",
                "all_audio (Mic + Game + Other audio)"
            ],
            state="readonly", width=35
        )
        audio_combo.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        def clean_audio(*args):
            val = audio_source.get()
            for a in ["game_only", "mic_and_game", "all_audio"]:
                if a in val:
                    audio_source.set(a)
                    break
        audio_source.trace_add("write", clean_audio)

        self._widgets["audio_source"] = audio_source
        row += 1

        # HOTKEY
        ttk.Label(main_frame, text="Save Hotkey:").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        hotkey = tk.StringVar(value=self.config.get("hotkey", "F8"))
        hotkey_entry = ttk.Entry(
            main_frame, textvariable=hotkey, width=15
        )
        hotkey_entry.grid(row=row, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Label(
            main_frame,
            text="Type the key (e.g., F8, CTRL+F, ALT+1)",
            foreground="#888"
        ).grid(row=row, column=1, sticky=tk.W, padx=(5, 0))

        self._widgets["hotkey"] = hotkey
        row += 1

        # SAVE LOCATION
        ttk.Label(main_frame, text="Save Location:").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        save_loc_frame = ttk.Frame(main_frame)
        save_loc_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))

        save_location = tk.StringVar(value=self.config.get("save_location",
                                           os.path.expanduser("~/Videos/GameClipper")))
        save_loc_entry = ttk.Entry(save_loc_frame, textvariable=save_location, width=35)
        save_loc_entry.pack(side=tk.LEFT, padx=(0, 5))

        def browse_save():
            dir_ = filedialog.askdirectory(
                 title="Select Save Folder")
            if dir_:
                save_location.set(dir_)

        browse_btn = ttk.Button(save_loc_frame, text="Browse", command=browse_save)
        browse_btn.pack(side=tk.LEFT)

        self._widgets["save_location"] = save_location
        row += 1

        # BUFFER STORAGE
        ttk.Label(main_frame, text="Buffer Storage:").grid(
            row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1

        buffer_storage = tk.StringVar(value=self.config.get("buffer_storage", "memory"))
        storage_combo = ttk.Combobox(
            main_frame, textvariable=buffer_storage,
            values=[
                "memory (Faster, uses more RAM)",
                "temp_files (Lower RAM, uses SSD)"
            ],
            state="readonly", width=35
        )
        storage_combo.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        def clean_storage(*args):
            val = buffer_storage.get()
            for s in ["memory", "temp_files"]:
                if s in val:
                    buffer_storage.set(s)
                    break
        buffer_storage.trace_add("write", clean_storage)

        self._widgets["buffer_storage"] = buffer_storage
        row += 1

        # PERFORMANCE WARNING
        perf_frame = ttk.Frame(main_frame)
        perf_frame.grid(row=row, column=0, columnspan=2, pady=(5, 10))
        warning_label = ttk.Label(
            perf_frame,
            text="\u26a0 High settings (1080p @ 60FPS) will use significant CPU resources.\n"
                 "Recommended: 720p @ 30 FPS for balanced performance.",
            foreground="#ffcc00",
            wraplength=450,
            justify=tk.LEFT
        )
        warning_label.pack(side=tk.LEFT)
        row += 1

        # BUTTONS
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Restore Defaults", command=self._on_defaults).pack(side=tk.LEFT, padx=5)

    def _on_save(self):
        """Save settings and close."""
        hotkey = self._widgets["hotkey"].get().strip().upper()
        if not hotkey:
            messagebox.showerror("Error", "Hotkey cannot be empty!")
            return

        self.config.set("buffer_duration_seconds", int(self._widgets["duration"].get()))
        self.config.set("resolution", self._widgets["resolution"].get())
        self.config.set("fps", int(self._widgets["fps"].get()))
        self.config.set("audio_source", self._widgets["audio_source"].get())
        self.config.set("hotkey", hotkey)
        self.config.set("save_location", self._widgets["save_location"].get())
        self.config.set("buffer_storage", self._widgets["buffer_storage"].get())

        if self.config.save():
            if self.on_save:
                self.on_save(self.config)
            messagebox.showinfo("Settings Saved", "Settings saved successfully!")
            self._on_cancel()
        else:
            messagebox.showerror("Error", "Failed to save settings!")

    def _on_cancel(self):
        """Close the settings window."""
        if self.window:
            self.window.grab_release()
            self.window.destroy()
        self.window = None

    def _on_defaults(self):
        """Restore default settings."""
        if messagebox.askyesno("Restore Defaults",
                                "Are you sure you want to restore default settings?"):
            self._widgets["duration"].set(30)
            self._widgets["resolution"].set("720p")
            self._widgets["fps"].set(30)
            self._widgets["audio_source"].set("game_only")
            self._widgets["hotkey"].set("F8")
            self._widgets["save_location"].set(
                os.path.expanduser("~/Videos/GameClipper"))
            self._widgets["buffer_storage"].set("memory")