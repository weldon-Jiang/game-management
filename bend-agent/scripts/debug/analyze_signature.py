"""
详细分析签名算法的每个步骤，对比 XStreamingDesktop
"""

import base64
import json
import time
import struct
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import load_der_private_key, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.backends import default_backend


class SignatureAnalyzer:
    """分析签名算法的每个步骤"""
    
    def __init__(self):
        self.private_key = None
        self.public_key = None
        self.keys = None
    
    def generate_keys(self):
        """生成密钥对"""
        self.private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self.public_key = self.private_key.public_key()
        
        # 原始私钥 (PKCS8 DER)
        private_bytes = self.private_key.private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )
        
        # 公钥 (uncompressed)
        public_bytes_uncompressed = self.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        self.keys = {
            'private': private_bytes,
            'public': public_bytes_uncompressed,
            'jwt': {
                'alg': 'ES256',
                'kty': 'EC',
                'crv': 'P-256',
                'x': base64.b64encode(public_bytes_uncompressed[1:33]).decode('ascii'),
                'y': base64.b64encode(public_bytes_uncompressed[33:65]).decode('ascii')
            }
        }
        
        return self.keys
    
    def analyze_signing_buffer(self, url, authorization_token, payload):
        """分析签名缓冲区的构造"""
        print("\n" + "="*60)
        print("签名缓冲区分析")
        print("="*60)
        
        windows_timestamp = (int(time.time()) + 11644473600) * 10000000
        
        print(f"\n1. 时间戳:")
        print(f"   Unix 时间: {int(time.time())}")
        print(f"   Windows 时间戳: {windows_timestamp}")
        print(f"   二进制 (hex): {windows_timestamp.to_bytes(8, 'big').hex()}")
        print(f"   小端 (hex): {windows_timestamp.to_bytes(8, 'little').hex()}")
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path
        
        print(f"\n2. URL 解析:")
        print(f"   完整 URL: {url}")
        print(f"   路径: '{path}'")
        print(f"   路径长度: {len(path)}")
        
        print(f"\n3. 字符串长度:")
        print(f"   'POST': {len('POST')}")
        print(f"   path: {len(path)}")
        print(f"   authorization_token: {len(authorization_token)}")
        print(f"   payload: {len(payload)}")
        
        alloc_size = 5 + 9 + 5 + len(path) + 1 + len(authorization_token) + 1 + len(payload) + 1
        print(f"\n4. 缓冲区大小:")
        print(f"   计算: 5 + 9 + 5 + {len(path)} + 1 + {len(authorization_token)} + 1 + {len(payload)} + 1 = {alloc_size}")
        
        buf = bytearray(alloc_size)
        
        print(f"\n5. 缓冲区结构:")
        
        # 偏移量 0-4: version (1) + padding
        struct.pack_into('>I', buf, 0, 1)
        buf[4] = 0
        print(f"   [0-4] version=1, padding=0: {buf[0:5].hex()}")
        
        # 偏移量 5-13: timestamp (Q = 8 bytes)
        struct.pack_into('>Q', buf, 5, windows_timestamp)
        buf[13] = 0
        print(f"   [5-13] timestamp, padding: {buf[5:14].hex()}")
        
        offset = 14
        print(f"\n   [14-17] POST method:")
        buf[offset:offset + 4] = b'POST'
        buf[offset + 4] = 0
        print(f"   '{buf[offset:offset+5].decode('ascii', errors='replace')}' -> {buf[offset:offset+5].hex()}")
        offset = offset + 4 + 1
        
        print(f"\n   [{offset}-{offset+len(path)}] path:")
        path_bytes = path.encode('utf-8')
        buf[offset:offset + len(path_bytes)] = path_bytes
        buf[offset + len(path_bytes)] = 0
        print(f"   '{path}' -> {path_bytes.hex()}")
        offset = offset + len(path_bytes) + 1
        
        print(f"\n   [{offset}-{offset+len(authorization_token)}] auth:")
        auth_bytes = authorization_token.encode('utf-8')
        buf[offset:offset + len(auth_bytes)] = auth_bytes
        buf[offset + len(auth_bytes)] = 0
        if authorization_token:
            print(f"   '{authorization_token}' -> {auth_bytes.hex()}")
        else:
            print(f"   '' (empty)")
        offset = offset + len(auth_bytes) + 1
        
        print(f"\n   [{offset}-{offset+len(payload)}] payload:")
        payload_bytes = payload.encode('utf-8')
        buf[offset:offset + len(payload_bytes)] = payload_bytes
        buf[offset + len(payload_bytes)] = 0
        print(f"   payload length: {len(payload_bytes)}")
        print(f"   payload preview: {payload_bytes[:50]}...")
        
        print(f"\n6. 完整缓冲区:")
        print(f"   长度: {len(buf)}")
        print(f"   Hex: {buf.hex()}")
        
        return bytes(buf)
    
    def sign(self, url, authorization_token, payload):
        """执行签名"""
        keys = self.keys
        buf = self.analyze_signing_buffer(url, authorization_token, payload)
        
        print("\n" + "="*60)
        print("签名过程")
        print("="*60)
        
        private_key = load_der_private_key(keys['private'], password=None, backend=default_backend())
        signature_der = private_key.sign(buf, ec.ECDSA(hashes.SHA256()))
        
        print(f"\n1. DER 签名:")
        print(f"   长度: {len(signature_der)} bytes")
        print(f"   Hex: {signature_der.hex()}")
        
        # 解析 DER
        r_offset = 4
        r_len = signature_der[3]
        s_offset = r_offset + r_len + 2
        s_len = signature_der[s_offset - 1]
        
        print(f"\n2. DER 解析:")
        print(f"   r_offset: {r_offset}")
        print(f"   r_len: {r_len}")
        print(f"   s_offset: {s_offset}")
        print(f"   s_len: {s_len}")
        
        r = signature_der[r_offset:r_offset + r_len]
        s = signature_der[s_offset:s_offset + s_len]
        
        print(f"\n3. 原始 r 和 s:")
        print(f"   r: {r.hex()}")
        print(f"   s: {s.hex()}")
        
        # 移除前导零
        if len(r) > 0 and r[0] == 0:
            r = r[1:]
            print(f"   r (移除前导零): {r.hex()}")
        if len(s) > 0 and s[0] == 0:
            s = s[1:]
            print(f"   s (移除前导零): {s.hex()}")
        
        # 填充到 32 字节
        r = b'\x00' * (32 - len(r)) + r
        s = b'\x00' * (32 - len(s)) + s
        
        print(f"\n4. 填充后的 r 和 s:")
        print(f"   r: {r.hex()} (长度: {len(r)})")
        print(f"   s: {s.hex()} (长度: {len(s)})")
        
        signature = r + s
        
        print(f"\n5. IEEE-P1363 签名:")
        print(f"   长度: {len(signature)} bytes")
        print(f"   Hex: {signature.hex()}")
        
        # 构造 header
        windows_timestamp = (int(time.time()) + 11644473600) * 10000000
        header = bytearray(12 + len(signature))
        struct.pack_into('>I', header, 0, 1)
        struct.pack_into('>Q', header, 4, windows_timestamp)
        header[12:12 + len(signature)] = signature
        
        print(f"\n6. 最终签名 (带 header):")
        print(f"   长度: {len(header)} bytes")
        print(f"   [0-4] header: {header[0:4].hex()}")
        print(f"   [4-12] timestamp: {header[4:12].hex()}")
        print(f"   [12-76] signature: {header[12:].hex()}")
        print(f"   Base64: {base64.b64encode(bytes(header)).decode('ascii')}")
        
        return bytes(header)


def main():
    analyzer = SignatureAnalyzer()
    keys = analyzer.generate_keys()
    
    print("="*60)
    print("ECDSA 签名算法详细分析")
    print("="*60)
    
    print(f"\n密钥信息:")
    print(f"  ProofKey x: {keys['jwt']['x']}")
    print(f"  ProofKey y: {keys['jwt']['y']}")
    
    url = "https://sisu.xboxlive.com/authorize"
    authorization_token = ""
    payload = json.dumps({
        "AccessToken": "t=test_token",
        "AppId": "000000004c20a908",
        "DeviceToken": "test_device_token",
        "Sandbox": "RETAIL",
        "SiteName": "user.auth.xboxlive.com",
        "UseModernGamertag": True,
        "ProofKey": {
            "use": "sig",
            "alg": "ES256",
            "kty": "EC",
            "crv": "P-256",
            "x": keys['jwt']['x'],
            "y": keys['jwt']['y']
        }
    })
    
    signature = analyzer.sign(url, authorization_token, payload)
    
    print("\n" + "="*60)
    print("分析完成")
    print("="*60)
    print("\n请使用 XStreamingDesktop 的相同参数进行测试，对比结果。")


if __name__ == "__main__":
    main()
