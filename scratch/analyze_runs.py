import csv
import json
import statistics
import os

logs_dir = r"c:\Users\Lirrak\Documents\Born Again\Radar Project\IWR6843AOP\Vital Sign\logs"

def analyze_session(vital_file, tlv_file):
    print(f"==================================================")
    print(f"ANALYSIS FOR SESSION: {os.path.basename(vital_file)}")
    print(f"==================================================")
    
    # 1. Vital stats
    records = []
    with open(vital_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
            
    if not records:
        print("No vital records found.")
        return

    total_samples = len(records)
    elapsed_times = [float(r['elapsed_s']) for r in records if r['elapsed_s']]
    duration = max(elapsed_times) - min(elapsed_times) if elapsed_times else 0
    
    # Range bin distribution
    range_bins = [int(r['range_bin']) for r in records if r['range_bin']]
    bin_counts = {}
    for b in range_bins:
        bin_counts[b] = bin_counts.get(b, 0) + 1
        
    print(f"Total Duration: {duration:.2f} seconds")
    print(f"Total Vital Samples: {total_samples}")
    print("\nRange Bin Distribution:")
    for b in sorted(bin_counts.keys()):
        count = bin_counts[b]
        pct = (count / total_samples) * 100
        distance = b * 0.04
        print(f"  Bin {b:2d} ({distance:4.2f}m): {count:3d} samples ({pct:6.2f}%)")
        
    # Validity and Rejection reasons
    rejection_reasons = {}
    valid_count = 0
    invalid_count = 0
    for r in records:
        valid = int(r['filter_valid']) if r['filter_valid'] else 0
        if valid:
            valid_count += 1
        else:
            invalid_count += 1
            reason = r['filter_reason'] or 'unknown'
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            
    print(f"\nData Validity:")
    print(f"  Valid / Accepted Samples: {valid_count} ({valid_count/total_samples*100:.2f}%)")
    print(f"  Invalid / Rejected Samples: {invalid_count} ({invalid_count/total_samples*100:.2f}%)")
    print("  Rejection Reasons:")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"    - {reason}: {count} ({count/total_samples*100:.2f}%)")
        
    # Stats for Heart Rate
    hr_raw = [float(r['heart_rate_raw_bpm']) for r in records if r['heart_rate_raw_bpm']]
    hr_filt = [float(r['heart_rate_filtered_bpm']) for r in records if r['heart_rate_filtered_bpm']]
    
    print(f"\nHeart Rate Statistics (BPM):")
    if hr_raw:
        print(f"  Raw: Mean={sum(hr_raw)/len(hr_raw):.2f}, Std={statistics.stdev(hr_raw) if len(hr_raw)>1 else 0:.2f}, Min={min(hr_raw):.2f}, Max={max(hr_raw):.2f}")
    if hr_filt:
        print(f"  Filtered: Mean={sum(hr_filt)/len(hr_filt):.2f}, Std={statistics.stdev(hr_filt) if len(hr_filt)>1 else 0:.2f}, Min={min(hr_filt):.2f}, Max={max(hr_filt):.2f}")
        
    # Stats for Breathing Rate
    br_raw = [float(r['breathing_rate_raw_bpm']) for r in records if r['breathing_rate_raw_bpm']]
    br_filt = [float(r['breathing_rate_filtered_bpm']) for r in records if r['breathing_rate_filtered_bpm']]
    
    print(f"\nBreathing Rate Statistics (BPM):")
    if br_raw:
        print(f"  Raw: Mean={sum(br_raw)/len(br_raw):.2f}, Std={statistics.stdev(br_raw) if len(br_raw)>1 else 0:.2f}, Min={min(br_raw):.2f}, Max={max(br_raw):.2f}")
    if br_filt:
        print(f"  Filtered: Mean={sum(br_filt)/len(br_filt):.2f}, Std={statistics.stdev(br_filt) if len(br_filt)>1 else 0:.2f}, Min={min(br_filt):.2f}, Max={max(br_filt):.2f}")

    # TLV Packet Count
    tlv_counts = {}
    total_frames = 0
    if os.path.exists(tlv_file):
        with open(tlv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_frames += 1
                types = row['tlv_types_hex'].split(';')
                for t in types:
                    if t:
                        tlv_counts[t] = tlv_counts.get(t, 0) + 1
                        
        print(f"\nTLV Frame Statistics:")
        print(f"  Total TLV Frames: {total_frames}")
        for t, count in sorted(tlv_counts.items()):
            desc = ""
            if t == "0x3fd": desc = "Tracker Target Index"
            elif t == "0x3fc": desc = "Tracker Target List"
            elif t == "0x3f2": desc = "Mapped Point Cloud"
            elif t == "0x3f3": desc = "Point Cloud Side Info"
            elif t == "0x410": desc = "Vital Signs"
            pct = (count / total_frames) * 100
            print(f"  - {t} ({desc}): {count} packets ({pct:.2f}%)")
    else:
        print("\nTLV summary file not found.")

def main():
    # Session 144857
    v_144857 = os.path.join(logs_dir, "vital_20260602_144857.csv")
    t_144857 = os.path.join(logs_dir, "tlv_summary_20260602_144857.csv")
    if os.path.exists(v_144857):
        analyze_session(v_144857, t_144857)
        
    # Session 151115
    v_151115 = os.path.join(logs_dir, "vital_20260602_151115.csv")
    t_151115 = os.path.join(logs_dir, "tlv_summary_20260602_151115.csv")
    if os.path.exists(v_151115):
        analyze_session(v_151115, t_151115)

    # Session 155208 (Newest Run)
    v_155208 = os.path.join(logs_dir, "vital_20260602_155208.csv")
    t_155208 = os.path.join(logs_dir, "tlv_summary_20260602_155208.csv")
    if os.path.exists(v_155208):
        analyze_session(v_155208, t_155208)

if __name__ == '__main__':
    main()
