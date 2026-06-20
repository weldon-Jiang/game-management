"""GSSV 云端 WebRTC input DataChannel 二进制格式（对照 libxsrp sendInputPacket）。"""

from __future__ import annotations

import struct
import threading
import time
from dataclasses import dataclass
from enum import IntFlag
from typing import Any, Dict, List, Optional


class InputReportType(IntFlag):
    """Input packet report type（对齐 libxsrp common/xsrpconfig.h InputReportType）。"""

    NONE = 0
    METADATA = 1
    GAMEPAD_REPORT = 2
    CLIENT_METADATA = 8


def _scale_trigger(value: int) -> int:
    """0-255 扳机值映射到 uint16（与 SmartGlass/xsrp 一致）。"""
    value = int(value or 0)
    if value <= 255:
        return value * 128
    return min(value, 65535)


@dataclass
class InputFrameMeta:
    """对齐 libxsrp XsFrame → sendInputPacket METADATA 段（7×uint32）。"""

    server_data_key: int
    first_arrival_ms: int
    submitted_ms: int
    decoded_ms: int
    rendered_ms: int


class InputFrameSyncQueue:
    """
    视频帧 → input METADATA 同步队列（对齐 libxsrp H264FramePool::PopFrames）。

    xCloud 要求 gamepad 包附带已解码帧 timing，否则云端会忽略输入。
    """

    def __init__(self, birth_monotonic: Optional[float] = None):
        self._birth = birth_monotonic if birth_monotonic is not None else time.monotonic()
        self._queue: List[InputFrameMeta] = []
        self._lock = threading.Lock()

    def reset(self, birth_monotonic: Optional[float] = None) -> None:
        with self._lock:
            self._queue.clear()
        if birth_monotonic is not None:
            self._birth = birth_monotonic

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._birth) * 1000)

    def push_video_frame(self, server_data_key: int) -> None:
        now_ms = self.elapsed_ms()
        meta = InputFrameMeta(
            server_data_key=int(server_data_key) & 0xFFFFFFFF,
            first_arrival_ms=now_ms,
            submitted_ms=now_ms,
            decoded_ms=now_ms,
            rendered_ms=now_ms,
        )
        with self._lock:
            self._queue.append(meta)
            # 防止长时间 F8 堆积
            if len(self._queue) > 120:
                self._queue = self._queue[-60:]

    def pop_all(self) -> List[InputFrameMeta]:
        with self._lock:
            items = list(self._queue)
            self._queue.clear()
            return items


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
    frame_metas: Optional[List[InputFrameMeta]] = None,
    client_metadata: bool = False,
    packet_now_ms: Optional[int] = None,
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
    frame_metas = frame_metas or []
    now_ms = int(packet_now_ms if packet_now_ms is not None else elapsed_ms)
    report_type = int(InputReportType.NONE)
    total_size = 14

    if client_metadata:
        report_type |= int(InputReportType.CLIENT_METADATA)
        total_size += 1

    if frame_metas:
        report_type |= int(InputReportType.METADATA)
        total_size += 1 + len(frame_metas) * 28

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

    if frame_metas:
        buf[offset] = len(frame_metas) & 0xFF
        offset += 1
        for meta in frame_metas:
            struct.pack_into("<I", buf, offset, meta.server_data_key)
            offset += 4
            struct.pack_into("<I", buf, offset, meta.first_arrival_ms)
            offset += 4
            struct.pack_into("<I", buf, offset, meta.submitted_ms)
            offset += 4
            struct.pack_into("<I", buf, offset, meta.decoded_ms)
            offset += 4
            struct.pack_into("<I", buf, offset, meta.rendered_ms)
            offset += 4
            struct.pack_into("<I", buf, offset, now_ms)
            offset += 4
            struct.pack_into("<I", buf, offset, now_ms)
            offset += 4

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
    """维护序列号、帧同步队列与时间基准，生成 input 包。"""

    def __init__(self):
        self._sequence = 0
        self._birth = time.monotonic()
        self.frame_sync = InputFrameSyncQueue(self._birth)

    def reset(self) -> None:
        self._sequence = 0
        self._birth = time.monotonic()
        self.frame_sync.reset(self._birth)

    @property
    def elapsed_ms(self) -> int:
        return self.frame_sync.elapsed_ms()

    def _next_packet(
        self,
        *,
        gamepads: Optional[List[Dict[str, int]]] = None,
        client_metadata: bool = False,
        include_frames: bool = True,
    ) -> bytes:
        frame_metas = self.frame_sync.pop_all() if include_frames else []
        now_ms = self.elapsed_ms
        packet = pack_input_packet(
            sequence=self._sequence,
            elapsed_ms=now_ms,
            gamepads=gamepads,
            frame_metas=frame_metas,
            client_metadata=client_metadata,
            packet_now_ms=now_ms,
        )
        self._sequence += 1
        return packet

    def next_gamepad_packet(self, gamepad_data: Dict[str, Any]) -> bytes:
        return self._next_packet(
            gamepads=[gamepad_dict_to_report(gamepad_data)],
            include_frames=True,
        )

    def next_metadata_only_packet(self) -> Optional[bytes]:
        """对齐 libxsrp inputReportingWorker：仅有帧 METADATA、无 gamepad。"""
        frame_metas = self.frame_sync.pop_all()
        if not frame_metas:
            return None
        now_ms = self.elapsed_ms
        packet = pack_input_packet(
            sequence=self._sequence,
            elapsed_ms=now_ms,
            frame_metas=frame_metas,
            packet_now_ms=now_ms,
        )
        self._sequence += 1
        return packet

    def client_metadata_packet(self) -> bytes:
        return self._next_packet(client_metadata=True, include_frames=False)

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
