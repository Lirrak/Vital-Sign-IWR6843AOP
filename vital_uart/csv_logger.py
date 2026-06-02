from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional

from .mmwave_parser import ParsedPacket, VitalSignData
from .vital_filter import FilteredVitalSign


class VitalCsvLogger:
    def __init__(self, out_dir: str | Path, session_name: Optional[str] = None) -> None:
        self.out_dir = Path(out_dir).expanduser().resolve()
        self.out_dir.mkdir(parents=True, exist_ok=True)

        if session_name is None:
            session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_name = session_name

        self.csv_path = self.out_dir / f"vital_{session_name}.csv"
        self.raw_path = self.out_dir / f"raw_uart_{session_name}.bin"
        self.tlv_path = self.out_dir / f"tlv_summary_{session_name}.csv"

        self.csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        self.raw_file: BinaryIO = self.raw_path.open("wb")
        self.tlv_file = self.tlv_path.open("w", newline="", encoding="utf-8")

        self.writer = csv.DictWriter(
            self.csv_file,
            fieldnames=[
                "system_time_iso",
                "elapsed_s",
                "frame_number",
                "target_id",
                "range_bin",
                "breathing_deviation",
                "heart_rate_raw_bpm",
                "breathing_rate_raw_bpm",
                "heart_rate_filtered_bpm",
                "breathing_rate_filtered_bpm",
                "filter_valid",
                "filter_reason",
                "parser_variant",
                "tlv_length",
                "heart_circular_buffer_json",
                "breath_circular_buffer_json",
            ],
        )
        self.writer.writeheader()

        self.tlv_writer = csv.DictWriter(
            self.tlv_file,
            fieldnames=[
                "system_time_iso",
                "frame_number",
                "num_tlvs",
                "tlv_types_hex",
                "vital_count",
                "total_packet_len",
            ],
        )
        self.tlv_writer.writeheader()

    def write_raw(self, data: bytes) -> None:
        self.raw_file.write(data)
        self.raw_file.flush()

    def log_packet_summary(self, packet: ParsedPacket) -> None:
        self.tlv_writer.writerow(
            {
                "system_time_iso": datetime.now().isoformat(timespec="milliseconds"),
                "frame_number": packet.header.frame_number,
                "num_tlvs": packet.header.num_tlvs,
                "tlv_types_hex": ";".join(hex(t.tlv_type) for t in packet.tlvs),
                "vital_count": len(packet.vital_signs),
                "total_packet_len": packet.header.total_packet_len,
            }
        )
        self.tlv_file.flush()

    def log_vital(
        self,
        elapsed_s: float,
        vital: VitalSignData,
        filtered: FilteredVitalSign,
    ) -> None:
        self.writer.writerow(
            {
                "system_time_iso": datetime.now().isoformat(timespec="milliseconds"),
                "elapsed_s": f"{elapsed_s:.3f}",
                "frame_number": vital.frame_number,
                "target_id": vital.target_id,
                "range_bin": vital.range_bin,
                "breathing_deviation": f"{vital.breathing_deviation:.6f}",
                "heart_rate_raw_bpm": f"{filtered.raw_heart_rate_bpm:.3f}",
                "breathing_rate_raw_bpm": f"{filtered.raw_breathing_rate_bpm:.3f}",
                "heart_rate_filtered_bpm": _fmt_optional(filtered.filtered_heart_rate_bpm),
                "breathing_rate_filtered_bpm": _fmt_optional(filtered.filtered_breathing_rate_bpm),
                "filter_valid": int(filtered.is_valid),
                "filter_reason": filtered.reason,
                "parser_variant": vital.parser_variant,
                "tlv_length": vital.tlv_length,
                "heart_circular_buffer_json": json.dumps(vital.heart_circular_buffer, separators=(",", ":")),
                "breath_circular_buffer_json": json.dumps(vital.breath_circular_buffer, separators=(",", ":")),
            }
        )
        self.csv_file.flush()

    def close(self) -> None:
        self.csv_file.close()
        self.raw_file.close()
        self.tlv_file.close()

    def __enter__(self) -> "VitalCsvLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _fmt_optional(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.3f}"
