import struct

raw_bin_path = r"c:\Users\Lirrak\Documents\Born Again\Radar Project\IWR6843AOP\Vital Sign\logs\raw_uart_20260602_142351.bin"
MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"
HEADER_LEN = 40

def inspect_bin():
    print(f"Reading raw binary: {raw_bin_path}")
    try:
        with open(raw_bin_path, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"Total binary size: {len(data)} bytes")
    
    offset = 0
    packets_found = 0
    tlv_sizes_3f2 = []
    
    while True:
        idx = data.find(MAGIC_WORD, offset)
        if idx < 0:
            break
        
        if len(data) - idx < HEADER_LEN:
            break
            
        magic, version, total_packet_len, platform, frame_number, time_cpu_cycles, \
            num_detected_obj, num_tlvs, sub_frame_number = struct.unpack_from("<8s8I", data, idx)
            
        if idx + total_packet_len > len(data):
            # Partial packet at the end
            break
            
        packet_bytes = data[idx : idx + total_packet_len]
        
        # Parse TLVs in this packet
        tlv_offset = HEADER_LEN
        for _ in range(num_tlvs):
            if tlv_offset + 8 > len(packet_bytes):
                break
            tlv_type, tlv_len = struct.unpack_from("<II", packet_bytes, tlv_offset)
            
            # Normal mmWave SDK payload is starting after the 8-byte TLV header
            # tlv_len is typically payload length. Let's see if 3f2 is here
            if tlv_type == 0x3f2:
                tlv_sizes_3f2.append(tlv_len)
                if len(tlv_sizes_3f2) <= 5:
                    print(f"Frame {frame_number}: Found TLV 0x3f2, tlv_length={tlv_len}")
                    # Print the first 32 bytes of the payload
                    payload_start = tlv_offset + 8
                    payload = packet_bytes[payload_start: payload_start + min(tlv_len, 64)]
                    print(f"  First 32 bytes of payload hex: {payload[:32].hex()}")
                    # Let's see if it's multiple of 16 (float point cloud) or 8 (compressed int16 point cloud) or 20 (point cloud + SNR)
                    if tlv_len % 16 == 0:
                        print(f"  tlv_length is divisible by 16 ({tlv_len // 16} points of 16-bytes float?)")
                        # Try to unpack first point as 4 floats (x, y, z, velocity)
                        if tlv_len >= 16:
                            x, y, z, vel = struct.unpack_from("<4f", payload, 0)
                            print(f"  Unpacked as 4f: x={x:.4f}, y={y:.4f}, z={z:.4f}, vel={vel:.4f}")
                    if tlv_len % 8 == 0:
                        print(f"  tlv_length is divisible by 8 ({tlv_len // 8} points of 8-bytes int16?)")
                        # Try to unpack first point as 4 int16
                        if tlv_len >= 8:
                            x, y, z, vel = struct.unpack_from("<4h", payload, 0)
                            print(f"  Unpacked as 4h: x={x}, y={y}, z={z}, vel={vel}")
                    if tlv_len % 20 == 0:
                        print(f"  tlv_length is divisible by 20 ({tlv_len // 20} points of 20-bytes?)")
            
            # Move to next TLV
            # Usually consumed length is tlv_len + 8
            tlv_offset += 8 + tlv_len
            
        offset = idx + total_packet_len
        packets_found += 1
        
    print(f"Processed {packets_found} packets.")
    if tlv_sizes_3f2:
        print(f"Found {len(tlv_sizes_3f2)} instances of TLV 0x3f2. Lengths: {set(tlv_sizes_3f2)}")

if __name__ == "__main__":
    inspect_bin()
