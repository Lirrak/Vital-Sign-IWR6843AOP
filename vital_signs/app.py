from __future__ import annotations

import argparse
import csv
import queue
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from .dsp_advanced import AdvancedVitalSignsDSP
from .dsp_filters import VitalSignStabilizer
from .mmwave_parser import VitalSignsSample
from .serial_worker import SerialWorker, WorkerConfig


class VitalSignMonitorCLI:
    """High-performance pure-scrolling CLI monitor that logs stabilized data exactly once every 10 seconds."""

    def __init__(
        self,
        cfg_port: str = "COM13",
        data_port: str = "COM14",
        cfg_file: str = "C:/Users/Lirrak/Documents/Born Again/Radar Project/IWR6843AOP/Vital Sign/config/vital_signs_AOP_6m.cfg",
        data_baud: int = 921600,
        send_cfg: bool = True,
        save_csv: bool = True,
        csv_path: str = "logs/vital_signs.csv",
    ) -> None:
        self.cfg_port = cfg_port
        self.data_port = data_port
        self.cfg_file = cfg_file
        self.data_baud = data_baud
        self.send_cfg = send_cfg
        self.save_csv = save_csv
        self.csv_path = csv_path

        self.worker: Optional[SerialWorker] = None
        self.start_time = time.time()
        
        # Vital sign histories
        self.history_t: List[float] = []
        self.history_hr: List[float] = []
        self.history_br: List[float] = []
        self.history_hr_raw: List[float] = []
        self.history_br_raw: List[float] = []
        self.history_dev: List[float] = []
        
        # Raw waveform buffers
        self.accumulated_heart_waveform: List[float] = []
        self.accumulated_breath_waveform: List[float] = []
        self.accumulated_timestamps: List[float] = []
        self.waveform_buffer_size = 256
        
        self.last_sample: Optional[VitalSignsSample] = None
        self.max_history_points = 600
        
        self.stabilizer = VitalSignStabilizer()
        self.advanced_dsp = AdvancedVitalSignsDSP()
        
        # 10-second scheduler variables
        self.last_print_time = 0.0
        self.print_interval = 10.0

    def start(self) -> None:
        if self.worker and self.worker.is_running:
            return

        cfg_file_path = Path(self.cfg_file)
        if self.send_cfg and not cfg_file_path.exists():
            sys.stderr.write(f"\033[91m[ERROR] Configuration file not found: {self.cfg_file}\n\033[0m")
            return

        self.start_time = time.time()
        self.last_print_time = time.time()  # Initialize print timer

        # Start SerialWorker with csv logging disabled in thread to prevent duplicate/high-frequency logs
        config = WorkerConfig(
            cfg_port=self.cfg_port,
            data_port=self.data_port,
            cfg_file=self.cfg_file,
            data_baud=self.data_baud,
            send_cfg_on_start=self.send_cfg,
            save_csv=False,  # Handled cleanly in main thread once every 10 seconds
        )
        self.worker = SerialWorker(config)
        self.worker.start()

        # Print welcoming header
        sys.stdout.write("\033[96m========================================================================\033[0m\n")
        sys.stdout.write(" (*) \033[1m60GHz mmWave Radar Vital Signs Scrolling Logger v1.0\033[0m\n")
        sys.stdout.write("     Interval: Logging stabilized readings every 10 seconds.\n")
        sys.stdout.write("\033[96m========================================================================\033[0m\n")
        sys.stdout.flush()

    def stop(self) -> None:
        if self.worker:
            self.worker.stop()
        sys.stdout.write("\n\033[93m[CLI] Monitor stopped safely.\n\033[0m")
        sys.stdout.flush()

    def run_loop(self) -> None:
        try:
            while self.worker and self.worker.is_running:
                self._drain_worker_queues()
                time.sleep(0.05)  # Moderate sleep
        except KeyboardInterrupt:
            sys.stdout.write("\n\033[93m[CLI] Keyboard interrupt detected. Exiting...\n\033[0m")
        finally:
            self.stop()

    def _drain_worker_queues(self) -> None:
        assert self.worker is not None

        # 1. Drain system/worker logs and print them immediately to screen
        while True:
            try:
                log_line = self.worker.logs.get_nowait()
                sys.stdout.write(f"\033[90m{log_line}\033[0m\n")
                sys.stdout.flush()
            except queue.Empty:
                break

        # 2. Drain parsed sample packets
        while True:
            try:
                sample = self.worker.samples.get_nowait()
                self._handle_sample(sample)
            except queue.Empty:
                break

    def _handle_sample(self, sample: VitalSignsSample) -> None:
        self.last_sample = sample
        t = sample.timestamp_s - self.start_time

        # 1. Accumulate raw waveforms
        n_samples = len(sample.heart_waveform) if sample.heart_waveform else 0
        if n_samples > 0:
            frame_period_s = 0.090
            for i in range(n_samples):
                t_sample = sample.timestamp_s - (n_samples - 1 - i) * frame_period_s
                self.accumulated_heart_waveform.append(sample.heart_waveform[i])

                if sample.breath_waveform and i < len(sample.breath_waveform):
                    self.accumulated_breath_waveform.append(sample.breath_waveform[i])
                elif sample.breath_waveform:
                    self.accumulated_breath_waveform.append(sample.breath_waveform[-1])
                else:
                    self.accumulated_breath_waveform.append(0.0)

                self.accumulated_timestamps.append(t_sample)
        else:
            self.accumulated_timestamps.append(sample.timestamp_s)
            self.accumulated_heart_waveform.append(0.0)
            self.accumulated_breath_waveform.append(0.0)

        # Truncate waveforms sliding window
        while len(self.accumulated_heart_waveform) > self.waveform_buffer_size:
            self.accumulated_heart_waveform.pop(0)
        while len(self.accumulated_breath_waveform) > self.waveform_buffer_size:
            self.accumulated_breath_waveform.pop(0)
        while len(self.accumulated_timestamps) > self.waveform_buffer_size:
            self.accumulated_timestamps.pop(0)

        # 2. Calculate dynamic sampling rate
        fs_actual = 11.11
        if len(self.accumulated_timestamps) >= 2:
            dts = np.diff(self.accumulated_timestamps)
            valid_dts = dts[dts > 0.001]
            if len(valid_dts) > 0:
                mean_dt = np.mean(valid_dts)
                if mean_dt > 0.0:
                    fs_actual = 1.0 / mean_dt

        # 3. Secondary DSP Estimation
        hr_conf = 1.0
        if len(self.accumulated_heart_waveform) >= 64:
            heart_arr = np.array(self.accumulated_heart_waveform)
            breath_arr = np.array(self.accumulated_breath_waveform)
            t_arr = np.array(self.accumulated_timestamps)
            t_history = t_arr - t_arr[0]

            hr_raw, hr_conf = self.advanced_dsp.filter_and_estimate_hr(
                heart_arr, breath_arr, fs_actual, t_history
            )
            br_raw = self.advanced_dsp.estimate_br(breath_arr, fs_actual, t_history)
        else:
            hr_raw = sample.heart_rate_bpm
            br_raw = sample.breathing_rate_bpm

        # 4. Dual-stage Stabilization
        smoothed_hr, smoothed_br = self.stabilizer.process(
            hr_raw=hr_raw,
            hr_valid=sample.heart_rate_valid,
            br_raw=br_raw,
            br_valid=sample.breathing_rate_valid,
            hr_conf=hr_conf,
            br_deviation=sample.breathing_deviation,
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

        # 5. Periodic 10-second data logging & screen printing
        now = time.time()
        if now - self.last_print_time >= self.print_interval:
            self.last_print_time = now
            self._export_vital_signs(sample, smoothed_hr, smoothed_br, hr_raw, br_raw, hr_conf, sample.breathing_deviation)

    def _export_vital_signs(
        self,
        sample: VitalSignsSample,
        hr_smoothed: float,
        br_smoothed: float,
        hr_raw: float,
        br_raw: float,
        hr_conf: float,
        br_dev: float,
    ) -> None:
        """Logs vital signs to console and CSV file exactly once every 10 seconds."""
        ts_str = time.strftime("%H:%M:%S")

        # Range verification and coloring
        hr_color = "\033[92m" if 50.0 <= hr_smoothed <= 110.0 else "\033[91m"
        br_color = "\033[92m" if 10.0 <= br_smoothed <= 25.0 else "\033[91m"

        is_warming = len(self.accumulated_heart_waveform) < 64
        status_tag = "\033[93m[WARMING]\033[0m" if is_warming else "\033[92m[OK]\033[0m"

        # PRINT TO CONSOLE
        sys.stdout.write(
            f"[{ts_str}] Bin: {sample.range_bin:2d} | "
            f"HR: {hr_color}{hr_smoothed:5.1f} BPM\033[0m (Raw: {hr_raw:5.1f}, Conf: {hr_conf:3.1f}) | "
            f"BR: {br_color}{br_smoothed:5.1f} BPM\033[0m (Raw: {br_raw:5.1f}, Dev: {br_dev:5.3f}) | "
            f"Status: {status_tag}\n"
        )
        sys.stdout.flush()

        # WRITE TO CSV (Clean 10-second rows)
        if self.save_csv:
            try:
                csv_path = Path(self.csv_path)
                if not csv_path.exists():
                    csv_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(csv_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            "timestamp_s", "datetime", "range_bin", "heart_rate_smoothed",
                            "heart_rate_raw", "breathing_rate_smoothed", "breathing_rate_raw",
                            "heart_confidence", "breathing_deviation"
                        ])
                
                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        f"{sample.timestamp_s:.3f}",
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        sample.range_bin,
                        f"{hr_smoothed:.2f}",
                        f"{hr_raw:.2f}",
                        f"{br_smoothed:.2f}",
                        f"{br_raw:.2f}",
                        f"{hr_conf:.2f}",
                        f"{br_dev:.4f}"
                    ])
            except Exception as e:
                sys.stderr.write(f"\033[91m[CSV ERROR] Failed to log 10s data row: {e}\n\033[0m")
                sys.stderr.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="IWR6843AOP Vital Sign Monitor (Console CLI)")
    parser.add_argument("--cfg_port", type=str, default="COM13", help="CLI config port")
    parser.add_argument("--data_port", type=str, default="COM14", help="Data port")
    parser.add_argument(
        "--cfg_file",
        type=str,
        default="C:/Users/Lirrak/Documents/Born Again/Radar Project/IWR6843AOP/Vital Sign/config/vital_signs_AOP_6m.cfg",
        help="Path to .cfg file",
    )
    parser.add_argument("--data_baud", type=int, default=921600, help="Baud rate for data port")
    parser.add_argument("--no_send_cfg", action="store_true", help="Do not send config file on start")
    parser.add_argument("--no_csv", action="store_true", help="Do not save CSV logs")
    parser.add_argument("--csv_path", type=str, default="logs/vital_signs.csv", help="Path to save CSV logs")

    args = parser.parse_args()

    app = VitalSignMonitorCLI(
        cfg_port=args.cfg_port,
        data_port=args.data_port,
        cfg_file=args.cfg_file,
        data_baud=args.data_baud,
        send_cfg=not args.no_send_cfg,
        save_csv=not args.no_csv,
        csv_path=args.csv_path,
    )
    app.start()
    app.run_loop()
