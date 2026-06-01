"""
详细调试 DER 到 IEEE-P1363 的转换
"""

import sys
import os
import base64
import time
import struct
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_der_private_key
from urllib.parse import urlparse


def generate_keys():
    """生成 ECDSA P-256 密钥对"""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_bytes_uncompressed = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    x = base64.b64encode(public_bytes_uncompressed[1:33]).decode('ascii')
    y = base64.b64encode(public_bytes_uncompressed[33:65]).decode('ascii')
    
    return {
        'private': private_bytes,
        'public': public_bytes_uncompressed,
        'jwt': {
            'alg': 'ES256',
            'kty': 'EC',
            'crv': 'P-256',
            'x': x,
            'y': y
        }
    }


def sign_debug(url, authorization_token, payload, keys):
    """详细的签名调试"""
    print("\n" + "="*60)
    print("签名调试")
    print("="*60)
    
    windows_timestamp = (int(time.time()) + 11644473600) * 10000000
    
    print(f"\n1. Windows Timestamp:")
    print(f"   Current Unix time: {int(time.time())}")
    print(f"   Windows timestamp: {windows_timestamp}")
    print(f"   Hex: {hex(windows_timestamp)}")
    
    parsed = urlparse(url)
    path = parsed.path
    
    print(f"\n2. URL Parsing:")
    print(f"   Full URL: {url}")
    print(f"   Path: {path}")
    
    alloc_size = 5 + 9 + 5 + len(path) + 1 + len(authorization_token) + 1 + len(payload) + 1
    print(f"\n3. Buffer Construction:")
    print(f"   alloc_size: {alloc_size}")
    
    buf = bytearray(alloc_size)
    
    struct.pack_into('>I', buf, 0, 1)
    buf[4] = 0
    struct.pack_into('>Q', buf, 5, windows_timestamp)
    buf[13] = 0
    
    offset = 14
    buf[offset:offset + 4] = b'POST'
    buf[offset + 4] = 0
    offset = offset + 4 + 1
    
    path_bytes = path.encode('utf-8')
    buf[offset:offset + len(path_bytes)] = path_bytes
    buf[offset + len(path_bytes)] = 0
    offset = offset + len(path_bytes) + 1
    
    auth_bytes = authorization_token.encode('utf-8')
    buf[offset:offset + len(auth_bytes)] = auth_bytes
    buf[offset + len(auth_bytes)] = 0
    offset = offset + len(auth_bytes) + 1
    
    payload_bytes = payload.encode('utf-8')
    buf[offset:offset + len(payload_bytes)] = payload_bytes
    buf[offset + len(payload_bytes)] = 0
    
    print(f"\n4. Buffer Content (hex):")
    print(f"   First 20 bytes: {buf[:20].hex()}")
    print(f"   Total bytes: {len(buf)}")
    
    private_key = load_der_private_key(keys['private'], password=None, backend=default_backend())
    signature_der = private_key.sign(bytes(buf), ec.ECDSA(hashes.SHA256()))
    
    print(f"\n5. DER Signature:")
    print(f"   Length: {len(signature_der)} bytes")
    print(f"   Hex: {signature_der.hex()}")
    print(f"   Bytes breakdown:")
    print(f"     [0] 0x{signature_der[0]:02x} (SEQUENCE marker)")
    print(f"     [1] 0x{signature_der[1]:02x} (SEQUENCE length)")
    print(f"     [2] 0x{signature_der[2]:02x} (INTEGER marker for r)")
    print(f"     [3] 0x{signature_der[3]:02x} (r length = {signature_der[3]})")
    print(f"     [4] 0x{signature_der[4]:02x} (r[0])")
    
    r_offset = 4
    r_len = signature_der[3]
    s_offset = r_offset + r_len + 2
    s_len = signature_der[s_offset - 1]
    
    print(f"\n6. DER Parsing:")
    print(f"   r_offset: {r_offset}")
    print(f"   r_len: {r_len}")
    print(f"   s_offset: {s_offset}")
    print(f"   s_len: {s_len}")
    
    r = signature_der[r_offset:r_offset + r_len]
    s = signature_der[s_offset:s_offset + s_len]
    
    print(f"\n7. Raw r and s values:")
    print(f"   r: {r.hex()}")
    print(f"   r length: {len(r)} bytes")
    print(f"   s: {s.hex()}")
    print(f"   s length: {len(s)} bytes")
    
    r_original = r
    s_original = s
    
    if len(r) > 0 and r[0] == 0:
        r = r[1:]
        print(f"   r after removing leading zero: {r.hex()} (length: {len(r)})")
    
    if len(s) > 0 and s[0] == 0:
        s = s[1:]
        print(f"   s after removing leading zero: {s.hex()} (length: {len(s)})")
    
    r = b'\x00' * (32 - len(r)) + r
    s = b'\x00' * (32 - len(s)) + s
    
    print(f"\n8. Padded r and s values:")
    print(f"   r: {r.hex()} (length: {len(r)})")
    print(f"   s: {s.hex()} (length: {len(s)})")
    
    signature = r + s
    
    print(f"\n9. IEEE-P1363 Signature:")
    print(f"   Total length: {len(signature)} bytes")
    print(f"   r || s: {signature.hex()}")
    
    header = bytearray(12 + len(signature))
    struct.pack_into('>I', header, 0, 1)
    struct.pack_into('>Q', header, 4, windows_timestamp)
    header[12:12 + len(signature)] = signature
    
    final_signature = bytes(header)
    print(f"\n10. Final Signature (with header):")
    print(f"    Total length: {len(final_signature)} bytes")
    print(f"    Header: {final_signature[:12].hex()}")
    print(f"    Signature: {final_signature[12:].hex()}")
    print(f"    Base64: {base64.b64encode(final_signature).decode('ascii')}")
    
    return final_signature


def main():
    print("DER to IEEE-P1363 Conversion Debug")
    
    keys = generate_keys()
    
    url = "https://sisu.xboxlive.com/authorize"
    authorization_token = ""
    payload = '{"AccessToken": "t=test", "AppId": "test"}'
    
    signature = sign_debug(url, authorization_token, payload, keys)
    
    print("\n" + "="*60)
    print("Test completed")
    print("="*60)


if __name__ == "__main__":
    main()
