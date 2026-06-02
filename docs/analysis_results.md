# Analysis Results & Pre-Run Code Review

This document contains a detailed analysis of the binary data structures streamed by the TI IWR6843AOP radar, a breakdown of the vital signs TLV payload, and a comprehensive code review to identify potential optimizations and verify correctness before execution.

---

## 1. Stream & Packet Structure Analysis

The IWR6843AOP Vital Signs with People Tracking application streams data packets over UART at 921600 baud. The structure of these packets is outlined below.

```
┌─────────────────────────────────────────────────────────────┐
│                      Packet Header                          │
│  Magic Word (8B) | Version (4B) | Total Length (4B) | ...   │
├─────────────────────────────────────────────────────────────┤
│                      TLV Header 1                           │
│             Type (4B)   |   Length (4B)                     │
├─────────────────────────────────────────────────────────────┤
│                      TLV Payload 1                          │
│             (Variable Length Value Data)                    │
├─────────────────────────────────────────────────────────────┤
│                      TLV Header 2...                        │
└─────────────────────────────────────────────────────────────┘
```

### Packet Header
Parsed in `mmwave_parser.py` (lines 10-12, 131-148), the header is 40 bytes long and matches the standard TI format:
*   **Magic Word** (8 bytes): `0x0201040306050807`
*   **Version** (4 bytes): Product/firmware release version.
*   **Total Packet Length** (4 bytes): Used by the stateful parser to slice the incoming byte stream cleanly.
*   **Platform** (4 bytes): Device identifier (e.g., `0xA6843` for IWR6843).
*   **Frame Number** (4 bytes): Monotonically increasing counter, used for drop-out detection.
*   **Number of TLVs** (4 bytes): Tells the parser how many TLV chunks follow.

---

## 2. Vital Signs TLV Payload Analysis (Type `0x410`)

The parser decodes TLV Type `0x410` (defined in `mmwave_parser.py` as `TLV_TYPE_VITAL_SIGNS`). There are two primary packet variants seen in different TI firmware versions:

### Variant A: Primary Format (`u16_id_range_primary`)
Total payload size is typically **136 bytes**.
*   **Target ID** (2 bytes, `uint16`): The tracking ID of the person (e.g. 0, 1, 2).
*   **Range Bin** (2 bytes, `uint16`): The range bin index where the chest is located.
*   **Breathing Deviation** (4 bytes, `float`): Measures standard deviation of the respiration signal. Higher values denote breathing abnormalities or movement.
*   **Heart Rate (Raw)** (4 bytes, `float`): Calculated on-chip heart rate in BPM.
*   **Breathing Rate (Raw)** (4 bytes, `float`): Calculated on-chip breathing rate in BPM.
*   **Heart Circular Buffer** (60 bytes, 15x `float`): A rolling history of the filtered cardiac phase values, representing the heart waveform.
*   **Breath Circular Buffer** (60 bytes, 15x `float`): A rolling history of the filtered respiration phase values, representing the breathing waveform.

### Variant B: Fallback Format (`u32_id_range_fallback`)
Used in some custom firmwares.
*   **Target ID** (4 bytes, `uint32`)
*   **Range Bin** (4 bytes, `uint32`)
*   *Other fields are identical, but offset by +4 bytes.*

---

## 3. Pre-Run Code Review

We analyzed the python scripts in the project to verify their safety, efficiency, and logical correctness.

### 1. Robust Parser Candidate Selection (`mmwave_parser.py`)
*   **Praise**: The parser handles both U16 and U32 ID/Range structures dynamically by executing both parsing routines and ranking the output quality using `_score_vital_candidate`.
*   **Security/Safety**: The helper function `_resolve_tlv_payload_bounds` uses defensive bounds checking:
    ```python
    if 0 <= tlv_length <= remaining_after_header:
        return payload_start, tlv_length, TLV_HEADER_STRUCT.size + tlv_length
    ```
    This prevents `IndexError` or memory exhaustion vulnerabilities when parsing corrupted serial streams.

### 2. Code Defect: Lockout Bug in `RobustVitalFilter` (`vital_filter.py`)
*   **Location**: Line 91-94.
*   **Details**: The absolute jump validator prevents spikes by comparing the current input `hr` with the `self.last_hr`. If the input is invalid (due to a real physiological change or target switch), it gets rejected. Since `self.last_hr` is only updated when a sample is accepted, the filter gets stuck with a stale `self.last_hr` and rejects all future valid samples.
*   **Fix Recommendation**: Add a timeout or a consecutive rejection counter to reset the filter.

### 3. File Handler Management (`csv_logger.py`)
*   **Praise**: Implements Python's context manager interface (`__enter__` and `__exit__`), guaranteeing that files are cleanly closed when the program exits, preventing resource leaks.
*   **Optimization**: CSV logging uses `DictWriter` and calls `.flush()` immediately after writing (lines 80 and 109). While this prevents data loss during sudden disconnects, it creates frequent disk writes. For extreme long-term runs, buffering with periodic flushes is recommended.

### 4. Serial Buffer Setup (`main.py`)
*   **Observation**: In `main.py` line 166:
    ```python
    chunk = data_ser.read(args.read_size)
    ```
    `args.read_size` defaults to **4096 bytes** (specified in `app_config.py`).
*   **Analysis**: Reading 4096 bytes at a time with a timeout of 0.2s is suitable for high-baud data streams. However, if the radar streams packets at 20 Hz (~2-3 KB/s), the parser will wait for the buffer to fill or time out before parsing, leading to bursty/jittery real-time outputs.
*   **Recommendation**: For real-time plotting, reduce `READ_SIZE` in `app_config.py` to **512** or **1024** to parse and display data with lower latency.

---

## 4. Live Session Analysis Log

All detailed reports of actual test sessions are documented version-by-version here:
*   [Analysis Results - Version 1 (2026-06-02 Run)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/docs/analysis_results_v1.md): Evaluates range bin instability (jumping 25 times in 3 minutes) and the baseline median-filter lockout limitations.
*   [Analysis Results - Version 2 (2026-06-02 Run)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/docs/analysis_results_v2.md): Analyzes the performance of 1D Kalman Filters, range-gate limiter (0.3m-1.5m), bin-jump gating, and the neon-green Point Cloud layout.
*   [Analysis Results - Version 3 (2026-06-02 Run)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/docs/analysis_results_v3.md): Evaluates the Nearest-Cluster Priority (NCP) Point Cloud tracking algorithm, Adaptive Kalman Filtering, range-gate limiter, and identifies the Centroid Jittering limitation.
