"""
Xbox Live 完整认证模块
=====================

参考 XStreamingDesktop (https://github.com/freexbox/XStreamingDesktop) 的认证流程实现。

完整认证流程：
1. ECDSA 密钥对生成
2. Device Token 获取 (https://device.auth.xboxlive.com/device/authenticate)
3. MSAL Token 获取 (使用 refresh_token 获取 access_token)
4. Xbox User Token 获取 (使用 MSAL access_token)
5. Sisu Authorization (MSAL access_token + Device Token → SisuToken)
6. XSTS Token 获取 (使用 SisuToken 中的 UserToken)
7. Streaming Token 获取 (gsToken)

作者：技术团队
版本：1.2
"""

import asyncio
import aiohttp
import json
import uuid
import base64
import time
import os
import hashlib
import logging
import struct
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class XboxAuthTokens:
    """Xbox 认证结果"""
    user_token: Optional[str] = None
    xsts_token: Optional[str] = None
    user_hash: Optional[str] = None
    device_token: Optional[str] = None
    sisu_token: Optional[Dict[str, Any]] = None
    xhome_token: Optional[str] = None
    gs_token: Optional[str] = None
    msal_access_token: Optional[str] = None


class ECDSAManager:
    """ECDSA 密钥管理器"""
    
    def __init__(self):
        self._keys: Optional[Dict[str, Any]] = None
    
    def generate_keys(self) -> Dict[str, Any]:
        """生成 ECDSA P-256 密钥对"""
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
        except ImportError:
            logger.error("需要安装 cryptography 库: pip install cryptography")
            raise
        
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
        
        self._keys = {
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
        
        logger.info("ECDSA 密钥对生成成功")
        return self._keys
    
    def get_keys(self) -> Dict[str, Any]:
        """获取密钥对，如果不存在则生成"""
        if self._keys is None:
            return self.generate_keys()
        return self._keys
    
    def sign(self, url: str, authorization_token: str, payload: str, keys: Dict[str, Any]) -> bytes:
        """
        使用 ECDSA 签名请求 (参考 XStreamingDesktop)
        
        签名格式：Windows 格式时间戳 + IEEE-P1363 签名
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_der_private_key
        from cryptography.hazmat.backends import default_backend
        from urllib.parse import urlparse
        
        windows_timestamp = (int(time.time()) + 11644473600) * 10000000
        
        parsed = urlparse(url)
        path = parsed.path
        
        alloc_size = 5 + 9 + 5 + len(path) + 1 + len(authorization_token) + 1 + len(payload) + 1
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
        
        private_key = load_der_private_key(keys['private'], password=None, backend=default_backend())
        signature_der = private_key.sign(bytes(buf), ec.ECDSA(hashes.SHA256()))
        
        # DER 转 IEEE-P1363
        # DER 格式: 30 <len> 02 <r_len> <r> 02 <s_len> <s>
        r_offset = 4
        r_len = signature_der[3]
        s_offset = r_offset + r_len + 2
        s_len = signature_der[s_offset - 1]
        
        r = signature_der[r_offset:r_offset + r_len]
        s = signature_der[s_offset:s_offset + s_len]
        
        # 移除 DER 编码的前导零（用于表示正数）
        if len(r) > 0 and r[0] == 0:
            r = r[1:]
        if len(s) > 0 and s[0] == 0:
            s = s[1:]
        
        # 确保是 32 字节
        r = b'\x00' * (32 - len(r)) + r
        s = b'\x00' * (32 - len(s)) + s
        
        signature = r + s
        
        # 头部：1 (4字节) + timestamp (8字节) + signature
        header = bytearray(12 + len(signature))
        struct.pack_into('>I', header, 0, 1)
        struct.pack_into('>Q', header, 4, windows_timestamp)
        header[12:12 + len(signature)] = signature
        
        return bytes(header)


class XboxAuth:
    """Xbox Live 完整认证类"""
    
    DEVICE_AUTH_URL = "https://device.auth.xboxlive.com/device/authenticate"
    SISU_AUTH_URL = "https://sisu.xboxlive.com/authenticate"
    SISU_AUTHORIZE_URL = "https://sisu.xboxlive.com/authorize"
    XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
    XHOME_TOKEN_URL = "https://xhome.gssv-play-prod.xboxlive.com/v2/login/user"
    XAL_USER_TOKEN_URL = "https://user.auth.xboxlive.com/user/authenticate"
    
    # login.live.com 是 Xbox 认证使用的端点
    LIVE_TOKEN_URL = "https://login.live.com/oauth20_token.srf"
    
    APP_ID = "000000004c20a908"
    TITLE_ID = "328178078"
    REDIRECT_URI = "ms-xal-000000004c20a908://auth"
    
    def __init__(self):
        self._ecdsa = ECDSAManager()
        self._user_token: Optional[Dict[str, Any]] = None
        self._device_token: Optional[Dict[str, Any]] = None
        self._sisu_token: Optional[Dict[str, Any]] = None
        self._xhome_token: Optional[Dict[str, Any]] = None
        self._web_token: Optional[Dict[str, Any]] = None
        self._live_access_token: Optional[str] = None
    
    async def get_device_token(self) -> Dict[str, Any]:
        """获取 Device Token"""
        logger.info("开始获取 Device Token...")
        
        keys = self._ecdsa.get_keys()
        device_id = str(uuid.uuid4()).upper()
        
        payload = {
            "Properties": {
                "AuthMethod": "ProofOfPossession",
                "Id": f"{{{device_id}}}",
                "DeviceType": "Android",
                "SerialNumber": f"{{{device_id}}}",
                "Version": "15.0",
                "ProofKey": {
                    "use": "sig",
                    "alg": "ES256",
                    "kty": "EC",
                    "crv": "P-256",
                    "x": keys['jwt']['x'],
                    "y": keys['jwt']['y']
                }
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
        
        body = json.dumps(payload)
        signature = self._ecdsa.sign(self.DEVICE_AUTH_URL, '', body, keys)
        
        headers = {
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Signature": base64.b64encode(signature).decode('ascii')
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.DEVICE_AUTH_URL, data=body, headers=headers) as resp:
                text = await resp.text()
                if resp.status != 200:
                    logger.error(f"Device Token 失败: {resp.status}, {text}")
                    raise Exception(f"Device Token failed: {resp.status}")
                
                data = await resp.json()
                self._device_token = data
                logger.info("Device Token 获取成功")
                return data
    
    async def get_xbox_user_token(self, live_access_token: str) -> str:
        """
        使用 Live AccessToken 获取 Xbox User Token
        参考 XStreamingDesktop
        """
        logger.info("开始获取 Xbox User Token...")
        
        payload = {
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={live_access_token}"
            }
        }
        
        headers = {
            "x-xbl-contract-version": "1",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.XAL_USER_TOKEN_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Xbox User Token 失败: {resp.status}, {text}")
                    raise Exception(f"Xbox User Token failed: {resp.status}")
                
                data = await resp.json()
                user_token = data.get('Token')
                logger.info("Xbox User Token 获取成功")
                return user_token
    
    async def refresh_live_token(self, refresh_token: str) -> str:
        """
        使用 refresh_token 从 login.live.com 获取 Live Token
        参考 XStreamingDesktop 的 refreshUserToken 方法
        """
        logger.info("从 login.live.com 刷新 Live Token...")
        
        payload = {
            "client_id": self.APP_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "service::user.auth.xboxlive.com::MBI_SSL"
        }
        
        body = "&".join([f"{k}={v}" for k, v in payload.items()])
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-store, must-revalidate, no-cache",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.LIVE_TOKEN_URL, data=body, headers=headers) as resp:
                text = await resp.text()
                if resp.status != 200:
                    logger.error(f"Live Token 刷新失败: {resp.status}, {text}")
                    raise Exception(f"Live Token refresh failed: {resp.status}")
                
                data = await resp.json()
                access_token = data.get('access_token')
                
                if not access_token:
                    logger.error(f"Live Token 响应缺少 access_token: {data}")
                    raise Exception("Live Token response missing access_token")
                
                logger.info("Live Token 刷新成功")
                self._live_access_token = access_token
                return access_token
    
    async def do_sisu_authorization(self, live_access_token: str, device_token: str) -> Dict[str, Any]:
        """
        执行 Sisu Authorization
        使用 Live AccessToken + Device Token 获取 SisuToken
        参考 XStreamingDesktop 的 doSisuAuthorization 方法
        """
        logger.info("开始 Sisu Authorization...")
        
        keys = self._ecdsa.get_keys()
        
        payload = {
            "AccessToken": f"t={live_access_token}",
            "AppId": self.APP_ID,
            "DeviceToken": device_token,
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
        }
        
        body = json.dumps(payload)
        
        signature = self._ecdsa.sign(self.SISU_AUTHORIZE_URL, '', body, keys)
        signature_b64 = base64.b64encode(signature).decode('ascii')
        
        headers = {
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/",
            "signature": signature_b64
        }
        
        print(f"\n[DEBUG] Sisu Authorization 请求详情:")
        print(f"  URL: {self.SISU_AUTHORIZE_URL}")
        print(f"  Body (前500字符): {body[:500]}")
        print(f"  Signature (Base64): {signature_b64[:50]}...")
        print(f"  Headers: {headers}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.SISU_AUTHORIZE_URL, data=body, headers=headers) as resp:
                text = await resp.text()
                print(f"\n[DEBUG] Sisu Authorization 响应详情:")
                print(f"  Status: {resp.status}")
                print(f"  X-Err Header: {resp.headers.get('X-Err', 'N/A')}")
                print(f"  Response Body (前500字符): {text[:500] if text else 'empty'}")
                
                if resp.status != 200:
                    logger.error(f"Sisu Authorization 失败: {resp.status}, {text}")
                    logger.error(f"X-Err Header: {resp.headers.get('X-Err', 'N/A')}")
                    raise Exception(f"Sisu Authorization failed: {resp.status}")
                
                data = await resp.json()
                self._sisu_token = data
                logger.info("Sisu Authorization 成功")
                return data
    
    async def do_xsts_authorization(self, relying_party: str) -> Tuple[str, str]:
        """
        执行 XSTS Authorization
        
        Args:
            relying_party: RelyingParty URI
        
        Returns:
            (XSTSToken, UserHash) 元组
        """
        logger.info(f"开始 XSTS Authorization (RelyingParty: {relying_party})...")
        
        if self._sisu_token is None:
            raise Exception("Sisu Token 未获取")
        
        sisu_user_token = self._sisu_token.get('UserToken', {}).get('Token')
        if not sisu_user_token:
            raise Exception("Sisu Token 格式错误，缺少 UserToken.Token")
        
        payload = {
            "RelyingParty": relying_party,
            "TokenType": "JWT",
            "Properties": {
                "UserTokens": [sisu_user_token],
                "SandboxId": "RETAIL"
            }
        }
        
        headers = {
            "x-xbl-contract-version": "1",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.XSTS_AUTH_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"XSTS Authorization 失败: {resp.status}, {text}")
                    raise Exception(f"XSTS failed: {resp.status}")
                
                data = await resp.json()
                xsts_token = data['Token']
                user_hash = data.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs', '')
                
                logger.info(f"XSTS Authorization 成功, UserHash: {user_hash[:10] if user_hash else 'N/A'}...")
                return xsts_token, user_hash
    
    async def get_stream_token(self, offering_id: str) -> Dict[str, Any]:
        """获取 Streaming Token (xHome 或 xCloud)"""
        logger.info(f"开始获取 Streaming Token (offeringId: {offering_id})...")
        
        xsts_token, user_hash = await self.do_xsts_authorization("http://gssv.xboxlive.com/")
        
        payload = {
            "token": xsts_token,
            "offeringId": offering_id
        }
        
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "x-gssv-client": "XboxComBrowser",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/",
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        url = f"https://{offering_id}.gssv-play-prod.xboxlive.com/v2/login/user"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Streaming Token 获取失败: {resp.status}, {text}")
                    raise Exception(f"StreamToken failed: {resp.status}")
                
                data = await resp.json()
                logger.info(f"{offering_id} Token 获取成功")
                return data
    
    async def get_xhome_token(self) -> str:
        """获取 xHome Token (gsToken)"""
        logger.info("开始获取 xHome Token...")
        
        data = await self.get_stream_token("xhome")
        
        gs_token = data.get('gsToken')
        if not gs_token:
            logger.error(f"xHome Token 响应缺少 gsToken: {data}")
            raise Exception("gsToken not found in xHome response")
        
        logger.info("xHome Token (gsToken) 获取成功")
        return gs_token
    
    async def authenticate_with_refresh_token(self, refresh_token: str) -> XboxAuthTokens:
        """
        使用 refresh_token 执行完整认证流程
        参考 XStreamingDesktop 的 refreshTokens 方法
        
        正确流程：
        1. Live Token (从 login.live.com)
        2. Device Token
        3. Xbox User Token (使用 Live Token)
        4. SisuToken (使用 Live Token + Device Token)
        5. XstsToken (使用 SisuToken.UserToken)
        6. StreamingToken (使用 XstsToken)
        
        Args:
            refresh_token: Microsoft OAuth Refresh Token
        
        Returns:
            XboxAuthTokens 对象
        """
        logger.info("="*60)
        logger.info("开始 Xbox Live 完整认证流程 (RefreshToken模式)")
        logger.info("="*60)
        
        try:
            # 步骤1: 从 login.live.com 获取 Live Token
            live_access_token = await self.refresh_live_token(refresh_token)
            
            # 步骤2: 获取 Device Token
            device_token_data = await self.get_device_token()
            device_token = device_token_data['Token']
            
            # 步骤3: 获取 Xbox User Token
            xbox_user_token = await self.get_xbox_user_token(live_access_token)
            
            # 步骤4: Sisu Authorization (使用 Live Token)
            sisu_data = await self.do_sisu_authorization(live_access_token, device_token)
            
            # 步骤5: XSTS Authorization (使用 SisuToken.UserToken.Token)
            xal_xsts_token, user_hash = await self.do_xsts_authorization("http://xboxlive.com")
            
            # 步骤6: 获取 Streaming Token
            gs_token = await self.get_xhome_token()
            
            logger.info("="*60)
            logger.info("Xbox Live 认证完成!")
            logger.info("="*60)
            logger.info(f"  UserHash: {user_hash}")
            logger.info(f"  gsToken: {gs_token[:50] if gs_token else 'N/A'}...")
            
            return XboxAuthTokens(
                user_token=xbox_user_token,
                xsts_token=xal_xsts_token,
                user_hash=user_hash,
                device_token=device_token,
                sisu_token=sisu_data,
                gs_token=gs_token,
                msal_access_token=live_access_token
            )
            
        except Exception as e:
            logger.error(f"Xbox Live 认证失败: {e}", exc_info=True)
            raise


async def test_xbox_auth():
    """测试 Xbox 认证流程"""
    import sys
    from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator
    
    print("="*60)
    print("Xbox Live 认证测试")
    print("="*60)
    
    try:
        print("\n1. 获取 Microsoft OAuth Token...")
        authenticator = MicrosoftMsalAuthenticator()
        
        auth_result = await authenticator.login_with_credentials(
            "jwdong1991@outlook.com",
            "jwdong@666"
        )
        
        if not auth_result or not auth_result.success:
            print(f"[FAIL] Microsoft OAuth 登录失败")
            return
        
        print(f"[OK] Microsoft OAuth 登录成功")
        access_token = auth_result.microsoft_tokens.access_token
        refresh_token = auth_result.microsoft_tokens.refresh_token
        print(f"  access_token: {access_token[:50]}...")
        print(f"  refresh_token: {refresh_token[:50] if refresh_token else 'N/A'}...")
        
        print("\n2. 使用 Refresh Token 获取 Xbox Live Tokens...")
        xbox_auth = XboxAuth()
        tokens = await xbox_auth.authenticate_with_refresh_token(refresh_token)
        
        print("\n" + "="*60)
        print("认证成功! Token 信息:")
        print("="*60)
        print(f"UserHash: {tokens.user_hash}")
        print(f"gsToken: {tokens.gs_token[:50] if tokens.gs_token else 'N/A'}...")
        
        print("\n3. 测试 gsToken 对 Xbox Live API 的有效性...")
        url = "https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home"
        headers = {
            "Authorization": f"Bearer {tokens.gs_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                print(f"\nGET {url}")
                print(f"Status: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    print(f"[OK] gsToken 有效!")
                    print(f"发现 {data.get('totalItems', 0)} 台 Xbox 主机:")
                    for server in data.get('results', []):
                        print(f"  - {server.get('serverId')}: {server.get('deviceName', 'Unknown')}")
                else:
                    text = await resp.text()
                    print(f"[FAIL] gsToken 无效: {text}")
        
        return tokens
        
    except Exception as e:
        print(f"\n[FAIL] 认证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_xbox_auth())
