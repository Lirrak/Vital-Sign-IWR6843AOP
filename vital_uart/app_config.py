from __future__ import annotations

"""
User-editable fixed settings for IWR6843AOPEVM Vital Sign UART reader.

Edit this file when you want to permanently set COM ports, config file/folder,
baud rates, and output folder. After editing, you can simply run:

    python main.py

Typical Windows mapping for IWR6843AOPEVM:
    Enhanced COM Port -> CLI/CFG port  -> 115200 baud
    Standard COM Port -> DATA port     -> 921600 baud
"""

# -----------------------------------------------------------------------------
# 1) Fixed COM ports
# -----------------------------------------------------------------------------
# Change these to match your Device Manager.
# Example used in your current setup:
CLI_PORT = "COM13"      # Enhanced COM Port / CFG / CLI
DATA_PORT = "COM14"     # Standard COM Port / DATA

# -----------------------------------------------------------------------------
# 2) Fixed config path
# -----------------------------------------------------------------------------
# You can set this to:
#   - a direct .cfg file path, for example:
#       r"C:\ti\radar_toolbox_x_xx_xx_xx\...\vital_signs_AOP_2m.cfg"
#   - or a folder containing one .cfg file, for example:
#       r"./configs"
#
# If this is a folder, the code will automatically choose the most likely
# Vital Sign .cfg file in that folder.
CFG_PATH = r"C:/Users/Lirrak/Documents/Born Again/Radar Project/IWR6843AOP/Vital Sign/config/vital_signs_AOP_6m.cfg"

# -----------------------------------------------------------------------------
# 3) Baud rates
# -----------------------------------------------------------------------------
CLI_BAUD = 115200
DATA_BAUD = 921600

# -----------------------------------------------------------------------------
# 4) Runtime behavior
# -----------------------------------------------------------------------------
# True  = send CFG_PATH to radar before reading DATA port.
# False = do not send config; only listen to DATA port.
SEND_CONFIG_ON_START = True

# True  = toggle RTS/DTR on CLI port to perform hardware reset before sending config,
#         avoiding the need to manually press the RST button.
HARDWARE_RESET_ON_START = True

# True  = run in auto-detect daemon mode in CLI mode. The script will wait for the radar
#         to be plugged in, then automatically reset, configure, and start collecting data.
#         It will also handle unplugging gracefully and resume waiting.
AUTO_DETECT_DAEMON = False

# 0 = record until Ctrl+C.
# Example: 120 = record for 120 seconds.
DURATION_SECONDS = 0.0

# Output folder for raw UART .bin and parsed CSV files.
OUT_DIR = r"./logs"

# Serial read block size. Keep 4096 unless you have a reason to change it.
READ_SIZE = 4096

# Print every config command and CLI response.
VERBOSE_CFG = True

# Print all TLV types in every parsed packet. Useful for debugging unknown labs.
PRINT_ALL_TLV = False

# -----------------------------------------------------------------------------
# 5) Version 2 Bounding Box & Kalman Filter Settings
# -----------------------------------------------------------------------------
MIN_RANGE_M = 0.3       # Minimum tracking range in meters
MAX_RANGE_M = 1.5       # Maximum tracking range in meters

# Kalman Filter parameters
ENABLE_KALMAN_RANGE = True
ENABLE_KALMAN_VITAL = True

# Process noise covariance (Q) and measurement noise covariance (R)
KF_RANGE_Q = 0.01
KF_RANGE_R = 0.50

KF_VITAL_Q = 0.05
KF_VITAL_R = 1.00

# -----------------------------------------------------------------------------
# 6) Version 3 Point Cloud Centroid & Focus Lock Settings
# -----------------------------------------------------------------------------
# "auto" (Nearest-Cluster Priority) or "manual" (Focus Lock)
TRACKING_MODE = "auto"
FOCUS_CENTER_M = 0.5    # Manual mode center lock
FOCUS_SPAN_M = 0.2      # Manual mode window (+/- 0.2m)
