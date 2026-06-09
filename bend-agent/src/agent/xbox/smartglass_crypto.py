"""
SmartGlass 加解密（移植 OpenXbox xbox-smartglass-core crypto.py，精简依赖 construct）。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
from binascii import unhexlify
from typing import Optional

from ..core.logger import get_logger

logger = get_logger("smartglass_crypto")

KDF_SALT_PREPEND = unhexlify("D637F1AAE2F0418C")
KDF_SALT_APPEND = unhexlify("A8F81A574E228AB7")

PUBLIC_KEY_EC_P256 = 0x00
PUBLIC_KEY_EC_P384 = 0x01
PUBLIC_KEY_EC_P521 = 0x02

CONNECT_RESULT_SUCCESS = 0x00


class SmartGlassCryptoError(Exception):
    """SmartGlass  crypto 初始化/加解密失败。"""


def _require_cryptography():
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        return default_backend, ec, Cipher, algorithms, modes, Encoding, PublicFormat
    except ImportError as exc:
        raise SmartGlassCryptoError(
            "缺少 cryptography 库，请 pip install cryptography"
        ) from exc


class SmartGlassCrypto:
    """ECDH + AES-128-CBC + HMAC-SHA256（OpenXbox KDF）。"""

    def __init__(self, foreign_public_key):
        (
            backend,
            ec,
            Cipher,
            algorithms,
            modes,
            Encoding,
            PublicFormat,
        ) = _require_cryptography()

        if not isinstance(foreign_public_key, ec.EllipticCurvePublicKey):
            raise SmartGlassCryptoError("foreign_public_key 类型无效")

        privkey = ec.generate_private_key(foreign_public_key.curve, backend)
        self._pubkey = privkey.public_key()
        secret = privkey.exchange(ec.ECDH(), foreign_public_key)
        salted = KDF_SALT_PREPEND + secret + KDF_SALT_APPEND
        expanded = hashlib.sha512(salted).digest()
        self._encrypt_key = expanded[:16]
        self._iv_key = expanded[16:32]
        self._hash_key = expanded[32:]
        self._pubkey_bytes = self._pubkey.public_bytes(
            format=PublicFormat.UncompressedPoint,
            encoding=Encoding.X962,
        )[1:]
        key_len = len(self._pubkey_bytes)
        if key_len == 0x40:
            self.pubkey_type = PUBLIC_KEY_EC_P256
        elif key_len == 0x60:
            self.pubkey_type = PUBLIC_KEY_EC_P384
        elif key_len == 0x85:
            self.pubkey_type = PUBLIC_KEY_EC_P521
        else:
            self.pubkey_type = PUBLIC_KEY_EC_P256

    @classmethod
    def from_certificate(cls, cert_der: bytes) -> "SmartGlassCrypto":
        from cryptography import x509
        from cryptography.hazmat.primitives.asymmetric import ec

        cert = x509.load_der_x509_certificate(cert_der)
        public_key = cert.public_key()
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise SmartGlassCryptoError("证书公钥不是 EC 类型")
        return cls(public_key)

    @classmethod
    def from_public_key_bytes(cls, public_key_bytes: bytes) -> "SmartGlassCrypto":
        _, ec, *_ = _require_cryptography()
        key_len = len(public_key_bytes)
        if key_len == 0x40:
            curve = ec.SECP256R1()
        elif key_len == 0x60:
            curve = ec.SECP384R1()
        elif key_len == 0x85:
            curve = ec.SECP521R1()
        else:
            raise SmartGlassCryptoError(f"未知公钥长度: {key_len}")
        foreign = ec.EllipticCurvePublicKey.from_encoded_point(curve, public_key_bytes)
        return cls(foreign)

    def generate_iv(self) -> bytes:
        return os.urandom(16)

    def encrypt(self, iv: bytes, plaintext: bytes) -> bytes:
        _, _, Cipher, algorithms, modes, _, _ = _require_cryptography()
        cipher = Cipher(algorithms.AES(self._encrypt_key), modes.CBC(iv), backend=_require_cryptography()[0])
        encryptor = cipher.encryptor()
        return encryptor.update(plaintext) + encryptor.finalize()

    def decrypt(self, iv: bytes, ciphertext: bytes) -> bytes:
        _, _, Cipher, algorithms, modes, _, _ = _require_cryptography()
        cipher = Cipher(algorithms.AES(self._encrypt_key), modes.CBC(iv), backend=_require_cryptography()[0])
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def hash(self, data: bytes) -> bytes:
        return hmac.new(self._hash_key, data, hashlib.sha256).digest()


def pkcs7_pad(payload: bytes, alignment: int = 16) -> bytes:
    overlap = len(payload) % alignment
    if overlap == 0:
        return payload
    size = alignment - overlap
    return payload + bytes([size]) * size


def pkcs7_unpad(payload: bytes) -> bytes:
    if not payload:
        return payload
    pad_count = payload[-1]
    if pad_count <= 0 or pad_count > 16:
        return payload
    return payload[:-pad_count]


def write_sg_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw + b"\x00"


def struct_pack_uint16(value: int) -> bytes:
    return struct.pack(">H", value)


def struct_pack_uint32(value: int) -> bytes:
    return struct.pack(">I", value)


def extract_public_key_from_cert(cert_der: bytes) -> bytes:
    """从 Discovery 响应证书 DER 提取未压缩 EC 公钥（去掉 0x04 前缀）。"""
    ctx = SmartGlassCrypto.from_certificate(cert_der)
    return ctx._pubkey_bytes
