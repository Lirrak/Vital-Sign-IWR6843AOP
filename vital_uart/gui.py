from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import traceback
from pathlib import Path
from typing import List, Optional

import numpy as np
import serial
import serial.tools.list_ports
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .app_config import (
    CFG_PATH,
    CLI_BAUD,
    CLI_PORT,
    DATA_BAUD,
    DATA_PORT,
    OUT_DIR,
    READ_SIZE,
    SEND_CONFIG_ON_START,
    HARDWARE_RESET_ON_START,
)
from .csv_logger import VitalCsvLogger
from .mmwave_parser import MmWaveFrameParser, VitalSignData
from .radar_config import send_cfg_file
from .vital_filter import RobustVitalFilter, FilteredVitalSign


class SerialWorker(threading.Thread):
    """
    Background worker thread that connects to the radar,
    optionally uploads the config, and streams data into thread-safe queues.
    """

    def __init__(
        self,
        cli_port: str,
        data_port: str,
        cfg_path: str,
        cli_baud: int,
        data_baud: int,
        send_cfg: bool,
        out_dir: str,
        data_queue: queue.Queue,
        log_queue: queue.Queue,
    ) -> None:
        super().__init__()
        self.cli_port = cli_port
        self.data_port = data_port
        self.cfg_path = cfg_path
        self.cli_baud = cli_baud
        self.data_baud = data_baud
        self.send_cfg = send_cfg
        self.out_dir = Path(out_dir)
        self.data_queue = data_queue
        self.log_queue = log_queue
        self._stop_event = threading.Event()
        self.range_lock_config = ("auto", 0.5, 0.2)

    def update_range_lock(self, mode: str, center: float, span: float) -> None:
        self.range_lock_config = (mode, center, span)

    def run(self) -> None:
        self.log_queue.put("[INFO] Starting Serial Worker thread...")
        logger: Optional[VitalCsvLogger] = None
        data_ser: Optional[serial.Serial] = None

        try:
            # 1. Send Configuration if enabled
            if self.send_cfg:
                self.log_queue.put(f"[RESET] Performing hardware reset on {self.cli_port}...")
                self.log_queue.put(f"[CFG] Connecting to CLI {self.cli_port}...")
                cfg_file = send_cfg_file(
                    cli_port=self.cli_port,
                    cfg_path=self.cfg_path,
                    baudrate=self.cli_baud,
                    verbose=False,
                    reset_device=HARDWARE_RESET_ON_START,
                )
                self.log_queue.put(f"[OK] Configuration successfully sent: {cfg_file.name}")
                self.log_queue.put("[INFO] Waiting 1.5s for sensor to initialize...")
                time.sleep(1.5)

            # 2. Open CSV/Raw Logger
            logger = VitalCsvLogger(self.out_dir)
            self.log_queue.put(f"[LOG] Binary RAW path : {logger.raw_path.name}")
            self.log_queue.put(f"[LOG] CSV logs path   : {logger.csv_path.name}")

            # 3. Open Data Port
            self.log_queue.put(f"[DATA] Connecting to {self.data_port} @ {self.data_baud}...")
            data_ser = serial.Serial(self.data_port, baudrate=self.data_baud, timeout=0.2)
            data_ser.reset_input_buffer()
            self.log_queue.put("[DATA] Connection opened successfully. Listening for telemetry...")

            frame_parser = MmWaveFrameParser()
            vital_filter = RobustVitalFilter()
            start_time = time.time()

            while not self._stop_event.is_set():
                chunk = data_ser.read(READ_SIZE)
                if not chunk:
                    continue

                logger.write_raw(chunk)
                packets = frame_parser.feed(chunk)

                for packet in packets:
                    logger.log_packet_summary(packet)
                    elapsed_s = time.time() - start_time

                    mode, center, span = self.range_lock_config
                    vital_filter.set_tracking_parameters(mode, center, span)

                    if packet.point_cloud:
                        vital_filter.set_last_point_cloud(packet.point_cloud)
                        self.data_queue.put(("point_cloud", elapsed_s, packet.point_cloud))

                    if packet.vital_signs:
                        for vital in packet.vital_signs:
                            filtered = vital_filter.update(vital)
                            logger.log_vital(elapsed_s, vital, filtered)
                            self.data_queue.put(("vital", elapsed_s, vital, filtered))

        except Exception as e:
            tb = traceback.format_exc()
            self.log_queue.put(f"[ERROR] Worker Thread Exception:\n{tb}")
        finally:
            self.log_queue.put("[INFO] Cleaning up and closing connections...")
            if data_ser and data_ser.is_open:
                data_ser.close()
            if logger:
                logger.close()
            self.log_queue.put("[INFO] Serial Worker thread stopped.")

    def stop(self) -> None:
        self._stop_event.set()


class VitalSignsMonitorGUI:
    """
    Sleek Dark Mode desktop GUI for TI mmWave Radar Vital Signs.
    Built using tkinter and matplotlib.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TI mmWave Radar - Vital Signs Dashboard")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e2e")

        self.data_queue: queue.Queue = queue.Queue()
        self.log_queue: queue.Queue = queue.Queue()
        self.worker: Optional[SerialWorker] = None

        # Trend History
        self.trend_time: List[float] = []
        self.trend_hr: List[float] = []
        self.trend_br: List[float] = []
        self.max_trend_points = 100

        self._setup_style()
        self._build_ui()
        self._start_log_poller()

    def _setup_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configure overall themes
        style.configure(".", background="#1e1e2e", foreground="#cdd6f4")
        style.configure("TFrame", background="#1e1e2e")
        style.configure("Card.TFrame", background="#181825", relief="flat")
        
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="#181825", foreground="#cdd6f4")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 11))
        
        style.configure("TButton", background="#313244", foreground="#cdd6f4", borderwidth=0, font=("Segoe UI Semibold", 10))
        style.map("TButton", background=[("active", "#45475a")])
        style.configure("Start.TButton", background="#a6e3a1", foreground="#11111b")
        style.map("Start.TButton", background=[("active", "#94e2d5")])
        style.configure("Stop.TButton", background="#f38ba8", foreground="#11111b")
        style.map("Stop.TButton", background=[("active", "#eba0ac")])

    def _build_ui(self) -> None:
        # Main Grid Layout
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # ----------------- SIDEBAR PANEL (LEFT) -----------------
        sidebar = ttk.Frame(self.root, width=300, padding=15)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sidebar.grid_propagate(False)

        # Title
        title_lbl = ttk.Label(sidebar, text="RADAR CONTROLS", font=("Segoe UI Semibold", 14), foreground="#89b4fa")
        title_lbl.pack(anchor="w", pady=(0, 20))

        # Port Configuration
        ttk.Label(sidebar, text="Configuration Port (CLI):").pack(anchor="w", pady=(5, 2))
        self.cli_port_var = tk.StringVar(value=CLI_PORT)
        self.cli_combo = ttk.Combobox(sidebar, textvariable=self.cli_port_var, values=self._get_com_ports())
        self.cli_combo.pack(fill="x", pady=(0, 10))

        ttk.Label(sidebar, text="Data Port:").pack(anchor="w", pady=(5, 2))
        self.data_port_var = tk.StringVar(value=DATA_PORT)
        self.data_combo = ttk.Combobox(sidebar, textvariable=self.data_port_var, values=self._get_com_ports())
        self.data_combo.pack(fill="x", pady=(0, 10))

        # Config File Selector
        ttk.Label(sidebar, text="Configuration (.cfg) File:").pack(anchor="w", pady=(5, 2))
        self.cfg_path_var = tk.StringVar(value=CFG_PATH)
        cfg_frame = ttk.Frame(sidebar)
        cfg_frame.pack(fill="x", pady=(0, 10))
        cfg_entry = ttk.Entry(cfg_frame, textvariable=self.cfg_path_var)
        cfg_entry.pack(side="left", fill="x", expand=True)
        browse_btn = ttk.Button(cfg_frame, text="...", width=3, command=self._browse_cfg_file)
        browse_btn.pack(side="right", padx=(5, 0))

        # Toggles
        self.send_cfg_var = tk.BooleanVar(value=SEND_CONFIG_ON_START)
        ttk.Checkbutton(sidebar, text="Upload Config on Start", variable=self.send_cfg_var).pack(anchor="w", pady=5)

        # Target Range Lock Control Frame
        lock_frame = ttk.LabelFrame(sidebar, text="TARGET RANGE LOCK", padding=8)
        lock_frame.pack(fill="x", pady=10)

        ttk.Label(lock_frame, text="Mode:").grid(row=0, column=0, sticky="w", pady=2)
        self.lock_mode_var = tk.StringVar(value="auto")
        self.lock_mode_combo = ttk.Combobox(lock_frame, textvariable=self.lock_mode_var, values=["auto", "manual"], width=10, state="readonly")
        self.lock_mode_combo.grid(row=0, column=1, sticky="w", pady=2)
        self.lock_mode_combo.bind("<<ComboboxSelected>>", self._on_range_lock_change)

        ttk.Label(lock_frame, text="Center (m):").grid(row=1, column=0, sticky="w", pady=2)
        self.lock_center_var = tk.DoubleVar(value=0.5)
        self.lock_center_entry = ttk.Entry(lock_frame, textvariable=self.lock_center_var, width=8)
        self.lock_center_entry.grid(row=1, column=1, sticky="w", pady=2)
        self.lock_center_entry.bind("<KeyRelease>", self._on_range_lock_change)

        ttk.Label(lock_frame, text="Span (m):").grid(row=2, column=0, sticky="w", pady=2)
        self.lock_span_var = tk.DoubleVar(value=0.2)
        self.lock_span_entry = ttk.Entry(lock_frame, textvariable=self.lock_span_var, width=8)
        self.lock_span_entry.grid(row=2, column=1, sticky="w", pady=2)
        self.lock_span_entry.bind("<KeyRelease>", self._on_range_lock_change)

        # Action Buttons
        self.start_btn = ttk.Button(sidebar, text="START MONITORING", style="Start.TButton", command=self._start_streaming)
        self.start_btn.pack(fill="x", pady=(10, 10))

        self.stop_btn = ttk.Button(sidebar, text="STOP MONITORING", style="Stop.TButton", command=self._stop_streaming)
        self.stop_btn.pack(fill="x", pady=5)
        self.stop_btn.state(["disabled"])

        # Status Light Indicator
        status_frame = ttk.Frame(sidebar, padding=5)
        status_frame.pack(fill="x", side="bottom", pady=10)
        self.status_canvas = tk.Canvas(status_frame, width=20, height=20, bg="#1e1e2e", highlightthickness=0)
        self.status_canvas.pack(side="left")
        self.status_led = self.status_canvas.create_oval(2, 2, 18, 18, fill="#585b70") # Gray initially
        self.status_lbl = ttk.Label(status_frame, text="Disconnected", font=("Segoe UI Semibold", 10), foreground="#a6adc8")
        self.status_lbl.pack(side="left", padx=10)

        # ----------------- MAIN DISPLAY PANEL (RIGHT) -----------------
        main_panel = ttk.Frame(self.root, padding=10)
        main_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        main_panel.columnconfigure(0, weight=1)
        main_panel.columnconfigure(1, weight=1)
        main_panel.rowconfigure(1, weight=1)

        # 1. Cards Panel (HR & BR Digital readouts)
        cards_frame = ttk.Frame(main_panel)
        cards_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)
        cards_frame.columnconfigure(2, weight=1)

        # Heart Rate Card
        hr_card = ttk.Frame(cards_frame, style="Card.TFrame", padding=10)
        hr_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ttk.Label(hr_card, text="HEART RATE", style="Card.TLabel", font=("Segoe UI Semibold", 9), foreground="#f38ba8").pack(anchor="w")
        self.hr_val_lbl = ttk.Label(hr_card, text="-- BPM", style="Card.TLabel", font=("Segoe UI Semibold", 28), foreground="#f38ba8")
        self.hr_val_lbl.pack(anchor="w")
        self.hr_sub_lbl = ttk.Label(hr_card, text="Raw: -- BPM", style="Card.TLabel", font=("Segoe UI", 9), foreground="#a6adc8")
        self.hr_sub_lbl.pack(anchor="w")

        # Respiration Card
        br_card = ttk.Frame(cards_frame, style="Card.TFrame", padding=10)
        br_card.grid(row=0, column=1, sticky="nsew", padx=5)
        ttk.Label(br_card, text="RESPIRATION RATE", style="Card.TLabel", font=("Segoe UI Semibold", 9), foreground="#89dceb").pack(anchor="w")
        self.br_val_lbl = ttk.Label(br_card, text="-- BPM", style="Card.TLabel", font=("Segoe UI Semibold", 28), foreground="#89dceb")
        self.br_val_lbl.pack(anchor="w")
        self.br_sub_lbl = ttk.Label(br_card, text="Raw: -- BPM", style="Card.TLabel", font=("Segoe UI", 9), foreground="#a6adc8")
        self.br_sub_lbl.pack(anchor="w")

        # Range / Target Info Card
        info_card = ttk.Frame(cards_frame, style="Card.TFrame", padding=10)
        info_card.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        ttk.Label(info_card, text="TARGET DISTANCE", style="Card.TLabel", font=("Segoe UI Semibold", 9), foreground="#a6e3a1").pack(anchor="w")
        self.range_val_lbl = ttk.Label(info_card, text="-- m", style="Card.TLabel", font=("Segoe UI Semibold", 28), foreground="#a6e3a1")
        self.range_val_lbl.pack(anchor="w")
        self.range_sub_lbl = ttk.Label(info_card, text="Range Bin: --", style="Card.TLabel", font=("Segoe UI", 9), foreground="#a6adc8")
        self.range_sub_lbl.pack(anchor="w")

        # 2. Matplotlib Plots
        self.fig = Figure(figsize=(8, 5), dpi=100, facecolor="#1e1e2e")
        # Subplots 2x2 grid: Point Cloud (top-left), Respiration (top-right), Cardiac (bottom-left), Trends (bottom-right)
        self.ax_point_cloud = self.fig.add_subplot(2, 2, 1, facecolor="#181825")
        self.ax_br_wave = self.fig.add_subplot(2, 2, 2, facecolor="#181825")
        self.ax_hr_wave = self.fig.add_subplot(2, 2, 3, facecolor="#181825")
        self.ax_trend = self.fig.add_subplot(2, 2, 4, facecolor="#181825")

        for ax in (self.ax_point_cloud, self.ax_br_wave, self.ax_hr_wave, self.ax_trend):
            ax.tick_params(colors="#cdd6f4", labelsize=8)
            ax.grid(True, color="#313244", linestyle=":")
            for spine in ax.spines.values():
                spine.set_color("#45475a")

        self.ax_point_cloud.set_title("2D Point Cloud (X-Y)", color="#a6e3a1", fontsize=9, fontweight="bold")
        self.ax_point_cloud.set_xlim(-1.5, 1.5)
        self.ax_point_cloud.set_ylim(-2.5, 2.5)
        self.ax_point_cloud.set_xlabel("Horizontal X (m)", color="#a6adc8", fontsize=7)
        self.ax_point_cloud.set_ylabel("Depth Y (m)", color="#a6adc8", fontsize=7)
        self.ax_point_cloud.axhline(0, color="#313244", linestyle="--", lw=0.8)
        self.ax_point_cloud.axvline(0, color="#313244", linestyle="--", lw=0.8)
        self.pc_scatter = self.ax_point_cloud.scatter([], [], color="#a6e3a1", s=30, alpha=0.8)

        self.ax_br_wave.set_title("Respiration Waveform", color="#89dceb", fontsize=9, fontweight="bold")
        self.ax_hr_wave.set_title("Cardiac Waveform", color="#f38ba8", fontsize=9, fontweight="bold")
        self.ax_trend.set_title("Vitals Trend History", color="#cdd6f4", fontsize=9, fontweight="bold")

        self.br_wave_line, = self.ax_br_wave.plot([], [], color="#89dceb", lw=2)
        self.hr_wave_line, = self.ax_hr_wave.plot([], [], color="#f38ba8", lw=1.5)
        self.trend_hr_line, = self.ax_trend.plot([], [], color="#f38ba8", lw=2, label="Heart Rate")
        self.trend_br_line, = self.ax_trend.plot([], [], color="#89dceb", lw=2, label="Breathing Rate")
        self.ax_trend.legend(facecolor="#181825", edgecolor="#45475a", labelcolor="#cdd6f4", fontsize=7, loc="upper left")

        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_panel)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

        # 3. Log Terminal Display (Bottom)
        self.log_text = ScrolledText(main_panel, height=8, bg="#11111b", fg="#a6adc8", insertbackground="#cdd6f4", font=("Consolas", 9), relief="flat")
        self.log_text.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    def _get_com_ports(self) -> List[str]:
        ports = serial.tools.list_ports.comports()
        return [p.device for p in sorted(ports)]

    def _browse_cfg_file(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("Configuration Files", "*.cfg")])
        if filename:
            self.cfg_path_var.set(filename)

    def _start_log_poller(self) -> None:
        """Fetch logs and parsed frames from workers asynchronously."""
        # 1. Process log print statements
        while True:
            try:
                log_line = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, log_line + "\n")
                self.log_text.see(tk.END)
            except queue.Empty:
                break

        # 2. Process parsed data frames
        while True:
            try:
                item = self.data_queue.get_nowait()
                if item[0] == "vital":
                    _, elapsed_s, vital, filtered = item
                    self._update_telemetry(elapsed_s, vital, filtered)
                elif item[0] == "point_cloud":
                    _, elapsed_s, points = item
                    self._update_point_cloud(points)
            except queue.Empty:
                break

        self.root.after(30, self._start_log_poller)

    def _update_telemetry(self, elapsed_s: float, vital: VitalSignData, filtered: FilteredVitalSign) -> None:
        # Update Digital Metric Cards
        hr_val = filtered.filtered_heart_rate_bpm
        br_val = filtered.filtered_breathing_rate_bpm

        if hr_val is not None:
            self.hr_val_lbl.configure(text=f"{hr_val:.1f} BPM")
            self.trend_hr.append(hr_val)
        else:
            self.hr_val_lbl.configure(text="-- BPM")
            self.trend_hr.append(vital.heart_rate_bpm if vital.heart_rate_bpm > 0 else 70.0)

        if br_val is not None:
            self.br_val_lbl.configure(text=f"{br_val:.1f} BPM")
            self.trend_br.append(br_val)
        else:
            self.br_val_lbl.configure(text="-- BPM")
            self.trend_br.append(vital.breathing_rate_bpm if vital.breathing_rate_bpm > 0 else 15.0)

        self.hr_sub_lbl.configure(text=f"Raw: {vital.heart_rate_bpm:.1f} BPM")
        self.br_sub_lbl.configure(text=f"Raw: {vital.breathing_rate_bpm:.1f} BPM")

        range_m = filtered.filtered_range_m if filtered.filtered_range_m is not None else (vital.range_bin * 0.04)
        self.range_val_lbl.configure(text=f"{range_m:.2f} m")
        self.range_sub_lbl.configure(text=f"Range Bin: {vital.range_bin} | Dev: {vital.breathing_deviation:.3f}")

        # Update Trends History
        self.trend_time.append(elapsed_s)
        if len(self.trend_time) > self.max_trend_points:
            self.trend_time.pop(0)
            self.trend_hr.pop(0)
            self.trend_br.pop(0)

        # Plot Respiration Waveform
        if vital.breath_circular_buffer:
            y_data = np.array(vital.breath_circular_buffer)
            self.br_wave_line.set_data(range(len(y_data)), y_data)
            self.ax_br_wave.set_xlim(0, len(y_data) - 1)
            self.ax_br_wave.set_ylim(np.min(y_data) - 0.2, np.max(y_data) + 0.2)

        # Plot Cardiac Waveform
        if vital.heart_circular_buffer:
            y_data = np.array(vital.heart_circular_buffer)
            self.hr_wave_line.set_data(range(len(y_data)), y_data)
            self.ax_hr_wave.set_xlim(0, len(y_data) - 1)
            self.ax_hr_wave.set_ylim(np.min(y_data) - 0.2, np.max(y_data) + 0.2)

        # Plot Rate Trends
        if self.trend_time:
            self.trend_hr_line.set_data(self.trend_time, self.trend_hr)
            self.trend_br_line.set_data(self.trend_time, self.trend_br)
            self.ax_trend.set_xlim(self.trend_time[0], self.trend_time[-1])
            self.ax_trend.set_ylim(
                min(min(self.trend_hr), min(self.trend_br)) - 5,
                max(max(self.trend_hr), max(self.trend_br)) + 5
            )

        # Redraw plots
        self.canvas.draw_idle()

    def _update_point_cloud(self, points: List[Tuple[float, float, float, float]]) -> None:
        if not points:
            self.pc_scatter.set_offsets(np.empty((0, 2)))
        else:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            offsets = np.column_stack((xs, ys))
            self.pc_scatter.set_offsets(offsets)
        self.canvas.draw_idle()

    def _start_streaming(self) -> None:
        cli_port = self.cli_combo.get()
        data_port = self.data_combo.get()
        cfg_path = self.cfg_path_var.get()

        if not cli_port or not data_port:
            messagebox.showerror("Error", "Please specify COM Ports for CLI and DATA.")
            return

        if self.send_cfg_var.get() and not Path(cfg_path).exists():
            messagebox.showerror("Error", f"Configuration file not found: {cfg_path}")
            return

        self.log_text.delete("1.0", tk.END)

        # Initialize background worker
        self.worker = SerialWorker(
            cli_port=cli_port,
            data_port=data_port,
            cfg_path=cfg_path,
            cli_baud=CLI_BAUD,
            data_baud=DATA_BAUD,
            send_cfg=self.send_cfg_var.get(),
            out_dir=OUT_DIR,
            data_queue=self.data_queue,
            log_queue=self.log_queue,
        )
        try:
            mode = self.lock_mode_var.get()
            center = float(self.lock_center_var.get())
            span = float(self.lock_span_var.get())
            self.worker.update_range_lock(mode, center, span)
            self._update_point_cloud_lock_bounds(mode, center, span)
        except Exception:
            pass
        self.worker.start()

        # Update UI Controls
        self.start_btn.state(["disabled"])
        self.stop_btn.state(["!disabled"])
        self.status_canvas.itemconfig(self.status_led, fill="#a6e3a1") # Green (Connected)
        self.status_lbl.configure(text="Connected & Streaming", foreground="#a6e3a1")

        # Clear local graph buffers
        self.trend_time.clear()
        self.trend_hr.clear()
        self.trend_br.clear()

    def _stop_streaming(self) -> None:
        if self.worker and self.worker.is_alive():
            self.log_queue.put("[INFO] Stopping Serial Worker thread... Please wait.")
            self.worker.stop()
            self.worker.join(timeout=2.0)

        # Update UI Controls
        self.start_btn.state(["!disabled"])
        self.stop_btn.state(["disabled"])
        self.status_canvas.itemconfig(self.status_led, fill="#f38ba8") # Pink (Stopped)
        self.status_lbl.configure(text="Stopped", foreground="#f38ba8")

    def _on_range_lock_change(self, event=None) -> None:
        mode = self.lock_mode_var.get()
        try:
            center = float(self.lock_center_var.get())
            span = float(self.lock_span_var.get())
        except (ValueError, tk.TclError):
            return  # Skip invalid inputs

        if self.worker and self.worker.is_alive():
            self.worker.update_range_lock(mode, center, span)

        self._update_point_cloud_lock_bounds(mode, center, span)

    def _update_point_cloud_lock_bounds(self, mode: str, center: float, span: float) -> None:
        if not hasattr(self, "pc_lock_lines"):
            self.pc_lock_lines = []

        # Remove old lock boundary lines
        for line in self.pc_lock_lines:
            try:
                line.remove()
            except Exception:
                pass
        self.pc_lock_lines.clear()

        if mode == "manual":
            min_y = center - span
            max_y = center + span
            # Draw dotted boundaries (pinkish color matching theme)
            l1 = self.ax_point_cloud.axhline(min_y, color="#f5e0dc", linestyle=":", lw=1.2)
            l2 = self.ax_point_cloud.axhline(max_y, color="#f5e0dc", linestyle=":", lw=1.2)
            self.pc_lock_lines.extend([l1, l2])

        self.canvas.draw_idle()
