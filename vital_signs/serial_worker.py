from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import serial
import serial.tools.list_ports

from .config_sender import send_config
from .csv_logger import CsvLogger
from .mmwave_parser import MmwavePacketParser, VitalSignsSample


@dataclass
class WorkerConfig:
    cfg_port: str
    data_port: str
    cfg_file: str
    cfg_baud: int = 115200
    data_baud: int = 921600
    send_cfg_on_start: bool = True
    csv_path: str = "logs/vital_signs.csv"
    save_csv: bool = True


def auto_detect_ports() -> Tuple[Optional[str], Optional[str]]:
    """Scans system serial ports to auto-detect Silicon Labs CP2105 Dual UART Bridge.

    Returns:
        Tuple[cfg_port, data_port] if detected, otherwise [None, None].
    """
    cfg_port = None
    data_port = None
    ports = list(serial.tools.list_ports.comports())

    # 1. Attempt detection using Silicon Labs CP2105 friendly descriptions
    for p in ports:
        desc = p.description or ""
        fn = getattr(p, "friendly_name", "") or ""
        device = p.device

        if "Enhanced COM Port" in desc or "Enhanced" in fn:
            cfg_port = device
        elif "Standard COM Port" in desc or "Standard" in fn:
            data_port = device

    # 2. Fallback: if not explicitly labeled, check generic dual CP210x ports
    if not cfg_port or not data_port:
        silabs_ports = []
        for p in ports:
            desc = p.description or ""
            fn = getattr(p, "friendly_name", "") or ""
            if "Silicon Labs" in desc or "CP210" in desc or "Silicon Labs" in fn or "CP210" in fn:
                silabs_ports.append(p.device)

        if len(silabs_ports) >= 2:
            # Historically, the lower COM index is Enhanced (CFG) and higher is Standard (DATA)
            silabs_ports_sorted = sorted(
                silabs_ports, key=lambda x: int("".join(filter(str.isdigit, x)) or 0)
            )
            cfg_port = silabs_ports_sorted[0]
            data_port = silabs_ports_sorted[1]

    return cfg_port, data_port


class SerialWorker:
    """Background worker that manages serial communications, configuration, and data acquisition."""

    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self.samples: queue.Queue[VitalSignsSample] = queue.Queue()
        self.logs: queue.Queue[str] = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.parser = MmwavePacketParser()
        self.csv_logger: Optional[CsvLogger] = None
        self.is_running = False

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.5)

    def _log(self, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.logs.put(f"[{ts}] {message}")

    def _run(self) -> None:
        self.is_running = True
        data_ser: Optional[serial.Serial] = None

        # 1. Automated Port Discovery
        self._log("Initiating hardware port auto-detection...")
        detected_cfg, detected_data = auto_detect_ports()
        
        actual_cfg = self.config.cfg_port
        actual_data = self.config.data_port

        if detected_cfg and detected_data:
            self._log(f"Auto-detected CP2105 Dual Bridge: CFG={detected_cfg}, DATA={detected_data}")
            actual_cfg = detected_cfg
            actual_data = detected_data
        else:
            self._log(f"CP2105 dual bridge not explicitly identified. Using defaults: CFG={actual_cfg}, DATA={actual_data}")

        # 2. Config transmission with exception recovery
        if self.config.send_cfg_on_start:
            try:
                send_config(
                    cfg_port=actual_cfg,
                    cfg_path=self.config.cfg_file,
                    baudrate=self.config.cfg_baud,
                    log=self._log,
                )
            except Exception as e:
                self._log(f"CFG ERROR: Failed to configure radar on {actual_cfg}: {e}")
                self._log("Radar may already be running or port is locked. Attempting to listen on DATA port...")

        # 3. CSV Logger setup
        if self.config.save_csv:
            try:
                self.csv_logger = CsvLogger(self.config.csv_path)
                self.csv_logger.open()
                self._log(f"CSV Logging enabled: {self.config.csv_path}")
            except Exception as e:
                self._log(f"CSV ERROR: Failed to open CSV log file: {e}")

        # 4. DATA UART Streaming Loop with dynamic reconnection self-healing
        reconnect_delay = 1.0
        while not self.stop_event.is_set():
            try:
                if data_ser is None or not data_ser.is_open:
                    self._log(f"Connecting to DATA port {actual_data} @ {self.config.data_baud}...")
                    data_ser = serial.Serial(
                        actual_data,
                        self.config.data_baud,
                        timeout=0.05,
                        write_timeout=1.0,
                    )
                    data_ser.reset_input_buffer()
                    self._log("Serial connection established. Streaming vital signs data...")

                # Read raw packets
                raw = data_ser.read(4096)
                if not raw:
                    continue

                timestamp_s = time.time()
                parsed_samples = self.parser.append(raw, timestamp_s)
                for sample in parsed_samples:
                    self.samples.put(sample)
                    if self.csv_logger is not None:
                        try:
                            self.csv_logger.write(sample)
                        except Exception as csv_err:
                            self._log(f"CSV WRITE ERROR: {csv_err}")

                if self.parser.last_error:
                    self._log(f"PARSER WARNING: {self.parser.last_error}")
                    self.parser.last_error = ""

            except serial.SerialException as se:
                self._log(f"SERIAL DISCONNECT: {se}. Retrying in {reconnect_delay}s...")
                if data_ser is not None:
                    try:
                        data_ser.close()
                    except Exception:
                        pass
                    data_ser = None
                time.sleep(reconnect_delay)
            except Exception as exc:
                self._log(f"UNEXPECTED WORKER EXCEPTION: {exc}")
                time.sleep(reconnect_delay)

        # Cleanup on stop
        if data_ser is not None and data_ser.is_open:
            try:
                data_ser.close()
            except Exception:
                pass
        if self.csv_logger is not None:
            try:
                self.csv_logger.close()
            except Exception:
                pass
            self.csv_logger = None

        self.is_running = False
        self._log("Worker stopped.")
