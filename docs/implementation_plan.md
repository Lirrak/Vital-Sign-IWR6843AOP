# Implementation Plan - mmWave Vital Signs Parser & Filtering Pipeline

This document details the software development lifecycle, structural difficulties, obstacles, and proposed solutions for the Python-based mmWave UART Vital Signs pipeline. It outlines the transition from the current V1 baseline to future, more robust iterations.

---

## Version 1: Stateful Parsing & Conservative Post-Filtering (Current Baseline)

### Architecture Overview
The current implementation consists of:
1.  **CLI Config Sender (`radar_config.py`)**: Sends `.cfg` configurations sequentially over a 115200 baud UART connection.
2.  **Stateful Frame Parser (`mmwave_parser.py`)**: Feeds incoming serial bytes into a dynamic ring buffer, locates the TI Magic Word (`0x0201040306050807`), validates package length headers, and decodes TLV type `0x410` (Vital Signs).
3.  **Conservative Post-Filter (`vital_filter.py`)**: Validates raw heart rate (HR) and breathing rate (BR) values against absolute boundaries and jump thresholds, applying a rolling median filter over accepted values.
4.  **CSV and Raw Binary Logger (`csv_logger.py`)**: Logs parsed values, filtering status, and raw circular waveforms.

---

### Technical Obstacles & Difficulties in V1

During our comprehensive code review of the V1 baseline, we identified several critical obstacles:

#### 1. Filter Lockout (Filter Deadlock)
*   **Problem**: In `vital_filter.py` (lines 91-94), the filter rejects sudden jumps in values:
    ```python
    if self.last_hr is not None and abs(hr - self.last_hr) > self.max_hr_jump_bpm:
        return False, f"hr_jump_{self.last_hr:.2f}_to_{hr:.2f}"
    ```
    If `_validate` returns `False`, `self.last_hr` is **never updated** with the new value.
*   **Obstacle**: If the subject's heart rate genuinely jumps (e.g., from 70 to 100 BPM due to movement or arousal), the difference (30 BPM) exceeds `max_hr_jump_bpm` (28.0). The filter will reject 100. The next sample (101) will *also* be rejected because it is still compared against the stale `self.last_hr` (70). Consequently, the filter gets locked out indefinitely and will reject all future correct readings.
*   **Impact**: Loss of tracking until the application is restarted.

#### 2. Single-Threaded Blocking I/O
*   **Problem**: In `main.py` (lines 158-204), serial reading, binary parsing, console printing, and CSV logging run sequentially in a single loop.
*   **Obstacle**: If disk write operations, console printing, or complex parsing encounter any micro-delays, the execution loop pauses. This can cause the OS serial buffer to overflow, leading to dropped bytes and bad packets.
*   **Impact**: Increased `dropped_bytes` and packet parser resets.

#### 3. Missing Real-time Signal Visualization
*   **Problem**: Telemetry is only printed to the console as text or stored in CSV logs.
*   **Obstacle**: Developers and clinicians cannot visually inspect respiration and cardiac waveforms in real-time to assess signal quality or target alignment.
*   **Impact**: Hard to debug antenna positioning and environmental clutter.

---

## Version 1: Lockout Recovery, Threaded I/O & Real-time GUI (Completed)

*   **Lockout Recovery**: Implemented consecutive rejection limit of 10 to auto-reset the filter and prevent deadlock.
*   **Double-Buffered Threaded I/O**: Offloaded serial reading to a dedicated `SerialWorker` thread.
*   **Real-time Dashboard**: Developed Tkinter GUI featuring cardiac/respiration waveform plots, and vitals trend history.

---

## Version 2: Point Cloud Visualization, Range Jitter Mitigation, and Kalman Filtering (Completed)

*   **Point Cloud UI Visualization**: Decoded and plotted 2D coordinates (neon-green) at 20 Hz.
*   **Phase Coherence & DC Removal**: Compensated step offset jumps when switching bins.
*   **1D Kalman Filters**: Smoothened range bin jitter and vitals tracking.
*   **Range-gate Limiter**: Configured fixed bounding box ($0.3\text{ m} - 1.5\text{ m}$) on host.

---

## Version 3: Point Cloud Target Tracking, Interactive Range Lock, and Adaptive Kalman (Active)

We are transitioning to Version 3 to resolve the 1.4m tracking bias when the subject is at 40-50cm. The full plan is detailed in:
*   [Implementation Plan - Version 3](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/docs/implementation_plan_v3.md)

### Key Specifications:
1.  **Nearest-Cluster Priority (NCP)**: Parse point clouds to calculate centroid coordinates Y of the closest reflector group, overriding the DSP's wall reflection lock at 1.4m.
2.  **Interactive Range Lock GUI**: Add control inputs (Auto vs Manual Lock, Center, Span) on the sidebar.
3.  **Adaptive Kalman Filtering**: Adjust measurement covariance matrix R dynamically based on point density and deviation metrics.
