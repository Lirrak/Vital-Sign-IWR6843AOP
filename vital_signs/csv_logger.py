from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, TextIO

from .mmwave_parser import VitalSignsSample


class CsvLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.file: Optional[TextIO] = None
        self.writer: Optional[csv.writer] = None

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        header = [
            "timestamp_s",
            "frame_number",
            "target_id",
            "range_bin",
            "breathing_deviation",
            "heart_rate_bpm",
            "breathing_rate_bpm",
        ]
        header += [f"heart_waveform_{i}" for i in range(15)]
        header += [f"breath_waveform_{i}" for i in range(15)]
        self.writer.writerow(header)
        self.file.flush()

    def write(self, sample: VitalSignsSample) -> None:
        if self.writer is None or self.file is None:
            return
        row = [
            f"{sample.timestamp_s:.6f}",
            sample.frame_number,
            sample.target_id,
            sample.range_bin,
            f"{sample.breathing_deviation:.6f}",
            f"{sample.heart_rate_bpm:.6f}",
            f"{sample.breathing_rate_bpm:.6f}",
        ]
        row += [f"{v:.6f}" for v in sample.heart_waveform]
        row += [f"{v:.6f}" for v in sample.breath_waveform]
        self.writer.writerow(row)
        self.file.flush()

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
        self.file = None
        self.writer = None
