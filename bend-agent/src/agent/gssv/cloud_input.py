"""GSSV 云端 WebRTC input DataChannel 二进制格式（对照 libxsrp sendInputPacket）。"""

from __future__ import annotations

import struct
import time
from enum import IntFlag
from typing import Any, Dict, List, Optional


class InputReportType(IntFlag):
    """Input packet report type 位标志。"""

    NONE = 0
    METADATA = 0x02
    GAMEPAD_REPORT = 0x04
    CLIENT_METADATA = 0x08


def _scale_trigger(value: int) -> int:
    """0-255 扳机值映射到 uint16（与 SmartGlass/xsrp 一致）。"""
    value = int(value or 0)
    if value <= 255:
        return value * 128
    return min(value, 65535)


def gamepad_dict_to_report(gamepad_data: Dict[str, Any], *, index: int = 0) -> Dict[str, int]:
    """将 Agent gamepad_data 映射为 sendInputPacket 字段。"""
    return {
        "gamepad_index": index,
        "buttons": int(gamepad_data.get("buttons", 0)) & 0xFFFF,
        "left_thumb_x": int(gamepad_data.get("left_thumb_x", 0)),
        "left_thumb_y": int(gamepad_data.get("left_thumb_y", 0)),
        "right_thumb_x": int(gamepad_data.get("right_thumb_x", 0)),
        "right_thumb_y": int(gamepad_data.get("right_thumb_y", 0)),
        "left_trigger": _scale_trigger(gamepad_data.get("left_trigger", 0)),
        "right_trigger": _scale_trigger(gamepad_data.get("right_trigger", 0)),
    }


def pack_input_packet(
    *,
    sequence: int,
    elapsed_ms: int,
    gamepads: Optional[List[Dict[str, int]]] = None,
    client_metadata: bool = False,
) -> bytes:
    """
    打包 input DataChannel 二进制包。

    布局（libxsrp XboxSeries::sendInputPacket）：
    - uint16 report_type
    - uint32 sequence
    - uint64 elapsed_ms
    - [uint8 max_points=2]  (ClientMetadata)
    - [uint8 count + N*28 metadata frames]
    - [uint8 count + N*23 gamepad reports]
    """
    gamepads = gamepads or []
    report_type = int(InputReportType.NONE)
    total_size = 14

    if client_metadata:
        report_type |= int(InputReportType.CLIENT_METADATA)
        total_size += 1

    if gamepads:
        report_type |= int(InputReportType.GAMEPAD_REPORT)
        total_size += 1 + len(gamepads) * 23

    buf = bytearray(total_size)
    offset = 0

    struct.pack_into("<H", buf, offset, report_type)
    offset += 2
    struct.pack_into("<I", buf, offset, int(sequence) & 0xFFFFFFFF)
    offset += 4
    struct.pack_into("<Q", buf, offset, int(elapsed_ms) & 0xFFFFFFFFFFFFFFFF)
    offset += 8

    if client_metadata:
        buf[offset] = 2
        offset += 1

    if gamepads:
        buf[offset] = len(gamepads) & 0xFF
        offset += 1
        for pad in gamepads:
            struct.pack_into("<B", buf, offset, int(pad.get("gamepad_index", 0)) & 0xFF)
            offset += 1
            struct.pack_into("<H", buf, offset, int(pad.get("buttons", 0)) & 0xFFFF)
            offset += 2
            struct.pack_into("<h", buf, offset, int(pad.get("left_thumb_x", 0)))
            offset += 2
            struct.pack_into("<h", buf, offset, int(pad.get("left_thumb_y", 0)))
            offset += 2
            struct.pack_into("<h", buf, offset, int(pad.get("right_thumb_x", 0)))
            offset += 2
            struct.pack_into("<h", buf, offset, int(pad.get("right_thumb_y", 0)))
            offset += 2
            struct.pack_into("<H", buf, offset, int(pad.get("left_trigger", 0)) & 0xFFFF)
            offset += 2
            struct.pack_into("<H", buf, offset, int(pad.get("right_trigger", 0)) & 0xFFFF)
            offset += 2
            struct.pack_into("<I", buf, offset, 0)
            offset += 4
            struct.pack_into("<I", buf, offset, 0)
            offset += 4

    return bytes(buf)


class CloudInputSender:
    """维护序列号与时间基准，生成 input 包。"""

    def __init__(self):
        self._sequence = 0
        self._birth = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._birth) * 1000)

    def next_gamepad_packet(self, gamepad_data: Dict[str, Any]) -> bytes:
        packet = pack_input_packet(
            sequence=self._sequence,
            elapsed_ms=self.elapsed_ms,
            gamepads=[gamepad_dict_to_report(gamepad_data)],
        )
        self._sequence += 1
        return packet

    def client_metadata_packet(self) -> bytes:
        packet = pack_input_packet(
            sequence=self._sequence,
            elapsed_ms=self.elapsed_ms,
            client_metadata=True,
        )
        self._sequence += 1
        return packet

    def neutral_gamepad_packet(self) -> bytes:
        return self.next_gamepad_packet(
            {
                "buttons": 0,
                "left_trigger": 0,
                "right_trigger": 0,
                "left_thumb_x": 0,
                "left_thumb_y": 0,
                "right_thumb_x": 0,
                "right_thumb_y": 0,
            }
        )
