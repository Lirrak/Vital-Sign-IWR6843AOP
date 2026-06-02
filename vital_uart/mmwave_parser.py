from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"
HEADER_LEN = 40
HEADER_STRUCT = struct.Struct("<8s8I")
TLV_HEADER_STRUCT = struct.Struct("<II")

# TI Vital Signs With People Tracking commonly uses this custom TLV.
TLV_TYPE_VITAL_SIGNS = 0x410
TLV_TYPE_POINT_CLOUD = 0x3f2
VITAL_PAYLOAD_LEN_PRIMARY = 136


@dataclass
class PacketHeader:
    version: int
    total_packet_len: int
    platform: int
    frame_number: int
    time_cpu_cycles: int
    num_detected_obj: int
    num_tlvs: int
    sub_frame_number: int


@dataclass
class VitalSignData:
    frame_number: int
    target_id: int
    range_bin: int
    breathing_deviation: float
    heart_rate_bpm: float
    breathing_rate_bpm: float
    heart_circular_buffer: List[float] = field(default_factory=list)
    breath_circular_buffer: List[float] = field(default_factory=list)
    tlv_length: int = 0
    parser_variant: str = ""


@dataclass
class ParsedTLV:
    tlv_type: int
    tlv_length: int
    payload_length: int
    payload_offset: int


@dataclass
class ParsedPacket:
    header: PacketHeader
    tlvs: List[ParsedTLV]
    vital_signs: List[VitalSignData]
    point_cloud: List[Tuple[float, float, float, float]] = field(default_factory=list)
    unknown_tlv_types: List[int] = field(default_factory=list)


class MmWaveFrameParser:
    """
    Stateful parser for mmWave UART binary stream.

    It searches for the standard magic word, extracts full packets using
    totalPacketLen, and decodes TLVs. Unknown TLVs are safely skipped.
    """

    def __init__(self, max_packet_len: int = 65535):
        self.buffer = bytearray()
        self.max_packet_len = max_packet_len
        self.total_bytes_seen = 0
        self.dropped_bytes = 0
        self.bad_packets = 0

    def feed(self, data: bytes) -> List[ParsedPacket]:
        self.total_bytes_seen += len(data)
        self.buffer.extend(data)
        packets: List[ParsedPacket] = []

        while True:
            packet_bytes = self._extract_one_packet()
            if packet_bytes is None:
                break
            try:
                packets.append(parse_packet(packet_bytes))
            except Exception as exc:
                self.bad_packets += 1
                print(f"[WARN] Bad packet skipped: {exc}")

        return packets

    def _extract_one_packet(self) -> Optional[bytes]:
        magic_idx = self.buffer.find(MAGIC_WORD)

        if magic_idx < 0:
            # Keep last len(MAGIC_WORD)-1 bytes in case they are a partial magic word.
            keep = len(MAGIC_WORD) - 1
            if len(self.buffer) > keep:
                self.dropped_bytes += len(self.buffer) - keep
                del self.buffer[:-keep]
            return None

        if magic_idx > 0:
            self.dropped_bytes += magic_idx
            del self.buffer[:magic_idx]

        if len(self.buffer) < HEADER_LEN:
            return None

        total_packet_len = struct.unpack_from("<I", self.buffer, 12)[0]

        if total_packet_len < HEADER_LEN or total_packet_len > self.max_packet_len:
            # Not a real header. Drop one byte and search again.
            self.dropped_bytes += 1
            del self.buffer[0]
            return None

        if len(self.buffer) < total_packet_len:
            return None

        packet = bytes(self.buffer[:total_packet_len])
        del self.buffer[:total_packet_len]
        return packet


def parse_packet(packet: bytes) -> ParsedPacket:
    if len(packet) < HEADER_LEN:
        raise ValueError(f"Packet too short: {len(packet)} bytes")

    magic, version, total_packet_len, platform, frame_number, time_cpu_cycles, \
        num_detected_obj, num_tlvs, sub_frame_number = HEADER_STRUCT.unpack_from(packet, 0)

    if magic != MAGIC_WORD:
        raise ValueError("Magic word mismatch")
    if total_packet_len != len(packet):
        raise ValueError(f"Length mismatch: header={total_packet_len}, actual={len(packet)}")

    header = PacketHeader(
        version=version,
        total_packet_len=total_packet_len,
        platform=platform,
        frame_number=frame_number,
        time_cpu_cycles=time_cpu_cycles,
        num_detected_obj=num_detected_obj,
        num_tlvs=num_tlvs,
        sub_frame_number=sub_frame_number,
    )

    tlvs: List[ParsedTLV] = []
    vital_signs: List[VitalSignData] = []
    point_cloud: List[Tuple[float, float, float, float]] = []
    unknown_tlv_types: List[int] = []
    offset = HEADER_LEN

    for _ in range(num_tlvs):
        if offset + TLV_HEADER_STRUCT.size > len(packet):
            break

        tlv_type, tlv_length = TLV_HEADER_STRUCT.unpack_from(packet, offset)
        payload_start, payload_len, consumed_len = _resolve_tlv_payload_bounds(
            packet_len=len(packet), tlv_offset=offset, tlv_length=tlv_length
        )
        payload = packet[payload_start: payload_start + payload_len]

        tlvs.append(
            ParsedTLV(
                tlv_type=tlv_type,
                tlv_length=tlv_length,
                payload_length=payload_len,
                payload_offset=payload_start,
            )
        )

        if tlv_type == TLV_TYPE_VITAL_SIGNS:
            vital = parse_vital_sign_payload(
                payload=payload,
                frame_number=frame_number,
                tlv_length=tlv_length,
            )
            if vital is not None:
                vital_signs.append(vital)
        elif tlv_type == TLV_TYPE_POINT_CLOUD:
            point_cloud = parse_point_cloud_payload(payload)
        else:
            unknown_tlv_types.append(tlv_type)

        offset += consumed_len

    return ParsedPacket(
        header=header,
        tlvs=tlvs,
        vital_signs=vital_signs,
        point_cloud=point_cloud,
        unknown_tlv_types=unknown_tlv_types,
    )


def _resolve_tlv_payload_bounds(packet_len: int, tlv_offset: int, tlv_length: int) -> Tuple[int, int, int]:
    """
    Most mmWave demos store tlv_length as payload length, excluding the 8-byte TLV header.
    Some custom labs/loggers may treat it as total TLV length. This function accepts both.
    """
    payload_start = tlv_offset + TLV_HEADER_STRUCT.size
    remaining_after_header = packet_len - payload_start

    # Preferred/common case: tlv_length is payload length.
    if 0 <= tlv_length <= remaining_after_header:
        return payload_start, tlv_length, TLV_HEADER_STRUCT.size + tlv_length

    # Fallback: tlv_length includes TLV header.
    if tlv_length >= TLV_HEADER_STRUCT.size:
        payload_len = tlv_length - TLV_HEADER_STRUCT.size
        if 0 <= payload_len <= remaining_after_header:
            return payload_start, payload_len, tlv_length

    raise ValueError(
        f"Invalid TLV length at offset={tlv_offset}: tlv_length={tlv_length}, "
        f"remaining_after_header={remaining_after_header}"
    )


def parse_vital_sign_payload(payload: bytes, frame_number: int, tlv_length: int) -> Optional[VitalSignData]:
    """
    Decode Vital Signs TLV 0x410.

    Common TI layout for 136-byte payload:
        uint16 target_id
        uint16 range_bin
        float  breathing_deviation
        float  heart_rate_bpm
        float  breathing_rate_bpm
        float[15] heart circular buffer / waveform-like data
        float[15] breath circular buffer / waveform-like data

    A fallback 32-bit ID/range variant is included for compatibility with modified firmware.
    """
    candidates: List[VitalSignData] = []

    primary = _parse_vital_primary_u16(payload, frame_number, tlv_length)
    if primary is not None:
        candidates.append(primary)

    fallback = _parse_vital_fallback_u32(payload, frame_number, tlv_length)
    if fallback is not None:
        candidates.append(fallback)

    if not candidates:
        return None

    candidates.sort(key=_score_vital_candidate, reverse=True)
    return candidates[0]


def _parse_vital_primary_u16(payload: bytes, frame_number: int, tlv_length: int) -> Optional[VitalSignData]:
    if len(payload) < 16:
        return None

    try:
        target_id, range_bin, breathing_dev, heart_rate, breathing_rate = struct.unpack_from("<HHfff", payload, 0)
    except struct.error:
        return None

    floats = _unpack_float_list(payload[16:])
    heart_buffer = floats[:15]
    breath_buffer = floats[15:30]

    return VitalSignData(
        frame_number=frame_number,
        target_id=target_id,
        range_bin=range_bin,
        breathing_deviation=breathing_dev,
        heart_rate_bpm=heart_rate,
        breathing_rate_bpm=breathing_rate,
        heart_circular_buffer=heart_buffer,
        breath_circular_buffer=breath_buffer,
        tlv_length=tlv_length,
        parser_variant="u16_id_range_primary",
    )


def _parse_vital_fallback_u32(payload: bytes, frame_number: int, tlv_length: int) -> Optional[VitalSignData]:
    if len(payload) < 20:
        return None

    try:
        target_id, range_bin, breathing_dev, heart_rate, breathing_rate = struct.unpack_from("<IIfff", payload, 0)
    except struct.error:
        return None

    floats = _unpack_float_list(payload[20:])
    half = len(floats) // 2
    heart_buffer = floats[:half]
    breath_buffer = floats[half:]

    return VitalSignData(
        frame_number=frame_number,
        target_id=target_id,
        range_bin=range_bin,
        breathing_deviation=breathing_dev,
        heart_rate_bpm=heart_rate,
        breathing_rate_bpm=breathing_rate,
        heart_circular_buffer=heart_buffer,
        breath_circular_buffer=breath_buffer,
        tlv_length=tlv_length,
        parser_variant="u32_id_range_fallback",
    )


def _unpack_float_list(data: bytes) -> List[float]:
    n = len(data) // 4
    if n <= 0:
        return []
    return list(struct.unpack_from("<" + "f" * n, data, 0))


def _finite(value: float) -> bool:
    return isinstance(value, float) and math.isfinite(value)


def _score_vital_candidate(v: VitalSignData) -> int:
    score = 0

    if 0 <= v.target_id <= 255:
        score += 2
    if 0 <= v.range_bin <= 2048:
        score += 2
    if _finite(v.breathing_deviation) and abs(v.breathing_deviation) < 1e4:
        score += 2
    if _finite(v.heart_rate_bpm):
        score += 1
        if 30 <= v.heart_rate_bpm <= 220 or v.heart_rate_bpm == 0:
            score += 4
    if _finite(v.breathing_rate_bpm):
        score += 1
        if 4 <= v.breathing_rate_bpm <= 60 or v.breathing_rate_bpm == 0:
            score += 4
    if len(v.heart_circular_buffer) >= 10:
        score += 1
    if len(v.breath_circular_buffer) >= 10:
        score += 1

    return score


def parse_point_cloud_payload(payload: bytes) -> List[Tuple[float, float, float, float]]:
    """
    Decode Point Cloud TLV 0x3f2.
    Each point represents 4 floats: x, y, z, velocity (16 bytes).
    """
    points = []
    num_points = len(payload) // 16
    for i in range(num_points):
        try:
            x, y, z, vel = struct.unpack_from("<4f", payload, i * 16)
            points.append((x, y, z, vel))
        except struct.error:
            break
    return points
