from __future__ import annotations

import queue
import serial
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

import serial.tools.list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import numpy as np
from .dsp_advanced import AdvancedVitalSignsDSP
from .dsp_filters import VitalSignStabilizer
from .mmwave_parser import VitalSignsSample
from .serial_worker import SerialWorker, WorkerConfig


class VitalSignMonitorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("IWR6843AOP Vital Sign Monitor")
        self.geometry("1200x820")
        self.minsize(1050, 720)

        self.worker: Optional[SerialWorker] = None
        self.start_time = time.time()
        self.history_t: List[float] = []
        self.history_hr: List[float] = []
        self.history_br: List[float] = []
        self.history_hr_raw: List[float] = []
        self.history_br_raw: List[float] = []
        self.history_dev: List[float] = []
        self.last_sample: Optional[VitalSignsSample] = None
        self.max_history_points = 600
        self.stabilizer = VitalSignStabilizer()
        self.advanced_dsp = AdvancedVitalSignsDSP()
        self.accumulated_heart_waveform: List[float] = []
        self.accumulated_breath_waveform: List[float] = []
        self.accumulated_timestamps: List[float] = []
        self.waveform_buffer_size = 256
        self.current_radar_range_bin: Optional[int] = None
        self.last_range_bin_update_time = 0.0

        self.cfg_port_var = tk.StringVar(value="COM13")
        self.data_port_var = tk.StringVar(value="COM14")
        self.cfg_file_var = tk.StringVar(value=str("C:/Users/Lirrak/Documents/Born Again/Radar Project/IWR6843AOP/Vital Sign/config/vital_signs_AOP_6m.cfg"))
        self.data_baud_var = tk.IntVar(value=921600)
        self.send_cfg_var = tk.BooleanVar(value=True)
        self.save_csv_var = tk.BooleanVar(value=True)
        self.csv_path_var = tk.StringVar(value=str(Path("logs") / "vital_signs.csv"))
        self.status_var = tk.StringVar(value="Idle")
        self.hr_var = tk.StringVar(value="Heart: -- bpm")
        self.br_var = tk.StringVar(value="Breath: -- bpm")
        self.target_var = tk.StringVar(value="Target: --")

        self._build_ui()
        self.after(100, self._update_ui_loop)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        controls = ttk.LabelFrame(root, text="Connection", padding=10)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="CFG port").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.cfg_port_var, width=12).grid(row=0, column=1, padx=5)

        ttk.Label(controls, text="DATA port").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.data_port_var, width=12).grid(row=0, column=3, padx=5)

        ttk.Label(controls, text="DATA baud").grid(row=0, column=4, sticky="w")
        ttk.Entry(controls, textvariable=self.data_baud_var, width=12).grid(row=0, column=5, padx=5)

        ttk.Button(controls, text="Refresh ports", command=self._refresh_ports).grid(row=0, column=6, padx=5)

        ttk.Label(controls, text="CFG file").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.cfg_file_var, width=72).grid(
            row=1, column=1, columnspan=5, sticky="ew", padx=5, pady=(8, 0)
        )
        ttk.Button(controls, text="Browse", command=self._browse_cfg).grid(row=1, column=6, padx=5, pady=(8, 0))

        ttk.Checkbutton(controls, text="Send CFG on start", variable=self.send_cfg_var).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(controls, text="Save CSV", variable=self.save_csv_var).grid(
            row=2, column=2, sticky="w", pady=(8, 0)
        )
        ttk.Entry(controls, textvariable=self.csv_path_var, width=45).grid(
            row=2, column=3, columnspan=3, sticky="ew", padx=5, pady=(8, 0)
        )
        ttk.Button(controls, text="CSV path", command=self._browse_csv).grid(row=2, column=6, padx=5, pady=(8, 0))

        self.start_button = ttk.Button(controls, text="Start", command=self._start)
        self.start_button.grid(row=3, column=0, pady=(10, 0), sticky="ew")
        self.stop_button = ttk.Button(controls, text="Stop", command=self._stop, state=tk.DISABLED)
        self.stop_button.grid(row=3, column=1, pady=(10, 0), sticky="ew")
        ttk.Button(controls, text="Clear plot", command=self._clear_plot).grid(row=3, column=2, pady=(10, 0), sticky="ew")
        ttk.Label(controls, textvariable=self.status_var).grid(row=3, column=3, columnspan=4, sticky="w", padx=10, pady=(10, 0))

        controls.columnconfigure(5, weight=1)

        gauges = ttk.Frame(root, padding=(0, 10, 0, 6))
        gauges.pack(fill=tk.X)
        ttk.Label(gauges, textvariable=self.hr_var, font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT, padx=(0, 25))
        ttk.Label(gauges, textvariable=self.br_var, font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT, padx=(0, 25))
        ttk.Label(gauges, textvariable=self.target_var, font=("Segoe UI", 12)).pack(side=tk.LEFT)

        chart_frame = ttk.Frame(root)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(10, 6), dpi=100)
        self.ax_rate = self.fig.add_subplot(311)
        self.ax_heart = self.fig.add_subplot(312)
        self.ax_breath = self.fig.add_subplot(313)
        self.fig.tight_layout(pad=2.0)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(root, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(8, 0))
        self.log_text = tk.Text(log_frame, height=8, wrap="word")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self._redraw_plot()

    def _refresh_ports(self) -> None:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            self._log("No serial ports found.")
            return
        self._log("Available serial ports:")
        for port in ports:
            self._log(f"  {port.device}: {port.description}")

    def _browse_cfg(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select TI .cfg file",
            filetypes=[("TI config", "*.cfg"), ("All files", "*.*")],
        )
        if file_path:
            self.cfg_file_var.set(file_path)

    def _browse_csv(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save CSV log",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if file_path:
            self.csv_path_var.set(file_path)

    def _start(self) -> None:
        if self.worker and self.worker.is_running:
            return

        cfg_file = self.cfg_file_var.get().strip()
        if self.send_cfg_var.get() and not Path(cfg_file).exists():
            messagebox.showerror(
                "Missing CFG",
                "Không thấy file .cfg. Hãy chọn vital_signs_AOP_2m.cfg hoặc vital_signs_AOP_6m.cfg từ TI Radar Toolbox.",
            )
            return

        self._clear_plot()
        self.start_time = time.time()

        config = WorkerConfig(
            cfg_port=self.cfg_port_var.get().strip(),
            data_port=self.data_port_var.get().strip(),
            cfg_file=cfg_file,
            data_baud=int(self.data_baud_var.get()),
            send_cfg_on_start=bool(self.send_cfg_var.get()),
            save_csv=bool(self.save_csv_var.get()),
            csv_path=self.csv_path_var.get().strip(),
        )
        self.worker = SerialWorker(config)
        self.worker.start()
        self.status_var.set("Starting...")
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)

    def _stop(self) -> None:
        if self.worker:
            self.worker.stop()
        self.status_var.set("Stopping...")
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)

    def _clear_plot(self) -> None:
        self.history_t.clear()
        self.history_hr.clear()
        self.history_br.clear()
        self.history_hr_raw.clear()
        self.history_br_raw.clear()
        self.history_dev.clear()
        self.stabilizer.reset()
        self.accumulated_heart_waveform.clear()
        self.accumulated_breath_waveform.clear()
        self.accumulated_timestamps.clear()
        self.current_radar_range_bin = None
        self.last_range_bin_update_time = 0.0
        self.last_sample = None
        self.hr_var.set("Heart: -- bpm")
        self.br_var.set("Breath: -- bpm")
        self.target_var.set("Target: --")
        self._redraw_plot()

    def _update_ui_loop(self) -> None:
        if self.worker:
            self._drain_worker_queues()
            if not self.worker.is_running and self.stop_button["state"] == tk.NORMAL:
                self.start_button.configure(state=tk.NORMAL)
                self.stop_button.configure(state=tk.DISABLED)
                self.status_var.set("Stopped")
        self.after(100, self._update_ui_loop)

    def _drain_worker_queues(self) -> None:
        assert self.worker is not None
        sample_received = False

        while True:
            try:
                log_line = self.worker.logs.get_nowait()
            except queue.Empty:
                break
            self._log(log_line)

        while True:
            try:
                sample = self.worker.samples.get_nowait()
            except queue.Empty:
                break
            self._handle_sample(sample)
            sample_received = True

        if sample_received:
            self._redraw_plot()

        if self.worker.is_running:
            self.status_var.set(
                f"Running | frames={self.worker.parser.frames_seen} | vital_tlvs={self.worker.parser.vital_tlvs_seen} | dropped={self.worker.parser.bytes_dropped} bytes"
            )

    def _update_radar_range_bin(self, target_id: int, range_bin: int) -> None:
        cfg_port = self.cfg_port_var.get().strip()
        
        def _send_cmd_thread():
            try:
                self._log(f"[DSP] Đang cấu hình động radar: Chuyển vùng Vital Signs sang Target {target_id} ở Range Bin {range_bin}...")
                with serial.Serial(cfg_port, 115200, timeout=0.5, write_timeout=1.0) as ser:
                    # Gửi lệnh thay đổi range bin
                    cmd = f"VSRangeIdxCfg {target_id} {range_bin}\n"
                    ser.write(cmd.encode("ascii"))
                    ser.flush()
                    time.sleep(0.05)
                    response = ser.read_all().decode("ascii", errors="ignore").strip()
                    if response:
                        self._log(f"[DSP] Radar phản hồi:\n{response}")
                    self._log(f"[DSP] Đã chuyển vùng Vital Signs sang Range Bin {range_bin} thành công!")
                    self.current_radar_range_bin = range_bin
            except Exception as e:
                self._log(f"[DSP] Lỗi cấu hình động radar qua {cfg_port}: {e}")

        threading.Thread(target=_send_cmd_thread, daemon=True).start()

    def _handle_sample(self, sample: VitalSignsSample) -> None:
        self.last_sample = sample
        t = sample.timestamp_s - self.start_time

        # 1. Accumulate raw waveforms and timestamps
        # Radar sends 15 historical points per packet, spaced at 90ms (0.090s)
        n_samples = len(sample.heart_waveform) if sample.heart_waveform else 0
        if n_samples > 0:
            frame_period_s = 0.090
            # Interpolate timestamps for all historical points inside the packet
            # The timestamp of the packet (sample.timestamp_s) corresponds to the last sample index (n_samples - 1)
            # The packet contains samples corresponding to times: sample.timestamp_s - (n_samples - 1 - i) * frame_period_s
            for i in range(n_samples):
                t_sample = sample.timestamp_s - (n_samples - 1 - i) * frame_period_s
                self.accumulated_heart_waveform.append(sample.heart_waveform[i])
                
                # Ensure breath waveform also has elements, fallback if lengths differ
                if sample.breath_waveform and i < len(sample.breath_waveform):
                    self.accumulated_breath_waveform.append(sample.breath_waveform[i])
                elif sample.breath_waveform:
                    self.accumulated_breath_waveform.append(sample.breath_waveform[-1])
                else:
                    self.accumulated_breath_waveform.append(0.0)
                    
                self.accumulated_timestamps.append(t_sample)
        else:
            # Fallback if waveform lists are empty
            self.accumulated_timestamps.append(sample.timestamp_s)
            self.accumulated_heart_waveform.append(0.0)
            self.accumulated_breath_waveform.append(0.0)

        # Keep buffer length at self.waveform_buffer_size using a while loop since we push multiple items at once
        while len(self.accumulated_heart_waveform) > self.waveform_buffer_size:
            self.accumulated_heart_waveform.pop(0)
        while len(self.accumulated_breath_waveform) > self.waveform_buffer_size:
            self.accumulated_breath_waveform.pop(0)
        while len(self.accumulated_timestamps) > self.waveform_buffer_size:
            self.accumulated_timestamps.pop(0)

        # 2. Dynamic range bin synchronization with Smart Range Bin Gate
        # Only accept range bin within a realistic human distance (bin 2 to 50, approx 0.3m to 6.0m)
        now = time.time()
        is_valid_bin = (2 <= sample.range_bin <= 50)
        
        if is_valid_bin and (self.current_radar_range_bin is None or self.current_radar_range_bin != sample.range_bin) and (now - self.last_range_bin_update_time > 5.0):
            self.last_range_bin_update_time = now
            self._update_radar_range_bin(sample.target_id, sample.range_bin)
            
            # Reset the dynamic waveforms buffers on range bin change to prevent phase discontinuities!
            self._log(f"[DSP] Đã xóa bộ đệm tích lũy dạng sóng để chuẩn bị nhận dữ liệu từ Range Bin mới {sample.range_bin}...")
            self.accumulated_heart_waveform.clear()
            self.accumulated_breath_waveform.clear()
            self.accumulated_timestamps.clear()

        # 3. Calculate dynamic sampling frequency fs_actual
        fs_actual = 11.11  # Mặc định theo cấu hình frame rate 90ms
        if len(self.accumulated_timestamps) >= 2:
            dts = np.diff(self.accumulated_timestamps)
            # Bỏ qua dts quá nhỏ
            valid_dts = dts[dts > 0.001]
            if len(valid_dts) > 0:
                mean_dt = np.mean(valid_dts)
                if mean_dt > 0.0:
                    fs_actual = 1.0 / mean_dt

        # 4. Estimate HR/BR using advanced secondary DSP if enough history is accumulated
        if len(self.accumulated_heart_waveform) >= 64:
            heart_arr = np.array(self.accumulated_heart_waveform)
            breath_arr = np.array(self.accumulated_breath_waveform)
            
            # Chuẩn hóa trục thời gian thực tế bắt đầu từ 0
            t_arr = np.array(self.accumulated_timestamps)
            t_history = t_arr - t_arr[0]
            
            hr_raw = self.advanced_dsp.filter_and_estimate_hr(heart_arr, breath_arr, fs_actual, t_history)
            br_raw = self.advanced_dsp.estimate_br(breath_arr, fs_actual, t_history)
        else:
            # Fallback to chip raw estimates during buffer warmup
            hr_raw = sample.heart_rate_bpm
            br_raw = sample.breathing_rate_bpm

        # 5. Stabilize / filter the vital signs data using the dual-stage stabilizer
        smoothed_hr, smoothed_br = self.stabilizer.process(
            hr_raw=hr_raw,
            hr_valid=sample.heart_rate_valid,
            br_raw=br_raw,
            br_valid=sample.breathing_rate_valid,
        )

        self.history_t.append(t)
        self.history_hr.append(smoothed_hr)
        self.history_br.append(smoothed_br)
        self.history_hr_raw.append(hr_raw)
        self.history_br_raw.append(br_raw)
        self.history_dev.append(sample.breathing_deviation)

        if len(self.history_t) > self.max_history_points:
            self.history_t = self.history_t[-self.max_history_points :]
            self.history_hr = self.history_hr[-self.max_history_points :]
            self.history_br = self.history_br[-self.max_history_points :]
            self.history_hr_raw = self.history_hr_raw[-self.max_history_points :]
            self.history_br_raw = self.history_br_raw[-self.max_history_points :]
            self.history_dev = self.history_dev[-self.max_history_points :]

        hr_text = f"Heart: {smoothed_hr:.1f} bpm"
        br_text = f"Breath: {smoothed_br:.1f} bpm"
        if not sample.heart_rate_valid:
            hr_text += " *"
        if not sample.breathing_rate_valid:
            br_text += " *"
        self.hr_var.set(hr_text)
        self.br_var.set(br_text)
        
        # Display extra info in the target bar including the buffer warming state
        warm_status = ""
        if len(self.accumulated_heart_waveform) < 64:
            warm_status = f" | DSP Warming: {len(self.accumulated_heart_waveform)}/64"
        self.target_var.set(
            f"Target ID: {sample.target_id} | Range bin: {sample.range_bin} | Breath dev: {sample.breathing_deviation:.3f} | Frame: {sample.frame_number}{warm_status}"
        )

    def _redraw_plot(self) -> None:
        self.ax_rate.clear()
        self.ax_heart.clear()
        self.ax_breath.clear()

        if self.history_t:
            # Heart rate: raw (dashed pinkish-red) vs smoothed (solid red)
            self.ax_rate.plot(
                self.history_t,
                self.history_hr_raw,
                color="#ff8787",
                linestyle="--",
                linewidth=1.0,
                alpha=0.6,
                label="Heart Rate (Raw)"
            )
            self.ax_rate.plot(
                self.history_t,
                self.history_hr,
                color="#fa5252",
                linestyle="-",
                linewidth=2.2,
                label="Heart Rate (Smoothed)"
            )
            
            # Breathing rate: raw (dashed light-blue) vs smoothed (solid blue)
            self.ax_rate.plot(
                self.history_t,
                self.history_br_raw,
                color="#74c0fc",
                linestyle="--",
                linewidth=1.0,
                alpha=0.6,
                label="Breathing Rate (Raw)"
            )
            self.ax_rate.plot(
                self.history_t,
                self.history_br,
                color="#228be6",
                linestyle="-",
                linewidth=2.2,
                label="Breathing Rate (Smoothed)"
            )

            self.ax_rate.set_xlabel("Time (s)")
            self.ax_rate.set_ylabel("BPM")
            self.ax_rate.grid(True, alpha=0.3)
            self.ax_rate.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", framealpha=0.8)
        else:
            self.ax_rate.text(0.5, 0.5, "No Vital Signs data yet", ha="center", va="center", transform=self.ax_rate.transAxes)
            self.ax_rate.set_xticks([])
            self.ax_rate.set_yticks([])

        if self.last_sample and self.last_sample.heart_waveform:
            self.ax_heart.plot(range(len(self.last_sample.heart_waveform)), self.last_sample.heart_waveform)
        self.ax_heart.set_title("Heart waveform circular buffer")
        self.ax_heart.set_xlabel("Sample index")
        self.ax_heart.grid(True, alpha=0.3)

        if self.last_sample and self.last_sample.breath_waveform:
            self.ax_breath.plot(range(len(self.last_sample.breath_waveform)), self.last_sample.breath_waveform)
        self.ax_breath.set_title("Breath waveform circular buffer")
        self.ax_breath.set_xlabel("Sample index")
        self.ax_breath.grid(True, alpha=0.3)

        self.fig.tight_layout(pad=2.0)
        self.canvas.draw_idle()

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


def main() -> None:
    app = VitalSignMonitorApp()
    app.mainloop()
