from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, List

import serial


COMMENT_PREFIXES = ("%", "#", "//")


def find_cfg_file(cfg_path: str | Path) -> Path:
    """
    Accept either a .cfg file path or a folder containing .cfg files.
    If a folder is provided, prefer files whose names look like vital sign configs.
    """
    path = Path(cfg_path).expanduser().resolve()

    if path.is_file():
        if path.suffix.lower() != ".cfg":
            raise ValueError(f"Config file must be .cfg, got: {path}")
        return path

    if not path.is_dir():
        raise FileNotFoundError(f"Config path does not exist: {path}")

    cfg_files = sorted(path.glob("*.cfg"))
    if not cfg_files:
        raise FileNotFoundError(f"No .cfg file found in folder: {path}")

    # Prefer common TI Vital Sign config names.
    priority_keywords = ("vital", "sign", "aop", "2m", "6m")
    scored: list[tuple[int, Path]] = []
    for cfg in cfg_files:
        name = cfg.name.lower()
        score = sum(1 for kw in priority_keywords if kw in name)
        scored.append((score, cfg))
    scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
    return scored[0][1]


def load_cfg_commands(cfg_file: str | Path) -> List[str]:
    """Load valid mmWave CLI commands from a .cfg file."""
    cfg_file = Path(cfg_file).expanduser().resolve()
    commands: List[str] = []

    with cfg_file.open("r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(COMMENT_PREFIXES):
                continue
            # TI cfg files often use '%' for comments. Remove inline '%' comments safely.
            if "%" in line:
                line = line.split("%", 1)[0].strip()
            if line:
                commands.append(line)

    return commands


def _read_cli_response(ser: serial.Serial, wait_s: float = 0.06) -> str:
    time.sleep(wait_s)
    data = ser.read_all()
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def send_cfg_commands(
    cli_port: str,
    commands: Iterable[str],
    baudrate: int = 115200,
    line_delay_s: float = 0.05,
    command_timeout_s: float = 1.0,
    verbose: bool = True,
) -> None:
    """
    Send mmWave .cfg commands to the CLI/CFG port.

    Use the Enhanced COM Port for IWR6843AOPEVM.
    """
    with serial.Serial(cli_port, baudrate=baudrate, timeout=command_timeout_s) as ser:
        time.sleep(1.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        for cmd in commands:
            if verbose:
                print(f"[CFG] {cmd}")
            ser.write((cmd + "\n").encode("ascii", errors="ignore"))
            ser.flush()

            # sensorStart and sensorStop may need a slightly longer wait.
            lower = cmd.lower()
            if lower.startswith("sensorstart") or lower.startswith("sensorstop") or lower.startswith("flushcfg"):
                time.sleep(0.25)
            else:
                time.sleep(line_delay_s)

            response = _read_cli_response(ser)
            if verbose and response.strip():
                print(response.strip())


def send_cfg_file(
    cli_port: str,
    cfg_path: str | Path,
    baudrate: int = 115200,
    verbose: bool = True,
) -> Path:
    """Find, load, and send a cfg file to the radar."""
    cfg_file = find_cfg_file(cfg_path)
    commands = load_cfg_commands(cfg_file)

    if not commands:
        raise ValueError(f"No valid CLI commands found in cfg file: {cfg_file}")

    if verbose:
        print(f"[CFG] Using config file: {cfg_file}")
        print(f"[CFG] Total commands: {len(commands)}")

    send_cfg_commands(cli_port=cli_port, commands=commands, baudrate=baudrate, verbose=verbose)
    return cfg_file
