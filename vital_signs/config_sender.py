from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Iterable, Optional

import serial


LogFn = Optional[Callable[[str], None]]


def iter_cfg_commands(cfg_path: str | Path) -> Iterable[str]:
    path = Path(cfg_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        yield line


def send_config(
    cfg_port: str,
    cfg_path: str | Path,
    baudrate: int = 115200,
    command_delay_s: float = 0.05,
    log: LogFn = None,
) -> None:
    """Send a TI mmWave .cfg file to the CLI/CFG UART port."""

    commands = list(iter_cfg_commands(cfg_path))
    if not commands:
        raise ValueError(f"No CLI commands found in config file: {cfg_path}")

    def _log(message: str) -> None:
        if log is not None:
            log(message)

    _log(f"Opening CFG port {cfg_port} @ {baudrate}...")
    with serial.Serial(cfg_port, baudrate, timeout=0.5, write_timeout=1.0) as ser:
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        for cmd in commands:
            ser.write((cmd + "\n").encode("ascii", errors="ignore"))
            ser.flush()
            time.sleep(command_delay_s)

            response = ser.read_all().decode("ascii", errors="ignore").strip()
            if response:
                _log(f"> {cmd}\n{response}")
            else:
                _log(f"> {cmd}")

    _log("Config sent successfully.")
