"""Xbox Live ECDSA 请求签名（对齐 xblauth Authenticator.make_signature）。"""

import base64
from calendar import timegm
from datetime import datetime, timezone
from typing import Any, Dict

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from jose.backends.cryptography_backend import CryptographyECKey
from jose.constants import ALGORITHMS


def make_ms_filetime() -> int:
    epoch_as_filetime = 116444736000000000
    hundreds_of_ns = 10000000
    dt = datetime.now(timezone.utc)
    filetime = epoch_as_filetime + (timegm(dt.timetuple()) * hundreds_of_ns)
    return filetime + (dt.microsecond * 10)


def create_signing_key() -> CryptographyECKey:
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    return CryptographyECKey(private_key, ALGORITHMS.ES256)


def make_signature(
    key: CryptographyECKey,
    method: str,
    path: str,
    authorization: str,
    post_data: bytes,
) -> str:
    nullbyte = 0
    message = bytearray()
    xbl_version = 1
    message += xbl_version.to_bytes(4, "big")
    message += nullbyte.to_bytes(1, "big")
    time_point = make_ms_filetime()
    message += time_point.to_bytes(8, "big")
    message += nullbyte.to_bytes(1, "big")
    message += bytes(method, "utf-8")
    message += nullbyte.to_bytes(1, "big")
    message += bytes(path, "utf-8")
    message += nullbyte.to_bytes(1, "big")
    message += bytes(authorization, "utf-8")
    message += nullbyte.to_bytes(1, "big")
    message += post_data
    message += nullbyte.to_bytes(1, "big")
    sig_bytes = key.sign(bytes(message))
    b64_message = bytearray()
    b64_message += xbl_version.to_bytes(4, "big")
    b64_message += time_point.to_bytes(8, "big")
    b64_message += sig_bytes
    return base64.standard_b64encode(b64_message).decode("ascii")


def proof_key_dict(key: CryptographyECKey) -> Dict[str, Any]:
    pubkey_desc = key.public_key().to_dict()
    pubkey_desc["use"] = "sig"
    return pubkey_desc
