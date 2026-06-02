from __future__ import annotations

import argparse
from pathlib import Path

from vital_uart.mmwave_parser import MmWaveFrameParser
from vital_uart.vital_filter import RobustVitalFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a saved raw_uart_*.bin file.")
    parser.add_argument("bin_file", help="Path to saved raw UART binary file")
    parser.add_argument("--chunk", type=int, default=4096)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.bin_file).expanduser().resolve()
    parser = MmWaveFrameParser()
    filt = RobustVitalFilter()
    packets = 0
    vitals = 0

    with path.open("rb") as f:
        while True:
            chunk = f.read(args.chunk)
            if not chunk:
                break
            for packet in parser.feed(chunk):
                packets += 1
                for vital in packet.vital_signs:
                    vitals += 1
                    filtered = filt.update(vital)
                    print(
                        f"frame={vital.frame_number} id={vital.target_id} "
                        f"HR_raw={vital.heart_rate_bpm:.2f} BR_raw={vital.breathing_rate_bpm:.2f} "
                        f"HR_med={filtered.filtered_heart_rate_bpm} BR_med={filtered.filtered_breathing_rate_bpm} "
                        f"valid={filtered.is_valid} reason={filtered.reason}"
                    )

    print(f"Packets={packets}, Vital records={vitals}, Dropped bytes={parser.dropped_bytes}, Bad packets={parser.bad_packets}")


if __name__ == "__main__":
    main()
