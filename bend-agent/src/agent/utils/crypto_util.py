"""
Cryptography Utilities
=====================

功能说明：
- AES 解密（匹配平台侧 AES-ECB-NoPadding 加密）
- 密码解密
- Token 编解码

注意：
- 解密密钥需要与平台侧配置的 aes.secret 一致
- 平台使用 ZeroPadding，密钥不足16字节用0补足

作者：技术团队
版本：1.1
"""

import base64
import json
from typing import Optional, Dict, Any

from ..core.logger import get_logger
from ..core.config import config


class CryptoError(Exception):
    """加解密异常"""
    pass


logger = get_logger('crypto')


def get_aes_key() -> bytes:
    """
    获取 AES 密钥

    密钥处理逻辑必须与平台侧 (Java) 完全一致：
    - 密钥长度 < 16 字节时：补足到 16 字节（用0填充）
    - 密钥长度 >= 16 字节时：截断到 16 字节

    Returns:
        16 字节的密钥
    """
    secret = config.get('aes.secret')
    if not secret:
        raise CryptoError("AES密钥未配置，请检查配置文件中的 aes.secret")

    key = secret.encode('utf-8')

    # 密钥长度不足16字节时补0，超过16字节时截断
    if len(key) < 16:
        key = key + b'\x00' * (16 - len(key))
    elif len(key) > 16:
        key = key[:16]

    return key


def zero_pad(data: bytes, block_size: int = 16) -> bytes:
    """
    ZeroPadding 填充

    数据长度不是 block_size 的倍数时，在末尾添加 0x00 直到满足倍数

    Args:
        data: 原始数据
        block_size: 块大小（默认16）

    Returns:
        填充后的数据
    """
    remainder = len(data) % block_size
    if remainder == 0:
        return data
    padding_len = block_size - remainder
    return data + b'\x00' * padding_len


def zero_unpad(data: bytes) -> bytes:
    """
    移除 ZeroPadding

    移除末尾的 0x00

    Args:
        data: 填充后的数据

    Returns:
        原始数据
    """
    return data.rstrip(b'\x00')


def decrypt_aes_hex(encrypted_hex: str, key: Optional[bytes] = None) -> str:
    """
    AES 解密（十六进制输入）

    匹配平台侧加密方式：
    - AES/ECB/NoPadding
    - ZeroPadding（手动填充）
    - 十六进制输出

    Args:
        encrypted_hex: 十六进制加密字符串
        key: AES密钥（可选，默认使用配置密钥）

    Returns:
        明文字符串

    Raises:
        CryptoError: 解密失败
    """
    if not encrypted_hex:
        raise CryptoError("密文不能为空")

    try:
        if key is None:
            key = get_aes_key()

        encrypted_bytes = bytes.fromhex(encrypted_hex)

        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(encrypted_bytes)

        decrypted = zero_unpad(decrypted)

        return decrypted.decode('utf-8')

    except Exception as e:
        logger.error(f"AES解密失败: {e}")
        raise CryptoError(f"AES解密失败: {str(e)}")


def decrypt_aes_base64(encrypted_base64: str, key: Optional[bytes] = None) -> str:
    """
    AES 解密（Base64输入）

    Args:
        encrypted_base64: Base64加密字符串
        key: AES密钥（可选）

    Returns:
        明文字符串
    """
    if not encrypted_base64:
        raise CryptoError("密文不能为空")

    try:
        if key is None:
            key = get_aes_key()

        encrypted_bytes = base64.b64decode(encrypted_base64)

        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(encrypted_bytes)

        decrypted = zero_unpad(decrypted)

        return decrypted.decode('utf-8')

    except Exception as e:
        logger.error(f"AES Base64解密失败: {e}")
        raise CryptoError(f"AES Base64解密失败: {str(e)}")


def decrypt_password(encrypted_password: str) -> str:
    """
    解密密码（统一入口）

    支持两种格式：
    1. 十六进制加密字符串
    2. Base64加密字符串

    Args:
        encrypted_password: 加密的密码字符串

    Returns:
        明文密码
    """
    if not encrypted_password:
        return ""

    if encrypted_password.startswith('hex:'):
        encrypted = encrypted_password[4:]
        return decrypt_aes_hex(encrypted)
    elif is_base64(encrypted_password):
        return decrypt_aes_base64(encrypted_password)
    else:
        return decrypt_aes_hex(encrypted_password)


def is_base64(s: str) -> bool:
    """检查字符串是否为Base64"""
    if not s:
        return False
    try:
        base64.b64decode(s, validate=True)
        return True
    except:
        return False


def encrypt_aes_hex(plain_text: str, key: Optional[bytes] = None) -> str:
    """
    AES 加密（十六进制输出）

    用于测试对比

    Args:
        plain_text: 明文字符串
        key: AES密钥（可选）

    Returns:
        十六进制加密字符串
    """
    if not plain_text:
        raise CryptoError("明文不能为空")

    try:
        if key is None:
            key = get_aes_key()

        from Crypto.Cipher import AES
        padded = zero_pad(plain_text.encode('utf-8'))
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted = cipher.encrypt(padded)

        return encrypted.hex()

    except Exception as e:
        logger.error(f"AES加密失败: {e}")
        raise CryptoError(f"AES加密失败: {str(e)}")


def decrypt_json(encrypted_json: str) -> Dict[str, Any]:
    """
    解密 JSON 字符串

    Args:
        encrypted_json: 加密的 JSON 字符串

    Returns:
        解密后的字典
    """
    try:
        decrypted = decrypt_password(encrypted_json)
        return json.loads(decrypted)
    except json.JSONDecodeError as e:
        raise CryptoError(f"JSON解析失败: {str(e)}")


def safe_decrypt(encrypted: str, default: str = "") -> str:
    """
    安全解密（不抛出异常）

    Args:
        encrypted: 加密字符串
        default: 解密失败时返回的默认值

    Returns:
        明文字符串或默认值
    """
    try:
        return decrypt_password(encrypted)
    except Exception as e:
        logger.warning(f"安全解密失败: {e}")
        return default


def test_encryption():
    """
    测试加密解密是否匹配

    用于验证平台侧和Agent侧的加密逻辑是否一致
    """
    test_key = b'test_aes_secret!'  # 16字节测试密钥

    test_cases = [
        "password123",
        "MyP@ssw0rd!",
        "中文密码测试",
        "a" * 100,
    ]

    print("=" * 60)
    print("AES 加解密一致性测试")
    print("=" * 60)

    for plain in test_cases:
        encrypted = encrypt_aes_hex(plain, test_key)
        decrypted = decrypt_aes_hex(encrypted, test_key)

        match = plain == decrypted
        status = "✅ PASS" if match else "❌ FAIL"

        print(f"\n原文: {plain[:50]}{'...' if len(plain) > 50 else ''}")
        print(f"密文: {encrypted[:64]}{'...' if len(encrypted) > 64 else ''}")
        print(f"解密: {decrypted[:50]}{'...' if len(decrypted) > 50 else ''}")
        print(f"结果: {status}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_encryption()
