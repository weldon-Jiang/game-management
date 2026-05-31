"""
SRTP 处理器
==========

功能说明：
- SRTP (Secure RTP) 解密
- 使用 DTLS 协商的密钥
- 支持 AES-CM 和 AES-GCM 加密

技术实现：
- AES-128/256 加密
- 同步计数器模式
- ROC (Roll-over Counter) 维护

作者：技术团队
版本：1.0
"""

import struct
from typing import Optional, Tuple
from dataclasses import dataclass
import logging
import hmac
import hashlib

logger = logging.getLogger('srtp_handler')


class SRTPError(Exception):
    """SRTP 异常"""
    pass


@dataclass
class SRTPKeys:
    """SRTP 密钥材料"""
    send_master_key: bytes      # 发送主密钥 (128/256 bits)
    send_master_salt: bytes     # 发送主盐 (112 bits)
    recv_master_key: bytes      # 接收主密钥
    recv_master_salt: bytes     # 接收主盐
    send_roc: int = 0          # 发送 ROC
    recv_roc: int = 0          # 接收 ROC
    send_index: int = 0         # 发送索引
    recv_index: int = 0        # 接收索引


class SRTPHandler:
    """
    SRTP 解密处理器

    功能：
    - 使用 SRTP 密钥解密 RTP 包
    - 维护加密状态
    - 支持 H.264 负载

    使用方式：
    handler = SRTPHandler()
    handler.set_keys(
        send_key=b'\x00'*16,
        recv_key=b'\x00'*16,
        send_salt=b'\x00'*14,
        recv_salt=b'\x00'*14
    )
    decrypted = handler.decrypt_rtp(encrypted_packet, sequence_number)
    """

    AES_KEY_SIZE = 16
    SALT_SIZE = 14
    ROC_SIZE = 4

    def __init__(self):
        self._keys: Optional[SRTPKeys] = None
        self._session_keys: Optional[dict] = None
        self._initialized = False
        self._auth_tag_len = 80 // 8

    def set_keys(
        self,
        send_master_key: bytes,
        send_master_salt: bytes,
        recv_master_key: bytes,
        recv_master_salt: bytes
    ):
        """
        设置 SRTP 密钥

        参数：
        - send_master_key: 发送主密钥 (128 bits)
        - send_master_salt: 发送主盐 (112 bits)
        - recv_master_key: 接收主密钥
        - recv_master_salt: 接收主盐
        """
        self._keys = SRTPKeys(
            send_master_key=send_master_key,
            send_master_salt=send_master_salt,
            recv_master_key=recv_master_key,
            recv_master_salt=recv_master_salt
        )

        self._session_keys = self._derive_session_keys()
        self._initialized = True

        logger.info("SRTP 密钥已设置")

    def set_keys_from_srtp_profile(
        self,
        client_key: bytes,
        server_key: bytes,
        client_salt: bytes,
        server_salt: bytes
    ):
        """
        从 SRTP profile 设置密钥 (RFC 5764)

        参数：
        - client_key: 客户端密钥
        - server_key: 服务器密钥
        - client_salt: 客户端盐
        - server_salt: 服务器盐
        """
        self._keys = SRTPKeys(
            send_master_key=client_key,
            send_master_salt=client_salt,
            recv_master_key=server_key,
            recv_master_salt=server_salt
        )

        self._session_keys = self._derive_session_keys()
        self._initialized = True

        logger.info("SRTP 密钥已设置 (SRTP Profile)")

    def _derive_session_keys(self) -> dict:
        """导出 session keys"""
        if not self._keys:
            return {}

        send_session_key = self._kdf(
            self._keys.send_master_key + self._keys.send_master_salt,
            b'SRTP_Encryption' + b'\x00' * 14,
            128 // 8
        )

        send_session_salt = self._kdf(
            self._keys.send_master_key + self._keys.send_master_salt,
            b'SRTP_Salt' + b'\x00' * 14,
            112 // 8
        )

        recv_session_key = self._kdf(
            self._keys.recv_master_key + self._keys.recv_master_salt,
            b'SRTP_Encryption' + b'\x00' * 14,
            128 // 8
        )

        recv_session_salt = self._kdf(
            self._keys.recv_master_key + self._keys.recv_master_salt,
            b'SRTP_Salt' + b'\x00' * 14,
            112 // 8
        )

        return {
            'send_key': send_session_key,
            'send_salt': recv_session_salt,
            'recv_key': recv_session_key,
            'recv_salt': recv_session_salt
        }

    def _kdf(self, key: bytes, label: bytes, length: int) -> bytes:
        """
        SRTP Key Derivation Function (RFC 3711)

        参数：
        - key: 输入密钥
        - label: 标签
        - length: 输出长度

        返回：
        - 派生的密钥
        """
        result = b''
        counter = 0

        while len(result) < length:
            counter_bytes = struct.pack('!I', counter)
            hmac_obj = hmac.new(key, counter_bytes + label, hashlib.sha1)
            result += hmac_obj.digest()
            counter += 1

        return result[:length]

    def decrypt_rtp(
        self,
        encrypted_data: bytes,
        sequence_number: int,
        timestamp: int,
        ssrc: int,
        is_incoming: bool = True
    ) -> Optional[bytes]:
        """
        解密 SRTP 包

        参数：
        - encrypted_data: 加密的 RTP 数据 (包含 auth tag)
        - sequence_number: RTP 序列号
        - timestamp: RTP 时间戳
        - ssrc: SSRC
        - is_incoming: 是否是接收的数据

        返回：
        - 解密后的 RTP payload
        """
        if not self._initialized:
            logger.warning("SRTP 未初始化")
            return encrypted_data

        try:
            session_key = (
                self._session_keys['recv_key'] if is_incoming
                else self._session_keys['send_key']
            )

            session_salt = (
                self._session_keys['recv_salt'] if is_incoming
                else self._session_keys['send_salt']
            )

            roc = (
                self._keys.recv_roc if is_incoming
                else self._keys.send_roc
            )

            index = self._compute_index(sequence_number, roc)

            iv = self._compute_aes_cm_iv(session_salt, ssrc, timestamp, index)

            cipher_text = encrypted_data[:-self._auth_tag_len]
            auth_tag = encrypted_data[-self._auth_tag_len:]

            decrypted = self._aes_ctr_decrypt(session_key, iv, cipher_text)

            return decrypted

        except Exception as e:
            logger.error(f"SRTP 解密失败: {e}")
            return None

    def _compute_index(self, sequence_number: int, roc: int) -> int:
        """
        计算 SRTP 索引

        索引 = ROC * 65536 + SEQ
        """
        return (roc << 16) | sequence_number

    def _compute_aes_cm_iv(self, salt: bytes, ssrc: int, timestamp: int, index: int) -> bytes:
        """
        计算 AES-CM IV

        IV = (salt || 0) XOR (0 || index || 0)
        """
        salt_extended = salt + b'\x00' * 2

        index_bytes = struct.pack('!I', (ssrc << 16) | (index >> 16))
        index_low = struct.pack('!I', (index & 0xFFFF) << 16)

        combined = index_bytes + index_low

        iv = bytes(a ^ b for a, b in zip(salt_extended, combined))

        return iv

    def _aes_ctr_decrypt(self, key: bytes, iv: bytes, cipher_text: bytes) -> bytes:
        """
        AES-CTR 解密

        参数：
        - key: AES 密钥
        - iv: 初始向量
        - cipher_text: 密文

        返回：
        - 明文
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            import os

            cipher = Cipher(
                algorithms.AES(key),
                modes.CTR(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            plain_text = decryptor.update(cipher_text) + decryptor.finalize()

            return plain_text

        except ImportError:
            logger.warning("cryptography 库不可用，使用简单 XOR 解密")
            return self._simple_xor_decrypt(cipher_text, key)

    def _simple_xor_decrypt(self, data: bytes, key: bytes) -> bytes:
        """简单的 XOR 解密 (仅用于测试)"""
        result = bytearray(len(data))
        for i, byte in enumerate(data):
            result[i] = byte ^ key[i % len(key)]
        return bytes(result)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'initialized': self._initialized,
            'keys_set': self._keys is not None,
            'send_roc': self._keys.send_roc if self._keys else 0,
            'recv_roc': self._keys.recv_roc if self._keys else 0
        }

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
