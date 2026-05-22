from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import List, Optional


MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"
HEADER_LEN = 40
TLV_HEADER_LEN = 8
VITAL_SIGNS_TLV_TYPE = 0x410
VITAL_SIGNS_PAYLOAD_LEN = 136
VITAL_SIGNS_STRUCT = struct.Struct("<HHfff15f15f")


@dataclass
class FrameHeader:
    version: int
    total_packet_len: int
    platform: int
    frame_number: int
    time_cpu_cycles: int
    num_detected_obj: int
    num_tlvs: int
    subframe_number: int


@dataclass
class VitalSignsSample:
    timestamp_s: float
    frame_number: int
    target_id: int
    range_bin: int
    breathing_deviation: float
    heart_rate_bpm: float
    breathing_rate_bpm: float
    heart_waveform: List[float] = field(default_factory=list)
    breath_waveform: List[float] = field(default_factory=list)

    @property
    def heart_rate_valid(self) -> bool:
        return math.isfinite(self.heart_rate_bpm) and 25.0 <= self.heart_rate_bpm <= 240.0

    @property
    def breathing_rate_valid(self) -> bool:
        return math.isfinite(self.breathing_rate_bpm) and 2.0 <= self.breathing_rate_bpm <= 80.0


class MmwavePacketParser:
    """Streaming parser for TI mmWave UART TLV frames.

    This parser targets the IWR6843AOP Vital Signs With People Tracking demo.
    It looks for the standard mmWave magic word, parses the frame header,
    then extracts TLV type 0x410 as a VitalSignsSample.
    """

    def __init__(self, max_buffer_size: int = 1_000_000) -> None:
        self.buffer = bytearray()
        self.max_buffer_size = max_buffer_size
        self.frames_seen = 0
        self.vital_tlvs_seen = 0
        self.bytes_dropped = 0
        self.last_error: str = ""

    def append(self, data: bytes, timestamp_s: float) -> List[VitalSignsSample]:
        if not data:
            return []

        self.buffer.extend(data)
        if len(self.buffer) > self.max_buffer_size:
            drop_len = len(self.buffer) - self.max_buffer_size
            del self.buffer[:drop_len]
            self.bytes_dropped += drop_len
            self.last_error = f"Buffer too large; dropped {drop_len} bytes"

        samples: List[VitalSignsSample] = []

        while True:
            magic_index = self.buffer.find(MAGIC_WORD)
            if magic_index < 0:
                # Keep a small tail in case the magic word is split between reads.
                keep = len(MAGIC_WORD) - 1
                if len(self.buffer) > keep:
                    self.bytes_dropped += len(self.buffer) - keep
                    del self.buffer[:-keep]
                return samples

            if magic_index > 0:
                self.bytes_dropped += magic_index
                del self.buffer[:magic_index]

            if len(self.buffer) < HEADER_LEN:
                return samples

            try:
                header_values = struct.unpack_from("<8I", self.buffer, 8)
            except struct.error as exc:
                self.last_error = f"Header unpack error: {exc}"
                return samples

            header = FrameHeader(*header_values)

            # Basic sanity checks. Wrong baud rate or wrong firmware usually fails here.
            if header.total_packet_len < HEADER_LEN or header.total_packet_len > 200_000:
                self.last_error = (
                    f"Invalid packet length {header.total_packet_len}; "
                    "resyncing on next byte"
                )
                self.bytes_dropped += 1
                del self.buffer[0]
                continue

            if len(self.buffer) < header.total_packet_len:
                return samples

            packet = bytes(self.buffer[: header.total_packet_len])
            del self.buffer[: header.total_packet_len]
            self.frames_seen += 1
            samples.extend(self._parse_packet(packet, header, timestamp_s))

    def _parse_packet(
        self, packet: bytes, header: FrameHeader, timestamp_s: float
    ) -> List[VitalSignsSample]:
        samples: List[VitalSignsSample] = []
        offset = HEADER_LEN

        for _ in range(header.num_tlvs):
            if offset + TLV_HEADER_LEN > len(packet):
                self.last_error = "TLV header exceeds packet length"
                break

            tlv_type, tlv_length = struct.unpack_from("<II", packet, offset)

            # Most mmWave demos use TLV length as payload length. Some user-modified
            # firmware may use total TLV length, so this block accepts both.
            payload_start = offset + TLV_HEADER_LEN
            payload_end_payload_len = payload_start + tlv_length
            payload_end_total_len = offset + tlv_length

            if payload_end_payload_len <= len(packet):
                payload = packet[payload_start:payload_end_payload_len]
                next_offset = payload_end_payload_len
            elif tlv_length >= TLV_HEADER_LEN and payload_end_total_len <= len(packet):
                payload = packet[payload_start:payload_end_total_len]
                next_offset = payload_end_total_len
            else:
                self.last_error = (
                    f"TLV length invalid: type=0x{tlv_type:X}, length={tlv_length}, "
                    f"remaining={len(packet) - offset}"
                )
                break

            if tlv_type == VITAL_SIGNS_TLV_TYPE:
                sample = self._parse_vital_signs_payload(payload, header, timestamp_s)
                if sample is not None:
                    samples.append(sample)
                    self.vital_tlvs_seen += 1

            offset = next_offset

        return samples

    def _parse_vital_signs_payload(
        self, payload: bytes, header: FrameHeader, timestamp_s: float
    ) -> Optional[VitalSignsSample]:
        if len(payload) < VITAL_SIGNS_PAYLOAD_LEN:
            self.last_error = (
                f"Vital Signs TLV too short: {len(payload)} bytes, "
                f"expected at least {VITAL_SIGNS_PAYLOAD_LEN}"
            )
            return None

        values = VITAL_SIGNS_STRUCT.unpack_from(payload, 0)
        target_id = int(values[0])
        range_bin = int(values[1])
        breathing_deviation = float(values[2])
        heart_rate_bpm = float(values[3])
        breathing_rate_bpm = float(values[4])
        heart_waveform = [float(v) for v in values[5:20]]
        breath_waveform = [float(v) for v in values[20:35]]

        return VitalSignsSample(
            timestamp_s=timestamp_s,
            frame_number=header.frame_number,
            target_id=target_id,
            range_bin=range_bin,
            breathing_deviation=breathing_deviation,
            heart_rate_bpm=heart_rate_bpm,
            breathing_rate_bpm=breathing_rate_bpm,
            heart_waveform=heart_waveform,
            breath_waveform=breath_waveform,
        )
