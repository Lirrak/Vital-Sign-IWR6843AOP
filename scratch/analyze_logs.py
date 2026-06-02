import csv
import json
import math
from collections import Counter

vital_path = r"c:\Users\Lirrak\Documents\Born Again\Radar Project\IWR6843AOP\Vital Sign\logs\vital_20260602_144613.csv"
tlv_path = r"c:\Users\Lirrak\Documents\Born Again\Radar Project\IWR6843AOP\Vital Sign\logs\tlv_summary_20260602_144613.csv"

def analyze_vital():
    print("--- ANALYZING VITAL LOG (V2 RUN 144613) ---")
    try:
        with open(vital_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    total_rows = len(rows)
    if total_rows == 0:
        print("No rows in vital log.")
        return

    print(f"Total entries: {total_rows}")

    # Times
    elapsed_times = [float(r['elapsed_s']) for r in rows if r['elapsed_s']]
    start_time = min(elapsed_times)
    end_time = max(elapsed_times)
    duration = end_time - start_time
    print(f"Start time: {start_time:.3f}s, End time: {end_time:.3f}s, Duration: {duration:.3f}s")

    # Frames
    frames = [int(r['frame_number']) for r in rows if r['frame_number']]
    start_frame = min(frames)
    end_frame = max(frames)
    expected_frames = (end_frame - start_frame) // 16 + 1
    actual_frames = len(set(frames))
    dropped_frames = expected_frames - actual_frames
    print(f"Frames range: {start_frame} to {end_frame}")
    print(f"Expected vital frames (decimated by 16): {expected_frames}")
    print(f"Actual vital frames received: {actual_frames}")
    print(f"Dropped vital frames: {dropped_frames} ({dropped_frames/expected_frames*100:.2f}%)")

    # Range Bins
    range_bins = [int(r['range_bin']) for r in rows if r['range_bin']]
    rb_counter = Counter(range_bins)
    print("\n--- RANGE BIN DISTRIBUTION ---")
    for rb, count in rb_counter.most_common():
        pct = count / total_rows * 100
        dist_m = rb * 0.04  # 4cm per bin
        print(f"  Range Bin {rb} (~{dist_m:.2f}m): {count} samples ({pct:.2f}%)")

    # Jumps in Range Bin
    transitions = 0
    for i in range(1, len(range_bins)):
        if range_bins[i] != range_bins[i-1]:
            transitions += 1
    print(f"Number of raw range bin transitions: {transitions}")

    # Filter validation
    filter_valid = [int(r['filter_valid']) for r in rows if r['filter_valid']]
    fv_counter = Counter(filter_valid)
    print("\n--- FILTER PERFORMANCE ---")
    for fv, count in fv_counter.items():
        pct = count / total_rows * 100
        status = "Valid" if fv == 1 else "Invalid/Rejected"
        print(f"  {status}: {count} samples ({pct:.2f}%)")

    reasons = [r['filter_reason'] for r in rows]
    reasons_counter = Counter(reasons)
    print("Rejection reasons / status:")
    for reason, count in reasons_counter.most_common():
        pct = count / total_rows * 100
        print(f"  {reason}: {count} samples ({pct:.2f}%)")

    def get_stats(data):
        if not data:
            return None
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std = math.sqrt(variance)
        return mean, std, min(data), max(data)

    # HR
    hr_raw = [float(r['heart_rate_raw_bpm']) for r in rows if r['heart_rate_raw_bpm']]
    hr_filt = [float(r['heart_rate_filtered_bpm']) for r in rows if r['heart_rate_filtered_bpm']]

    raw_hr_stats = get_stats(hr_raw)
    filt_hr_stats = get_stats(hr_filt)

    print("\n--- HEART RATE STATS ---")
    if raw_hr_stats:
        print(f"Raw HR: Mean={raw_hr_stats[0]:.2f}, Std={raw_hr_stats[1]:.2f}, Min={raw_hr_stats[2]:.2f}, Max={raw_hr_stats[3]:.2f}")
    if filt_hr_stats:
        print(f"Filtered HR: Mean={filt_hr_stats[0]:.2f}, Std={filt_hr_stats[1]:.2f}, Min={filt_hr_stats[2]:.2f}, Max={filt_hr_stats[3]:.2f}")
    else:
        print("Filtered HR: No valid samples output!")

    # BR
    br_raw = [float(r['breathing_rate_raw_bpm']) for r in rows if r['breathing_rate_raw_bpm']]
    br_filt = [float(r['breathing_rate_filtered_bpm']) for r in rows if r['breathing_rate_filtered_bpm']]

    raw_br_stats = get_stats(br_raw)
    filt_br_stats = get_stats(br_filt)

    print("\n--- BREATHING RATE STATS ---")
    if raw_br_stats:
        print(f"Raw BR: Mean={raw_br_stats[0]:.2f}, Std={raw_br_stats[1]:.2f}, Min={raw_br_stats[2]:.2f}, Max={raw_br_stats[3]:.2f}")
    if filt_br_stats:
        print(f"Filtered BR: Mean={filt_br_stats[0]:.2f}, Std={filt_br_stats[1]:.2f}, Min={filt_br_stats[2]:.2f}, Max={filt_br_stats[3]:.2f}")
    else:
        print("Filtered BR: No valid samples output!")

    # Breathing Deviation
    bd = [float(r['breathing_deviation']) for r in rows if r['breathing_deviation']]
    bd_stats = get_stats(bd)
    if bd_stats:
        print(f"\nBreathing Deviation: Mean={bd_stats[0]:.6f}, Std={bd_stats[1]:.6f}, Min={bd_stats[2]:.6f}, Max={bd_stats[3]:.6f}")

def analyze_tlv():
    print("\n--- TLV SUMMARY LOG ANALYSIS ---")
    try:
        with open(tlv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading TLV file: {e}")
        return

    total_rows = len(rows)
    print(f"Total TLV packets parsed: {total_rows}")
    
    tlv_type_counter = Counter()
    for r in rows:
        tlv_str = r.get('tlv_types_hex', '')
        if tlv_str:
            types = tlv_str.split(';')
            for t in types:
                if t.strip():
                    tlv_type_counter[t.strip()] += 1
                    
    for tlv_type, count in tlv_type_counter.items():
        name = "Unknown"
        if tlv_type == "0x3fc":
            name = "Tracker Target List"
        elif tlv_type == "0x3fd":
            name = "Tracker Target Index"
        elif tlv_type == "0x410":
            name = "Vital Signs"
        elif tlv_type == "0x3fb":
            name = "Tracker Point Cloud"
        elif tlv_type == "0x3f2":
            name = "Mapped Point Cloud"
        print(f"  TLV Type {tlv_type} ({name}): {count} occurrences")

if __name__ == "__main__":
    analyze_vital()
    analyze_tlv()
