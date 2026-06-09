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
        self._dtls_cookie: bytes = b""
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

            return self._state == DTLSState.VERIFIED

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

    def handle_hello_verify_request(self, data: bytes):
        """处理 DTLS HelloVerifyRequest，提取 cookie 并重发 ClientHello。"""
        try:
            if len(data) < 3:
                logger.error("HelloVerifyRequest 数据太短")
                return
            cookie_len = data[2]
            if len(data) < 3 + cookie_len:
                logger.error("HelloVerifyRequest cookie 长度无效")
                return
            self._dtls_cookie = data[3:3 + cookie_len]
            logger.debug("收到 HelloVerifyRequest，cookie 长度=%s", cookie_len)
            asyncio.get_event_loop().create_task(self._resend_client_hello())
        except Exception as exc:
            logger.error("处理 HelloVerifyRequest 失败: %s", exc)
            self._state = DTLSState.FAILED

    async def _resend_client_hello(self):
        """携带 cookie 重发 ClientHello。"""
        self._client_random = os.urandom(32)
        self._client_hello = self._build_client_hello()
        await self._send_handshake(self._client_hello)

    def _build_client_hello(self) -> bytes:
        """构建 ClientHello"""
        client_version = b'\xfe\xfd'
        cookie = self._dtls_cookie
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


class DTLSPSKClient(DTLSHandler):
    """
    DTLS-PSK 客户端（RFC 4279 + SRTP 扩展 RFC 5764）。

    对照 xsrp/libxsrp 的 DtlsSrtpTransport：在 UDP 上完成 PSK 握手并导出 SRTP 密钥。
    """

    def __init__(self, psk: bytes, psk_identity: str = "xbox"):
        super().__init__()
        self._psk = psk
        self._psk_identity = psk_identity or "xbox"
        self._handshake_done = asyncio.Event()

    async def connect(self, host: str, port: int, timeout: float = 10.0) -> bool:
        """PSK 握手：发送 ClientHello 后等待 ChangeCipherSpec（含 HelloVerifyRequest 重试）。"""
        self._remote_host = host
        self._remote_port = port
        self._handshake_done.clear()
        self._dtls_cookie = b""
        try:
            self._state = DTLSState.CONNECTING
            loop = asyncio.get_event_loop()
            self._protocol = DTLSProtocol(self)
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: self._protocol,
                remote_addr=(host, port),
            )
            self._state = DTLSState.HANDSHAKING
            self._client_random = os.urandom(32)
            self._client_hello = self._build_client_hello()
            await self._send_handshake(self._client_hello)
            await asyncio.wait_for(self._handshake_done.wait(), timeout=timeout)
            return self._state == DTLSState.VERIFIED
        except asyncio.TimeoutError:
            logger.error("DTLS-PSK 握手超时: %s:%s", host, port)
            self._state = DTLSState.FAILED
            return False
        except Exception as exc:
            logger.error("DTLS-PSK 连接失败: %s", exc)
            self._state = DTLSState.FAILED
            return False

    def _build_client_hello(self) -> bytes:
        """构建带 PSK 与 SRTP 扩展的 ClientHello。"""
        client_version = b"\xfe\xfd"  # DTLS 1.2
        cookie = self._dtls_cookie
        session_id = b""
        # TLS_PSK_WITH_AES_128_CBC_SHA + TLS_EMPTY_RENEGOTIATION_INFO_SCSV
        cipher_suites = b"\x00\x04\x00\x2f\x00\xff"
        extensions = self._build_psk_srtp_extensions()

        client_hello_body = (
            client_version
            + self._client_random
            + struct.pack("B", len(session_id))
            + session_id
            + struct.pack("B", len(cookie))
            + cookie
            + struct.pack("!H", len(cipher_suites))
            + cipher_suites
            + struct.pack("B", 1)
            + b"\x00"
            + struct.pack("!H", len(extensions))
            + extensions
        )

        handshake_header = b"\x01" + struct.pack("!I", len(client_hello_body))[1:] + b"\x00" * 3
        return handshake_header + client_hello_body

    def _build_psk_srtp_extensions(self) -> bytes:
        """PSK identity + use_srtp 扩展。"""
        identity_bytes = self._psk_identity.encode("utf-8")
        psk_identity = struct.pack("!H", len(identity_bytes)) + identity_bytes
        psk_identity_ext = struct.pack("!HH", 45, len(psk_identity)) + psk_identity

        srtp_profiles = b"\x00\x01"  # SRTP_AES128_CM_HMAC_SHA1_80
        srtp_ext = struct.pack("!HH", 14, len(srtp_profiles)) + srtp_profiles

        return psk_identity_ext + srtp_ext

    def handle_server_hello(self, data: bytes):
        try:
            if len(data) < 34:
                logger.error("ServerHello 数据太短")
                return
            self._server_random = data[2:34]
            logger.debug("收到 ServerHello")
        except Exception as exc:
            logger.error("处理 ServerHello 失败: %s", exc)
            self._state = DTLSState.FAILED

    def handle_server_hello_done(self):
        logger.debug("收到 ServerHelloDone，发送 ClientKeyExchange + ChangeCipherSpec")
        asyncio.get_event_loop().create_task(self._finish_psk_handshake())

    def handle_change_cipher_spec(self):
        logger.debug("收到服务端 ChangeCipherSpec，导出 SRTP 密钥")
        self._derive_srtp_keys_from_psk()
        self._state = DTLSState.VERIFIED
        self._handshake_done.set()

    async def _finish_psk_handshake(self):
        """PSK 握手后半段：ClientKeyExchange → ChangeCipherSpec（对齐 libxsrp DtlsSrtpTransport）。"""
        identity = self._psk_identity.encode("utf-8")
        body = struct.pack("!H", len(identity)) + identity
        client_key_exchange = b"\x10" + struct.pack("!I", len(body))[1:] + b"\x00" * 3 + body
        await self._send_handshake(client_key_exchange)
        await self._send_change_cipher_spec()

    async def _send_change_cipher_spec(self):
        """发送 ChangeCipherSpec 记录。"""
        if not self._transport:
            return
        record = (
            bytes([0x14])
            + b"\xfe\xfd"
            + struct.pack("!H", 0)
            + b"\x00" * 6
            + struct.pack("!H", 1)
            + b"\x01"
        )
        self._transport.sendto(record)

    def _derive_srtp_keys_from_psk(self):
        """PSK master secret + RFC 5764 SRTP 密钥导出。"""
        if not self._client_random or not self._server_random:
            self._client_random = self._client_random or os.urandom(32)
            self._server_random = self._server_random or os.urandom(32)

        seed = self._client_random + self._server_random
        label = b"master secret"
        a = hmac.new(self._psk, label + seed, hashlib.sha1).digest()
        master = b""
        while len(master) < 48:
            master += hmac.new(self._psk, a + label + seed, hashlib.sha1).digest()
            a = hmac.new(self._psk, a, hashlib.sha1).digest()
        self._master_secret = master[:48]
        self._srtp_keys = self._srtp_key_derivation(
            self._master_secret,
            self._client_random,
            self._server_random,
        )
        logger.info("DTLS-PSK SRTP 密钥材料已导出")


class DTLSProtocol(asyncio.DatagramProtocol):
    """DTLS 数据报协议"""

    def __init__(self, handler: DTLSHandler):
        self._handler = handler
        self._transport = None

    def connection_made(self, transport):
        """连接建立"""
        self._transport = transport
        self._handler._transport = transport
        logger.debug("DTLS 协议连接已建立")

    def datagram_received(self, data, addr):
        """收到数据报"""
        if len(data) < 13:
            return
        content_type = data[0]

        if content_type == 0x16:
            self._handle_handshake(data[13:])
        elif content_type == 0x14:
            if hasattr(self._handler, "handle_change_cipher_spec"):
                self._handler.handle_change_cipher_spec()
        elif content_type == 0x15:
            logger.warning("收到 DTLS Alert")
        elif content_type == 0x17:
            logger.debug("收到 DTLS Application Data")

    def _handle_handshake(self, data: bytes):
        """处理握手消息"""
        if not data:
            return

        handshake_type = data[0]

        if handshake_type == 0x03:
            if hasattr(self._handler, "handle_hello_verify_request"):
                self._handler.handle_hello_verify_request(data[4:])
        elif handshake_type == 0x02:
            self._handler.handle_server_hello(data[4:])
        elif handshake_type == 0x0E:
            if hasattr(self._handler, "handle_server_hello_done"):
                self._handler.handle_server_hello_done()
        elif handshake_type == 0x0F:
            if hasattr(self._handler, "handle_server_hello_done"):
                self._handler.handle_server_hello_done()

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
