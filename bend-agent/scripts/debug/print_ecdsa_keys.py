"""
打印 ECDSA 密钥信息，格式与 XStreamingDesktop 一致
"""

import base64
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def generate_and_print_keys():
    """生成并打印 ECDSA 密钥对"""
    print("="*60)
    print("ECDSA 密钥对信息 (XStreamingDesktop 格式)")
    print("="*60)
    
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
    private_b64 = base64.b64encode(private_bytes).decode('ascii')
    
    jwt_keys = {
        "alg": "ES256",
        "kty": "EC",
        "crv": "P-256",
        "x": x,
        "y": y
    }
    
    print("\nJWT Keys (ProofKey):")
    print(json.dumps(jwt_keys, indent=2))
    
    print("\nPrivate Key (Base64, DER format):")
    print(private_b64)
    
    print("\nPublic Key (Base64, uncompressed X9.62):")
    print(base64.b64encode(public_bytes_uncompressed).decode('ascii'))
    
    print("\n" + "="*60)
    print("使用说明:")
    print("="*60)
    print("1. 将 JWT Keys 复制到 ProofKey 字段中")
    print("2. 将 Private Key 保存到文件，以便在 XStreamingDesktop 和 Python 之间共享")
    
    return jwt_keys, private_b64


if __name__ == "__main__":
    generate_and_print_keys()
