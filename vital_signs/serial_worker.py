from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import serial

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


class SerialWorker:
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

    def _log(self, message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.logs.put(f"[{ts}] {message}")

    def _run(self) -> None:
        self.is_running = True
        data_ser: Optional[serial.Serial] = None

        try:
            if self.config.send_cfg_on_start:
                send_config(
                    self.config.cfg_port,
                    self.config.cfg_file,
                    baudrate=self.config.cfg_baud,
                    log=self._log,
                )

            if self.config.save_csv:
                self.csv_logger = CsvLogger(self.config.csv_path)
                self.csv_logger.open()
                self._log(f"CSV logging: {self.config.csv_path}")

            self._log(f"Opening DATA port {self.config.data_port} @ {self.config.data_baud}...")
            data_ser = serial.Serial(
                self.config.data_port,
                self.config.data_baud,
                timeout=0.05,
                write_timeout=1.0,
            )
            data_ser.reset_input_buffer()
            self._log("Reading UART data. Keep the subject still and face the radar chest area.")

            while not self.stop_event.is_set():
                raw = data_ser.read(4096)
                if not raw:
                    continue

                timestamp_s = time.time()
                parsed_samples = self.parser.append(raw, timestamp_s)
                for sample in parsed_samples:
                    self.samples.put(sample)
                    if self.csv_logger is not None:
                        self.csv_logger.write(sample)

                if self.parser.last_error:
                    self._log(self.parser.last_error)
                    self.parser.last_error = ""

        except Exception as exc:  # noqa: BLE001 - show useful error in GUI
            self._log(f"ERROR: {exc}")
        finally:
            if data_ser is not None and data_ser.is_open:
                data_ser.close()
            if self.csv_logger is not None:
                self.csv_logger.close()
                self.csv_logger = None
            self.is_running = False
            self._log("Stopped.")
