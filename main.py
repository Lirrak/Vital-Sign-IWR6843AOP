from __future__ import annotations

import argparse
import time
import tkinter as tk
from pathlib import Path

import serial
import serial.tools.list_ports

from vital_uart.app_config import (
    CFG_PATH,
    CLI_BAUD,
    CLI_PORT,
    DATA_BAUD,
    DATA_PORT,
    DURATION_SECONDS,
    OUT_DIR,
    PRINT_ALL_TLV,
    READ_SIZE,
    SEND_CONFIG_ON_START,
    VERBOSE_CFG,
    HARDWARE_RESET_ON_START,
    AUTO_DETECT_DAEMON,
)
from vital_uart.csv_logger import VitalCsvLogger
from vital_uart.gui import VitalSignsMonitorGUI
from vital_uart.mmwave_parser import MmWaveFrameParser, TLV_TYPE_VITAL_SIGNS
from vital_uart.radar_config import send_cfg_file
from vital_uart.vital_filter import RobustVitalFilter


def parse_args() -> argparse.Namespace:
    """
    Command line arguments are now optional.

    Default values come from:
        vital_uart/app_config.py

    That means you can edit app_config.py once, then simply run:
        python main.py
    """
    parser = argparse.ArgumentParser(
        description="Read IWR6843AOPEVM Vital Sign UART data and log HR/BR to CSV."
    )

    parser.add_argument(
        "--cli",
        default=CLI_PORT,
        help=f"CLI/CFG port. Default from app_config.py: {CLI_PORT}",
    )
    parser.add_argument(
        "--data",
        default=DATA_PORT,
        help=f"DATA port. Default from app_config.py: {DATA_PORT}",
    )
    parser.add_argument(
        "--cfg",
        default=CFG_PATH,
        help=f"Path to .cfg file or folder containing .cfg. Default: {CFG_PATH}",
    )
    parser.add_argument(
        "--out",
        default=OUT_DIR,
        help=f"Output folder for raw .bin and parsed .csv. Default: {OUT_DIR}",
    )
    parser.add_argument(
        "--cli-baud",
        type=int,
        default=CLI_BAUD,
        help=f"CLI baud rate. Default: {CLI_BAUD}",
    )
    parser.add_argument(
        "--data-baud",
        type=int,
        default=DATA_BAUD,
        help=f"DATA baud rate. Default: {DATA_BAUD}",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DURATION_SECONDS,
        help="Seconds to record; 0 means until Ctrl+C.",
    )
    parser.add_argument(
        "--read-size",
        type=int,
        default=READ_SIZE,
        help=f"Serial read block size. Default: {READ_SIZE}",
    )
    parser.add_argument(
        "--quiet-cfg",
        action="store_true",
        default=not VERBOSE_CFG,
        help="Do not print every cfg command.",
    )
    parser.add_argument(
        "--print-all-tlv",
        action="store_true",
        default=PRINT_ALL_TLV,
        help="Print TLV type summary for every packet.",
    )
    parser.add_argument(
        "--cli-mode",
        action="store_true",
        help="Run in pure CLI scrolling text mode instead of GUI.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=HARDWARE_RESET_ON_START,
        help=f"Toggle RTS/DTR to reset board programmatically. Default: {HARDWARE_RESET_ON_START}",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        default=AUTO_DETECT_DAEMON,
        help=f"Run in auto-detect daemon mode. Default: {AUTO_DETECT_DAEMON}",
    )

    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--send-config",
        dest="send_config",
        action="store_true",
        help="Force sending cfg before reading DATA port.",
    )
    config_group.add_argument(
        "--no-config",
        dest="send_config",
        action="store_false",
        help="Do not send cfg; only read DATA port.",
    )
    parser.set_defaults(send_config=SEND_CONFIG_ON_START)

    return parser.parse_args()


def detect_ports(pref_cli: str, pref_data: str) -> tuple[str | None, str | None]:
    """
    Check if preferred ports are available.
    If not, scan for other matching Silicon Labs dual-UART ports.
    """
    ports = [p.device for p in serial.tools.list_ports.comports()]
    
    if pref_cli in ports and pref_data in ports:
        return pref_cli, pref_data
        
    all_ports = sorted(serial.tools.list_ports.comports(), key=lambda x: x.device)
    cli_candidate = None
    data_candidate = None
    
    for p in all_ports:
        desc = p.description.lower()
        if "enhanced" in desc or "cfg" in desc or "cli" in desc:
            cli_candidate = p.device
        elif "standard" in desc or "data" in desc or "telemetry" in desc:
            data_candidate = p.device
            
    if not cli_candidate or not data_candidate:
        silabs_ports = [p for p in all_ports if "silicon labs" in p.description.lower() or "cp210" in p.description.lower()]
        if len(silabs_ports) >= 2:
            cli_candidate = silabs_ports[0].device
            data_candidate = silabs_ports[1].device
            
    return cli_candidate, data_candidate


def run_collection_session(cli_port: str, data_port: str, args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("========== IWR6843AOPEVM VITAL UART ==========")
    print(f"[SETUP] CLI/CFG port : {cli_port} @ {args.cli_baud}")
    print(f"[SETUP] DATA port    : {data_port} @ {args.data_baud}")
    print(f"[SETUP] CFG path     : {args.cfg}")
    print(f"[SETUP] Output folder: {out_dir.resolve()}")
    print(f"[SETUP] Send config  : {args.send_config}")
    print(f"[SETUP] Reset device : {args.reset}")

    if args.send_config:
        cfg_file = send_cfg_file(
            cli_port=cli_port,
            cfg_path=args.cfg,
            baudrate=args.cli_baud,
            verbose=not args.quiet_cfg,
            reset_device=args.reset,
        )
        print(f"[OK] Config sent: {cfg_file}")
        print("[INFO] Waiting 1.5s for sensorStart/data stream...")
        time.sleep(1.5)
    else:
        print("[INFO] Config sending disabled. Reading DATA port only.")

    frame_parser = MmWaveFrameParser()
    vital_filter = RobustVitalFilter()

    start_time = time.time()
    packet_count = 0
    vital_count = 0

    print(f"[DATA] Opening {data_port} @ {args.data_baud}")
    print("[DATA] Press Ctrl+C to stop.")

    with VitalCsvLogger(out_dir) as logger:
        print(f"[LOG] Raw UART   : {logger.raw_path}")
        print(f"[LOG] Vital CSV  : {logger.csv_path}")
        print(f"[LOG] TLV summary: {logger.tlv_path}")

        with serial.Serial(data_port, baudrate=args.data_baud, timeout=0.2) as data_ser:
            data_ser.reset_input_buffer()

            while True:
                if args.duration > 0 and (time.time() - start_time) >= args.duration:
                    print("[DONE] Duration reached.")
                    break

                chunk = data_ser.read(args.read_size)
                if not chunk:
                    continue

                logger.write_raw(chunk)
                packets = frame_parser.feed(chunk)

                for packet in packets:
                    packet_count += 1
                    logger.log_packet_summary(packet)

                    if args.print_all_tlv:
                        tlv_hex = ", ".join(hex(t.tlv_type) for t in packet.tlvs)
                        print(
                            f"[TLV] frame={packet.header.frame_number} "
                            f"numTLV={packet.header.num_tlvs} types=[{tlv_hex}]"
                        )

                    if not packet.vital_signs:
                        continue

                    elapsed_s = time.time() - start_time
                    for vital in packet.vital_signs:
                        vital_count += 1
                        filtered = vital_filter.update(vital)
                        logger.log_vital(elapsed_s, vital, filtered)

                        hr_f = _fmt(filtered.filtered_heart_rate_bpm)
                        br_f = _fmt(filtered.filtered_breathing_rate_bpm)
                        print(
                            f"[VITAL] frame={vital.frame_number:>7} "
                            f"id={vital.target_id:<3} rangeBin={vital.range_bin:<4} "
                            f"HR_raw={vital.heart_rate_bpm:6.2f} "
                            f"BR_raw={vital.breathing_rate_bpm:6.2f} "
                            f"HR_med={hr_f:>7} BR_med={br_f:>7} "
                            f"valid={filtered.is_valid} "
                            f"reason={filtered.reason} "
                            f"variant={vital.parser_variant}"
                        )

    print("\n========== SUMMARY ==========")
    print(f"Packets parsed : {packet_count}")
    print(f"Vital records  : {vital_count}")
    print(f"Dropped bytes  : {frame_parser.dropped_bytes}")
    print(f"Bad packets    : {frame_parser.bad_packets}")
    print(f"Vital TLV type : {hex(TLV_TYPE_VITAL_SIGNS)}")
    print(f"Output folder  : {out_dir.resolve()}")


def main() -> None:
    args = parse_args()
    
    if not args.cli_mode and not args.daemon:
        print("[SETUP] Launching GUI Dashboard. Use --cli-mode to run in terminal or --daemon for background autodetect.")
        root = tk.Tk()
        app = VitalSignsMonitorGUI(root)
        root.mainloop()
        return

    if args.daemon:
        print("========== IWR6843AOPEVM AUTO-DETECT DAEMON ==========")
        print(f"[DAEMON] Preferred CLI port  : {args.cli}")
        print(f"[DAEMON] Preferred DATA port : {args.data}")
        print(f"[DAEMON] Checking for devices every 1.0s...")
        print("[DAEMON] Press Ctrl+C to exit daemon.")

        last_port_check = 0.0
        try:
            while True:
                now = time.time()
                if now - last_port_check >= 1.0:
                    last_port_check = now
                    cli_port, data_port = detect_ports(args.cli, args.data)
                    if cli_port and data_port:
                        print(f"\n[DAEMON] Device detected! CLI: {cli_port}, DATA: {data_port}")
                        try:
                            run_collection_session(cli_port, data_port, args)
                        except (serial.SerialException, OSError) as e:
                            print(f"\n[DAEMON] Connection lost (device unplugged): {e}")
                        print("\n[DAEMON] Resuming standby. Waiting for device to be plugged in...")
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[DAEMON] Daemon stopped by user.")
    else:
        try:
            run_collection_session(args.cli, args.data, args)
        except KeyboardInterrupt:
            print("\n[STOP] User stopped recording.")


def _fmt(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.2f}"


if __name__ == "__main__":
    main()
