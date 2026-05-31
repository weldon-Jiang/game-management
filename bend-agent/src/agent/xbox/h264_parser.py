"""
H.264 NALU 解析器
================

功能说明：
- 解析 RTP H.264 负载
- 处理 STAP-A / FU-A 分片
- 组装完整 NALU
- 提取 NALU 类型

技术实现：
- RTP H.264 payload format (RFC 6184)
- NALU 类型解析
- 分片组装

作者：技术团队
版本：1.0
"""

import struct
from dataclasses import dataclass
from typing import Optional, Callable, List
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger('h264_parser')


class NALUType(Enum):
    """H.264 NALU 类型"""
    NON_IDR = 1           # 非 IDR 图像
    PARTITION_A = 2       # 分区 A
    PARTITION_B = 3       # 分区 B
    PARTITION_C = 4       # 分区 C
    IDR = 5               # IDR 图像
    SEI = 6               # 补充增强信息
    SPS = 7               # 序列参数集
    PPS = 8               # 图像参数集
    ACCESS_UNIT = 9       # 访问单元分隔符
    END_OF_SEQUENCE = 10  # 序列结束
    END_OF_STREAM = 11    # 流结束
    FILLER_DATA = 12      # 填充数据
    STAP_A = 24           # 聚合包 A
    STAP_B = 25           # 聚合包 B
    MTAP16 = 26           # 多时间聚合包 16
    MTAP24 = 27           # 多时间聚合包 24
    FU_A = 28             # 分片 A
    FU_B = 29             # 分片 B


@dataclass
class NALU:
    """H.264 NALU 单元"""
    type: NALUType
    data: bytes
    timestamp: int
    marker: bool
    size: int


@dataclass
class SPSInfo:
    """SPS 信息"""
    profile_idc: int
    level_idc: int
    width: int
    height: int
    fps: float


class H264Parser:
    """
    H.264 NALU 解析器

    功能：
    - 解析 H.264 RTP 负载
    - 处理 STAP-A (聚合包)
    - 处理 FU-A (分片)
    - 组装完整 NALU

    NALU 类型：
    - 1: 非 IDR 图像
    - 5: IDR 图像
    - 6: SEI
    - 7: SPS (序列参数集)
    - 8: PPS (图像参数集)

    使用方式：
    parser = H264Parser()
    parser.set_callback(on_nalu)
    parser.feed(rtp_payload)
    """

    START_CODE = b'\x00\x00\x00\x01'

    def __init__(self):
        self._fragment_buf: Optional[bytes] = None
        self._frag_header: Optional[int] = None
        self._frag_timestamp: Optional[int] = None
        self._callback: Optional[Callable[[NALU], None]] = None
        self._nalu_count = 0
        self._sps_info: Optional[SPSInfo] = None

    def set_callback(self, callback: Callable[[NALU], None]):
        """设置 NALU 回调"""
        self._callback = callback

    def feed(self, payload: bytes, timestamp: int = 0, marker: bool = False) -> List[NALU]:
        """
        输入 RTP H.264 负载

        参数：
        - payload: RTP payload
        - timestamp: RTP 时间戳
        - marker: RTP marker 位

        返回：
        - NALU 列表
        """
        if not payload:
            return []

        try:
            nal_type = payload[0] & 0x1F
            nalu_list: List[NALU] = []

            if nal_type == 24:  # STAP-A
                nalu_list = self._parse_stap_a(payload, timestamp, marker)
            elif nal_type == 28:  # FU-A
                nalu_list = self._parse_fu_a(payload, timestamp, marker)
            else:  # Single NALU
                nalu_list = [self._create_nalu(payload, timestamp, marker, nal_type)]

            for nalu in nalu_list:
                self._process_nalu(nalu)

            return nalu_list

        except Exception as e:
            logger.error(f"H.264 解析失败: {e}")
            return []

    def _create_nalu(self, data: bytes, timestamp: int, marker: bool, nal_type: int) -> NALU:
        """创建 NALU 对象"""
        return NALU(
            type=NALUType(nal_type) if nal_type < 32 else NALUType.FU_A,
            data=data,
            timestamp=timestamp,
            marker=marker,
            size=len(data)
        )

    def _parse_stap_a(self, payload: bytes, timestamp: int, marker: bool) -> List[NALU]:
        """解析 STAP-A 聚合包"""
        if len(payload) < 3:
            return []

        nalu_list = []
        offset = 1

        while offset <= len(payload) - 2:
            size = struct.unpack('!H', payload[offset:offset+2])[0]
            offset += 2

            if offset + size > len(payload):
                logger.warning("STAP-A NALU 大小超出范围")
                break

            nalu_data = payload[offset:offset+size]
            offset += size

            if len(nalu_data) > 0:
                nal_type = nalu_data[0] & 0x1F
                nalu_list.append(self._create_nalu(nalu_data, timestamp, False, nal_type))

        return nalu_list

    def _parse_fu_a(self, payload: bytes, timestamp: int, marker: bool) -> List[NALU]:
        """解析 FU-A 分片"""
        if len(payload) < 2:
            return []

        indicator = payload[0]
        fu_header = payload[1]

        nal_type = indicator & 0x1F

        start_bit = fu_header & 0x80
        end_bit = fu_header & 0x40
        nal_header = indicator & 0xE0 | (fu_header & 0x1F)

        if start_bit:
            self._fragment_buf = bytes([nal_header])
            self._frag_header = nal_type
            self._frag_timestamp = timestamp

        if self._fragment_buf is not None:
            self._fragment_buf += payload[2:]

        if end_bit and self._fragment_buf is not None:
            nalu = self._create_nalu(
                self._fragment_buf,
                self._frag_timestamp or timestamp,
                marker,
                nal_type
            )
            self._fragment_buf = None
            self._frag_header = None
            self._frag_timestamp = None
            return [nalu]

        return []

    def _process_nalu(self, nalu: NALU):
        """处理 NALU"""
        self._nalu_count += 1

        if nalu.type == NALUType.SPS:
            self._parse_sps(nalu.data)
        elif nalu.type == NALUType.PPS:
            self._parse_pps(nalu.data)

        if self._callback:
            self._callback(nalu)

    def _parse_sps(self, data: bytes):
        """解析 SPS"""
        try:
            if len(data) < 4:
                return

            data = data[1:]

            nal_reader = NALUReader(data)
            profile_idc = nal_reader.read_u8()
            nal_reader.read_bits(16)
            level_idc = nal_reader.read_u8()

            if profile_idc in [66, 77, 88]:
                nal_reader.read_ue()
            elif profile_idc in [100, 110, 122, 244, 44, 83, 86]:
                if profile_idc in [100, 110, 122, 244]:
                    chroma_format_idc = nal_reader.read_ue()
                    if chroma_format_idc == 3:
                        nal_reader.read_bits(1)
                nal_reader.read_ue()
                nal_reader.read_ue()
                nal_reader.read_bits(1)

            pic_order_cnt_type = nal_reader.read_ue()
            if pic_order_cnt_type == 0:
                nal_reader.read_ue()
            elif pic_order_cnt_type == 1:
                nal_reader.read_bits(1)
                nal_reader.read_ue()
                for _ in range(nal_reader.read_ue()):
                    nal_reader.read_ue()

            nal_reader.read_bits(1)
            pic_width_in_mbs_minus1 = nal_reader.read_ue()
            pic_height_in_map_units_minus1 = nal_reader.read_ue()
            frame_mbs_only_flag = nal_reader.read_bits(1)

            width = (pic_width_in_mbs_minus1 + 1) * 16
            height = (pic_height_in_map_units_minus1 + 1) * 16 * (2 - frame_mbs_only_flag)

            self._sps_info = SPSInfo(
                profile_idc=profile_idc,
                level_idc=level_idc,
                width=width,
                height=height,
                fps=30.0
            )

            logger.info(f"解析 SPS: {width}x{height}, profile={profile_idc}, level={level_idc}")

        except Exception as e:
            logger.warning(f"SPS 解析失败: {e}")

    def _parse_pps(self, data: bytes):
        """解析 PPS"""
        pass

    def reset(self):
        """重置解析器"""
        self._fragment_buf = None
        self._frag_header = None
        self._frag_timestamp = None
        self._nalu_count = 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'nalu_count': self._nalu_count,
            'sps_info': self._sps_info.__dict__ if self._sps_info else None
        }

    @property
    def sps_info(self) -> Optional[SPSInfo]:
        """获取 SPS 信息"""
        return self._sps_info


class NALUReader:
    """NALU 字节读取器"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self._bits_pos = 0
        self._current_byte = 0

    def read_u8(self) -> int:
        """读取一个字节"""
        if self._pos >= len(self._data):
            return 0
        value = self._data[self._pos]
        self._pos += 1
        return value

    def read_bits(self, count: int) -> int:
        """读取指定位数"""
        result = 0
        for _ in range(count):
            if self._bits_pos == 0:
                self._current_byte = self.read_u8()
                self._bits_pos = 8

            result = (result << 1) | ((self._current_byte >> (self._bits_pos - 1)) & 1)
            self._bits_pos -= 1

        return result

    def read_ue(self) -> int:
        """读取指数Golomb编码的无符号数"""
        leading_zero_bits = 0

        while self.read_bits(1) == 0:
            leading_zero_bits += 1
            if leading_zero_bits > 32:
                return 0

        if leading_zero_bits == 0:
            return 0

        value = (1 << leading_zero_bits) | self.read_bits(leading_zero_bits - 1)
        return value - 1


class H264FrameAssembler:
    """
    H.264 帧组装器

    功能：
    - 组装完整视频帧
    - 处理 IDR 和非 IDR 帧
    - 提供解码器友好的格式

    使用方式：
    assembler = H264FrameAssembler()
    for nalu in nalu_list:
        frame = assembler.add_nalu(nalu)
        if frame:
            decoder.decode(frame)
    """

    def __init__(self):
        self._current_frame: List[bytes] = []
        self._frame_timestamp: Optional[int] = None
        self._frame_type: Optional[NALUType] = None
        self._last_idr_timestamp: Optional[int] = None

    def add_nalu(self, nalu: NALU) -> Optional[bytes]:
        """
        添加 NALU，返回完整帧（如果一帧结束）

        参数：
        - nalu: NALU 单元

        返回：
        - 完整帧的Annex B格式数据，或 None
        """
        if nalu.type in (NALUType.IDR, NALUType.NON_IDR):
            if self._frame_timestamp is not None and nalu.timestamp != self._frame_timestamp:
                frame = self._finish_frame()
                self._start_frame(nalu)
                return frame

            if self._frame_timestamp is None:
                self._start_frame(nalu)

            self._current_frame.append(nalu.data)

            if nalu.marker:
                return self._finish_frame()

        return None

    def _start_frame(self, nalu: NALU):
        """开始新帧"""
        self._current_frame = [nalu.data]
        self._frame_timestamp = nalu.timestamp
        self._frame_type = nalu.type

        if nalu.type == NALUType.IDR:
            self._last_idr_timestamp = nalu.timestamp

    def _finish_frame(self) -> Optional[bytes]:
        """完成当前帧"""
        if not self._current_frame:
            return None

        frame_data = b''
        for nalu_data in self._current_frame:
            frame_data += H264Parser.START_CODE + nalu_data

        self._current_frame = []
        self._frame_timestamp = None

        return frame_data

    def reset(self):
        """重置"""
        self._current_frame = []
        self._frame_timestamp = None
        self._frame_type = None

    @property
    def has_frame(self) -> bool:
        """是否有未完成的帧"""
        return len(self._current_frame) > 0
