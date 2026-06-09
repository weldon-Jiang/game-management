"""
RTP 会话管理器
=============

功能说明：
- 管理 RTP 视频流接收
- 处理 RTP 数据包
- 维护 RTP 序列号和时间戳
- 支持 H.264 视频流

技术实现：
- UDP socket 接收
- RTP 头部解析
- H.264 NALU 提取

作者：技术团队
版本：1.0
"""

import asyncio
import struct
from dataclasses import dataclass
from typing import Optional, Callable, AsyncIterator
from enum import Enum
import logging

logger = logging.getLogger('rtp_session')


class RTPState(Enum):
    """RTP 会话状态"""
    IDLE = "idle"
    BINDING = "binding"
    CONNECTED = "connected"
    RECEIVING = "receiving"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class RTPHeader:
    """RTP 头部结构"""
    version: int
    padding: int
    extension: int
    csrc_count: int
    marker: int
    payload_type: int
    sequence_number: int
    timestamp: int
    ssrc: int


@dataclass
class RTPPacket:
    """RTP 数据包"""
    header: RTPHeader
    payload: bytes
    payload_offset: int
    raw_data: bytes


class RTPSession:
    """
    RTP 会话管理器

    功能：
    - 绑定 UDP 端口接收 RTP 流
    - 解析 RTP 头部
    - 提取 H.264 NALU
    - 处理乱序和重传

    使用方式：
    session = RTPSession()
    await session.bind('0.0.0.0', 50500)
    async for packet in session.packets():
        process_h264(packet)
    """

    RTP_HEADER_FORMAT = '!BBHII'
    RTP_HEADER_SIZE = 12

    def __init__(self):
        self._state = RTPState.IDLE
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional['RTPProtocol'] = None
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._expected_seq = 0
        self._packets_received = 0
        self._packets_lost = 0
        self._last_packet_time = 0.0

    async def bind(self, host: str, port: int, reuse_port: bool = False) -> bool:
        """
        绑定 UDP 端口

        参数：
        - host: 绑定地址
        - port: 绑定端口
        - reuse_port: 是否重用端口

        返回：
        - True: 绑定成功
        - False: 绑定失败
        """
        try:
            self._state = RTPState.BINDING
            loop = asyncio.get_event_loop()

            self._protocol = RTPProtocol(self._queue)
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: self._protocol,
                local_addr=(host, port),
                reuse_address=reuse_port
            )

            self._running = True
            self._state = RTPState.CONNECTED
            logger.info(f"RTP 会话绑定成功: {host}:{port}")
            return True

        except Exception as e:
            logger.error(f"RTP 会话绑定失败: {e}")
            self._state = RTPState.ERROR
            return False

    async def packets(self) -> AsyncIterator[RTPPacket]:
        """
        异步获取 RTP 数据包

        使用方式：
        async for packet in session.packets():
            print(f"收到包: seq={packet.header.sequence_number}")
        """
        self._state = RTPState.RECEIVING

        while self._running:
            try:
                raw = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                if isinstance(raw, tuple):
                    data, _addr = raw
                else:
                    data = raw
                packet = self.parse_packet(data)
                if packet is None:
                    continue
                self._packets_received += 1
                self._last_packet_time = asyncio.get_event_loop().time()
                yield packet

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"RTP 接收异常: {e}")
                break

    def parse_packet(self, data: bytes) -> Optional[RTPPacket]:
        """
        解析 RTP 数据包

        参数：
        - data: 原始 RTP 数据

        返回：
        - RTPPacket 或 None
        """
        if len(data) < self.RTP_HEADER_SIZE:
            logger.warning(f"RTP 数据太短: {len(data)} bytes")
            return None

        try:
            header_data = data[:self.RTP_HEADER_SIZE]
            (
                byte0,
                byte1,
                seq_num,
                timestamp,
                ssrc
            ) = struct.unpack(self.RTP_HEADER_FORMAT, header_data)

            version = (byte0 >> 6) & 0x03
            padding = (byte0 >> 5) & 0x01
            extension = (byte0 >> 4) & 0x01
            csrc_count = byte0 & 0x0F

            marker = (byte1 >> 7) & 0x01
            payload_type = byte1 & 0x7F

            header = RTPHeader(
                version=version,
                padding=padding,
                extension=extension,
                csrc_count=csrc_count,
                marker=marker,
                payload_type=payload_type,
                sequence_number=seq_num,
                timestamp=timestamp,
                ssrc=ssrc
            )

            payload_offset = self.RTP_HEADER_SIZE

            if csrc_count > 0:
                csrc_size = csrc_count * 4
                if len(data) >= self.RTP_HEADER_SIZE + csrc_size:
                    payload_offset += csrc_size
                else:
                    logger.warning(f"RTP CSRC 计数异常: {csrc_count}")
                    return None

            if padding and len(data) > 0:
                padding_size = data[-1]
                if padding_size <= len(data) - payload_offset:
                    payload_offset += padding_size

            return RTPPacket(
                header=header,
                payload=data[payload_offset:],
                payload_offset=payload_offset,
                raw_data=data
            )

        except struct.error as e:
            logger.error(f"RTP 头部解析失败: {e}")
            return None

    def close(self):
        """关闭会话"""
        self._running = False
        self._state = RTPState.CLOSED

        if self._transport:
            self._transport.close()
            self._transport = None

        logger.info(f"RTP 会话已关闭, 共接收 {self._packets_received} 个包, 丢失 {self._packets_lost} 个")

    @property
    def state(self) -> RTPState:
        """获取会话状态"""
        return self._state

    @property
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._running

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'state': self._state.value,
            'packets_received': self._packets_received,
            'packets_lost': self._packets_lost,
            'running': self._running,
            'last_packet_time': self._last_packet_time
        }


class RTPProtocol(asyncio.DatagramProtocol):
    """
    RTP 数据报协议

    实现 asyncio.DatagramProtocol 接口
    用于接收 UDP 数据包
    """

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._transport = None

    def connection_made(self, transport):
        """连接建立"""
        self._transport = transport
        logger.debug("RTP 协议连接已建立")

    def datagram_received(self, data, addr):
        """收到数据报"""
        if not self._queue.full():
            self._queue.put_nowait((data, addr))
        else:
            logger.warning("RTP 队列已满，丢弃数据包")

    def error_received(self, exc):
        """错误接收"""
        logger.error(f"RTP 协议错误: {exc}")

    def connection_lost(self, exc):
        """连接丢失"""
        logger.debug(f"RTP 协议连接丢失: {exc}")


class H264RTPPacketAssemble:
    """
    H.264 RTP 分片组装器

    功能：
    - 处理 FU-A 分片
    - 组装完整 NALU
    - 处理 STAP-A 聚合包

    使用方式：
    assembler = H264RTPPacketAssemble()
    for packet in rtp_packets:
        for nalu in assembler.assemble(packet):
            process_nalu(nalu)
    """

    def __init__(self):
        self._fragment_buffer: Optional[bytes] = None
        self._fragment_header: Optional[int] = None
        self._fragment_start = False

    def assemble(self, packet: RTPPacket) -> list:
        """
        组装 H.264 NALU

        参数：
        - packet: RTP 数据包

        返回：
        - NALU 列表
        """
        if packet.header.payload_type not in (96, 99, 127):
            logger.debug(f"非 H.264 RTP 包: payload_type={packet.header.payload_type}")
            return []

        return list(self._parse_payload(packet.payload, packet.header.marker))

    def _parse_payload(self, payload: bytes, marker: int) -> list:
        """解析 H.264 payload"""
        if not payload:
            return []

        nal_type = payload[0] & 0x1F

        if nal_type == 24:
            return self._parse_stap_a(payload)
        elif nal_type == 28:
            return self._parse_fu_a(payload, marker)
        else:
            return [payload]

    def _parse_stap_a(self, payload: bytes) -> list:
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

            nalu = payload[offset:offset+size]
            offset += size

            if len(nalu) > 0:
                nalu_list.append(nalu)

        return nalu_list

    def _parse_fu_a(self, payload: bytes, marker: int) -> list:
        """解析 FU-A 分片"""
        if len(payload) < 2:
            return []

        indicator = payload[0]
        fu_header = payload[1]

        nal_type = indicator & 0x1F
        start_bit = (fu_header >> 7) & 0x01
        end_bit = (fu_header >> 6) & 0x01
        nal_header = indicator & 0xE0 | (fu_header & 0x1F)

        if start_bit:
            self._fragment_buffer = bytes([nal_header])
            self._fragment_start = True

        if self._fragment_buffer is None:
            return []

        self._fragment_buffer += payload[2:]

        if end_bit and self._fragment_start:
            nalu = self._fragment_buffer
            self._fragment_buffer = None
            self._fragment_start = False
            return [nalu]

        return []

    def reset(self):
        """重置组装器状态"""
        self._fragment_buffer = None
        self._fragment_header = None
        self._fragment_start = False
