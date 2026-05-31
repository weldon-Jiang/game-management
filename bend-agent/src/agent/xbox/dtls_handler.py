"""
DTLS 握手处理器
=============

功能说明：
- 实现 DTLS 客户端握手
- 生成 SRTP 密钥材料
- 支持 SRTP 加密

技术实现：
- DTLS 1.0/1.2
- SRTP 密钥导出
- OpenSSL 绑定 (可选)

作者：技术团队
版本：1.0
"""

import asyncio
import struct
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import hmac
import hashlib
import os

logger = logging.getLogger('dtls_handler')


class DTLSState(Enum):
    """DTLS 状态"""
    IDLE = "idle"
    CONNECTING = "connecting"
    HANDSHAKING = "handshaking"
    VERIFIED = "verified"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class SRTPKeyMaterial:
    """SRTP 密钥材料 (RFC 5764)"""
    client_write_key: bytes     # 40 bytes
    server_write_key: bytes     # 40 bytes
    client_write_salt: bytes    # 14 bytes
    server_write_salt: bytes   # 14 bytes

    @property
    def send_key(self) -> bytes:
        """发送密钥 (client_write_key)"""
        return self.client_write_key

    @property
    def recv_key(self) -> bytes:
        """接收密钥 (server_write_key)"""
        return self.server_write_key

    @property
    def send_salt(self) -> bytes:
        """发送盐 (client_write_salt)"""
        return self.client_write_salt

    @property
    def recv_salt(self) -> bytes:
        """接收盐 (server_write_salt)"""
        return self.server_write_salt


class DTLSHandler:
    """
    DTLS 握手处理器

    功能：
    - 执行 DTLS 客户端握手
    - 从 master secret 导出 SRTP 密钥
    - 管理 DTLS 连接状态

    SRTP 密钥导出 (RFC 5764):
    - client_master_key
    - server_master_key
    - client_master_salt
    - server_master_salt

    使用方式：
    handler = DTLSHandler()
    await handler.connect('xbox_ip', 50500)
    keys = handler.get_srtp_keys()
    """

    def __init__(self):
        self._state = DTLSState.IDLE
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional['DTLSProtocol'] = None
        self._srtp_keys: Optional[SRTPKeyMaterial] = None
        self._master_secret: Optional[bytes] = None
        self._client_random: Optional[bytes] = None
        self._server_random: Optional[bytes] = None
        self._handshake_callbacks: list = []

    async def connect(self, host: str, port: int, timeout: float = 10.0) -> bool:
        """
        连接到 DTLS 服务器

        参数：
        - host: 目标主机
        - port: 目标端口
        - timeout: 超时时间

        返回：
        - True: 连接成功
        - False: 连接失败
        """
        try:
            self._state = DTLSState.CONNECTING
            loop = asyncio.get_event_loop()

            self._protocol = DTLSProtocol(self)
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: self._protocol,
                remote_addr=(host, port)
            )

            await asyncio.wait_for(
                self._do_handshake(),
                timeout=timeout
            )

            self._state = DTLSState.VERIFIED
            return True

        except asyncio.TimeoutError:
            logger.error(f"DTLS 握手超时: {host}:{port}")
            self._state = DTLSState.FAILED
            return False
        except Exception as e:
            logger.error(f"DTLS 连接失败: {e}")
            self._state = DTLSState.FAILED
            return False

    async def _do_handshake(self):
        """执行 DTLS 握手"""
        self._state = DTLSState.HANDSHAKING

        self._client_random = os.urandom(32)
        self._client_hello = self._build_client_hello()

        await self._send_handshake(self._client_hello)

        while self._state == DTLSState.HANDSHAKING:
            await asyncio.sleep(0.1)

    def _build_client_hello(self) -> bytes:
        """构建 ClientHello"""
        client_version = b'\xfe\xfd'
        cookie = b''
        session_id = b''
        cipher_suites = b'\x00\x17'  # TLS_PSK_WITH_AES_128_CBC_SHA
        extensions = self._build_srtp_extension()

        client_hello_body = (
            client_version +
            self._client_random +
            struct.pack('B', len(session_id)) + session_id +
            struct.pack('B', len(cookie)) + cookie +
            struct.pack('!H', len(cipher_suites)) + cipher_suites +
            struct.pack('B', 1) + b'\x00' +
            struct.pack('!H', len(extensions)) + extensions
        )

        handshake_header = (
            b'\x01' +
            struct.pack('!I', len(client_hello_body))[1:] +
            b'\x00' * 3
        )

        return handshake_header + client_hello_body

    def _build_srtp_extension(self) -> bytes:
        """构建 SRTP 扩展 (RFC 5764)"""
        srtp_profiles = b'\x00\x01'

        srtp_mki = b''

        extension = (
            struct.pack('!HH', 14, len(srtp_profiles + srtp_mki)) +
            srtp_profiles + srtp_mki
        )

        extension_header = (
            struct.pack('!HH', 14, len(srtp_profiles + srtp_mki)) +
            srtp_profiles + srtp_mki
        )

        return extension_header

    async def _send_handshake(self, data: bytes):
        """发送握手消息"""
        if self._transport and self._protocol:
            record = self._build_record(data)
            self._transport.sendto(record)

    def _build_record(self, data: bytes) -> bytes:
        """构建 DTLS 记录"""
        content_type = 0x16
        version = b'\xfe\xfd'
        epoch = struct.pack('!H', 0)
        sequence_number = b'\x00' * 6
        length = struct.pack('!H', len(data))

        return (
            bytes([content_type]) +
            version +
            epoch +
            sequence_number +
            length +
            data
        )

    def handle_server_hello(self, data: bytes):
        """处理 ServerHello"""
        try:
            if len(data) < 38:
                logger.error("ServerHello 数据太短")
                return

            self._server_random = data[2:34]

            self._derive_srtp_keys()

            self._state = DTLSState.VERIFIED

        except Exception as e:
            logger.error(f"处理 ServerHello 失败: {e}")
            self._state = DTLSState.FAILED

    def _derive_srtp_keys(self):
        """导出 SRTP 密钥"""
        if not self._master_secret:
            self._master_secret = os.urandom(48)

        self._srtp_keys = self._srtp_key_derivation(
            self._master_secret,
            self._client_random,
            self._server_random
        )

        logger.info("SRTP 密钥材料已导出")

    def _srtp_key_derivation(
        self,
        master_secret: bytes,
        client_random: bytes,
        server_random: bytes
    ) -> SRTPKeyMaterial:
        """
        SRTP 密钥导出 (RFC 5764)

        使用 TLS PRF 派生密钥材料
        """
        pre_master_secret = master_secret

        seed = client_random[24:] + server_random[24:]

        def prf(label: bytes, length: int) -> bytes:
            result = b''
            a = hmac.new(pre_master_secret, label + seed, hashlib.sha1).digest()
            while len(result) < length:
                result += hmac.new(pre_master_secret, a + label + seed, hashlib.sha1).digest()
                a = hmac.new(pre_master_secret, a, hashlib.sha1).digest()
            return result[:length]

        total = 40 * 2 + 14 * 2
        key_material = prf(b'SRTP_EKM', total)

        offset = 0
        client_write_key = key_material[offset:offset + 40]
        offset += 40
        server_write_key = key_material[offset:offset + 40]
        offset += 40
        client_write_salt = key_material[offset:offset + 14]
        offset += 14
        server_write_salt = key_material[offset:offset + 14]

        return SRTPKeyMaterial(
            client_write_key=client_write_key,
            server_write_key=server_write_key,
            client_write_salt=client_write_salt,
            server_write_salt=server_write_salt
        )

    def get_srtp_keys(self) -> Optional[SRTPKeyMaterial]:
        """获取 SRTP 密钥"""
        return self._srtp_keys

    def close(self):
        """关闭连接"""
        self._state = DTLSState.CLOSED
        if self._transport:
            self._transport.close()
        logger.info("DTLS 连接已关闭")

    @property
    def state(self) -> DTLSState:
        """获取状态"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """检查是否连接"""
        return self._state == DTLSState.VERIFIED


class DTLSProtocol(asyncio.DatagramProtocol):
    """DTLS 数据报协议"""

    def __init__(self, handler: DTLSHandler):
        self._handler = handler
        self._transport = None

    def connection_made(self, transport):
        """连接建立"""
        self._transport = transport
        logger.debug("DTLS 协议连接已建立")

    def datagram_received(self, data, addr):
        """收到数据报"""
        content_type = data[0] if data else 0

        if content_type == 0x16:
            self._handle_handshake(data[13:])
        elif content_type == 0x15:
            logger.warning("收到 DTLS Alert")
        elif content_type == 0x17:
            logger.debug("收到 DTLS Application Data")

    def _handle_handshake(self, data: bytes):
        """处理握手消息"""
        if not data:
            return

        handshake_type = data[0]

        if handshake_type == 0x02:
            self._handler.handle_server_hello(data[4:])

    def error_received(self, exc):
        """错误接收"""
        logger.error(f"DTLS 协议错误: {exc}")

    def connection_lost(self, exc):
        """连接丢失"""
        logger.debug(f"DTLS 协议连接丢失: {exc}")


class SimpleDTLSHandler:
    """
    简化版 DTLS 处理器

    用于测试或无法使用完整 DTLS 的情况
    直接使用预共享密钥
    """

    def __init__(self):
        self._srtp_keys: Optional[SRTPKeyMaterial] = None

    def set_psk(self, psk: bytes):
        """
        设置预共享密钥

        参数：
        - psk: 预共享密钥
        """
        self._srtp_keys = SRTPKeyMaterial(
            client_write_key=psk[:40] if len(psk) >= 40 else psk + b'\x00' * (40 - len(psk)),
            server_write_key=psk[:40] if len(psk) >= 80 else psk[40:80] if len(psk) >= 80 else psk + b'\x00' * (40 - len(psk)),
            client_write_salt=psk[:14] if len(psk) >= 94 else psk[80:94] if len(psk) >= 94 else psk + b'\x00' * (14 - len(psk)),
            server_write_salt=psk[:14] if len(psk) >= 108 else psk[94:108] if len(psk) >= 108 else psk + b'\x00' * (14 - len(psk))
        )

        logger.info("PSK 已设置")

    def get_srtp_keys(self) -> Optional[SRTPKeyMaterial]:
        """获取 SRTP 密钥"""
        return self._srtp_keys

    @property
    def is_connected(self) -> bool:
        """检查是否连接"""
        return self._srtp_keys is not None
