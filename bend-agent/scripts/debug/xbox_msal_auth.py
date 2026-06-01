"""
Xbox Live 认证模块 (MSAL 方式 - 不需要 ECDSA 签名)
====================================================

参考 XStreamingDesktop (MsalAuthentication.ts + msal.ts) 的实现。

核心优势：
- 不需要 ECDSA 签名，实现更简单
- 使用 Device Code Flow 或直接使用 MSAL Token
- 兼容性好，成功率高

认证流程：
1. Microsoft OAuth Token (MSAL) - 可从 MicrosoftMsalAuthenticator 获取
2. Xbox User Token (使用 MSAL Token)
3. XSTS Token (GSSV)
4. Streaming Token (gsToken)

作者：技术团队
版本：2.0
"""

import asyncio
import aiohttp
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class XboxAuthTokens:
    """Xbox 认证结果"""
    msal_token: Optional[str] = None
    xbox_user_token: Optional[str] = None
    xsts_gssv_token: Optional[str] = None
    xsts_web_token: Optional[str] = None
    user_hash: Optional[str] = None
    gs_token: Optional[str] = None
    xcloud_token: Optional[str] = None


class XboxMsalAuth:
    """
    Xbox Live 认证类 (MSAL 方式)
    
    参考 XStreamingDesktop 的 msal.ts 实现
    """
    
    # API Endpoints
    MSAL_DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
    MSAL_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    XAL_USER_TOKEN_URL = "https://user.auth.xboxlive.com/user/authenticate"
    XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
    LIVE_TOKEN_URL = "https://login.live.com/oauth20_token.srf"
    GSSV_TOKEN_URL_PATTERN = "https://{offering}.gssv-play-prod.xboxlive.com/v2/login/user"
    
    # Client ID for Xbox App
    MSAL_CLIENT_ID = "1f907974-e22b-4810-a9de-d9647380c97e"
    
    def __init__(self):
        self._msal_access_token: Optional[str] = None
        self._xbox_user_token: Optional[str] = None
        self._xsts_token: Optional[str] = None
        self._user_hash: Optional[str] = None
    
    async def device_code_auth(self) -> Tuple[str, Dict[str, Any]]:
        """
        执行 Device Code Flow 认证
        
        Returns:
            (msal_access_token, full_token_data) 元组
        """
        logger.info("开始 Device Code Flow 认证...")
        
        print("\n" + "="*60)
        print("Device Code Flow 认证")
        print("="*60)
        
        # 1. 请求 Device Code
        print("\n1. 请求 Device Code...")
        
        payload = {
            "client_id": self.MSAL_CLIENT_ID,
            "scope": "xboxlive.signin openid profile offline_access"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.MSAL_DEVICE_CODE_URL,
                data="&".join([f"{k}={v}" for k, v in payload.items()]),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Device Code 请求失败: {resp.status}, {text}")
                
                data = await resp.json()
                
                print(f"\n[OK] Device Code 获取成功")
                print(f"  用户代码: {data.get('user_code')}")
                print(f"\n  ⚠️  请访问: {data.get('verification_uri')}")
                print(f"  ⚠️  输入代码: {data.get('user_code')}")
                
                device_code = data.get('device_code')
                interval = data.get('interval', 5)
                expires_in = data.get('expires_in', 900)
                
                # 2. 轮询获取 Token
                print(f"\n2. 等待用户认证 (最多 {expires_in} 秒)...")
                print("   按 Ctrl+C 取消")
                
                start_time = time.time()
                while True:
                    await asyncio.sleep(interval)
                    
                    async with session.post(
                        self.MSAL_TOKEN_URL,
                        data=f"grant_type=urn:ietf:params:oauth:grant-type:device_code&client_id={self.MSAL_CLIENT_ID}&device_code={device_code}",
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    ) as token_resp:
                        token_data = await token_resp.json()
                        
                        if token_resp.status == 200:
                            print(f"\n[OK] ✅ 用户认证成功!")
                            access_token = token_data.get('access_token')
                            print(f"  access_token: {access_token[:50]}...")
                            print(f"  refresh_token: {token_data.get('refresh_token', '')[:30] if token_data.get('refresh_token') else 'N/A'}...")
                            self._msal_access_token = access_token
                            return access_token, token_data
                        elif token_resp.status == 400:
                            error = token_data.get('error')
                            if error == 'authorization_pending':
                                elapsed = int(time.time() - start_time)
                                if elapsed < expires_in:
                                    print(f"   等待中... ({elapsed}/{expires_in} 秒)", end='\r')
                                    continue
                                else:
                                    raise Exception("认证超时")
                            else:
                                raise Exception(f"认证失败: {error} - {token_data.get('error_description', '')}")
                        else:
                            raise Exception(f"Token 请求失败: {token_resp.status}")
    
    async def get_xbox_user_token(self, msal_token: str) -> str:
        """
        使用 MSAL AccessToken 获取 Xbox User Token
        
        参考 msal.ts 的 doXstsAuthentication 方法
        """
        logger.info("获取 Xbox User Token...")
        print(f"  [1/4] 获取 Xbox User Token...")
        
        payload = {
            "Properties": {
                "AuthMethod": "RPS",
                "RpsTicket": f"d={msal_token}",
                "SiteName": "user.auth.xboxlive.com"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
        
        headers = {
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.XAL_USER_TOKEN_URL,
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Xbox User Token 失败: {resp.status}, {text}")
                    raise Exception(f"Xbox User Token failed: {resp.status}")
                
                data = await resp.json()
                token = data.get('Token')
                self._xbox_user_token = token
                logger.info("Xbox User Token 获取成功")
                return token
    
    async def do_xsts_authorization(self, user_token: str, relying_party: str) -> Tuple[str, str]:
        """
        执行 XSTS Authorization
        
        Args:
            user_token: Xbox User Token 或其他 User Token
            relying_party: RelyingParty URI
                         - "http://xboxlive.com" (Web Token)
                         - "http://gssv.xboxlive.com/" (GSSV Token)
        
        Returns:
            (token, user_hash) 元组
        """
        relying_name = "Web" if "xboxlive.com" in relying_party and "gssv" not in relying_party else "GSSV"
        logger.info(f"XSTS Authorization ({relying_name})...")
        print(f"  [{'2' if relying_party == 'http://gssv.xboxlive.com/' else '3'}/4] XSTS Authorization ({relying_name})...")
        
        payload = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [user_token]
            },
            "RelyingParty": relying_party,
            "TokenType": "JWT"
        }
        
        headers = {
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.XSTS_AUTH_URL,
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"XSTS Authorization 失败: {resp.status}, {text}")
                    raise Exception(f"XSTS Authorization failed: {resp.status}")
                
                data = await resp.json()
                token = data.get('Token')
                user_hash = data.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs', '')
                
                logger.info(f"XSTS Authorization 成功, UserHash: {user_hash[:10] if user_hash else 'N/A'}...")
                return token, user_hash
    
    async def get_stream_token(self, xsts_token: str, offering: str) -> Dict[str, Any]:
        """
        获取 Streaming Token
        
        Args:
            xsts_token: XSTS Token (from gssv.xboxlive.com)
            offering: "xhome" 或 "xgpuweb" 或 "xgpuwebf2p"
        
        Returns:
            Streaming Token 数据
        """
        offering_name = "xHome" if offering == "xhome" else "xCloud"
        logger.info(f"获取 Streaming Token ({offering_name})...")
        print(f"  [4/4] 获取 Streaming Token ({offering_name})...")
        
        url = f"https://{offering}.gssv-play-prod.xboxlive.com/v2/login/user"
        
        payload = {
            "token": xsts_token,
            "offeringId": offering
        }
        
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "x-gssv-client": "XboxComBrowser"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Streaming Token 获取失败: {resp.status}, {text}")
                    raise Exception(f"Streaming Token failed: {resp.status}")
                
                data = await resp.json()
                logger.info(f"Streaming Token ({offering}) 获取成功")
                return data
    
    async def get_web_token(self) -> str:
        """
        获取 Web Token (用于 Xbox API 调用)
        """
        if not self._xbox_user_token:
            raise Exception("需要先调用 get_xbox_user_token")
        
        token, _ = await self.do_xsts_authorization(self._xbox_user_token, "http://xboxlive.com")
        return token
    
    async def get_gssv_token(self) -> str:
        """
        获取 GSSV Token (用于串流)
        """
        if not self._xbox_user_token:
            raise Exception("需要先调用 get_xbox_user_token")
        
        token, _ = await self.do_xsts_authorization(self._xbox_user_token, "http://gssv.xboxlive.com/")
        return token
    
    async def get_streaming_tokens(self, msal_token: str) -> XboxAuthTokens:
        """
        获取完整的 Streaming Token (xHome 和 xCloud)
        
        Args:
            msal_token: Microsoft OAuth Access Token
        
        Returns:
            XboxAuthTokens 对象
        """
        logger.info("="*60)
        logger.info("开始获取 Streaming Tokens")
        logger.info("="*60)
        
        # 1. Xbox User Token
        xbox_user_token = await self.get_xbox_user_token(msal_token)
        
        # 2. GSSV Token
        gssv_token = await self.get_gssv_token()
        
        # 3. xHome Token
        xhome_data = await self.get_stream_token(gssv_token, "xhome")
        gs_token = xhome_data.get('gsToken')
        
        # 4. xCloud Token (可能失败)
        xcloud_token = None
        try:
            xcloud_data = await self.get_stream_token(gssv_token, "xgpuweb")
            xcloud_token = xcloud_data.get('gsToken')
        except Exception as e:
            logger.warning(f"xCloud Token 获取失败，尝试 xgpuwebf2p: {e}")
            try:
                xcloud_data = await self.get_stream_token(gssv_token, "xgpuwebf2p")
                xcloud_token = xcloud_data.get('gsToken')
            except Exception as e2:
                logger.warning(f"xgpuwebf2p 也失败: {e2}")
        
        # 5. Web Token
        web_token = await self.get_web_token()
        
        logger.info("="*60)
        logger.info("Streaming Tokens 获取完成!")
        logger.info("="*60)
        logger.info(f"  xHome Token: {gs_token[:30] if gs_token else 'N/A'}...")
        logger.info(f"  xCloud Token: {xcloud_token[:30] if xcloud_token else 'N/A'}...")
        logger.info(f"  Web Token: {web_token[:30]}...")
        
        return XboxAuthTokens(
            msal_token=msal_token,
            xbox_user_token=xbox_user_token,
            xsts_gssv_token=gssv_token,
            xsts_web_token=web_token,
            user_hash=self._user_hash,
            gs_token=gs_token,
            xcloud_token=xcloud_token
        )
    
    async def authenticate_with_msal_token(self, msal_token: str) -> XboxAuthTokens:
        """
        使用已有的 MSAL Token 获取 Xbox Streaming Tokens
        
        Args:
            msal_token: Microsoft OAuth Access Token
        
        Returns:
            XboxAuthTokens 对象
        """
        return await self.get_streaming_tokens(msal_token)
    
    async def discover_consoles(self, gs_token: str) -> list:
        """
        发现 Home Xbox 主机
        
        Args:
            gs_token: xHome Streaming Token
        
        Returns:
            Xbox 主机列表
        """
        logger.info("发现 Home Xbox 主机...")
        
        device_info = {
            "appInfo": {
                "env": {
                    "clientAppId": "www.xbox.com",
                    "clientAppType": "browser",
                    "clientAppVersion": "26.1.97",
                    "clientSdkVersion": "10.3.7",
                    "httpEnvironment": "prod",
                    "sdkInstallId": ""
                }
            },
            "dev": {
                "hw": { "make": "Microsoft", "model": "unknown", "sdktype": "web" },
                "os": { "name": "windows", "ver": "22631.2715", "platform": "desktop" },
                "displayInfo": {
                    "dimensions": { "widthInPixels": 1920, "heightInPixels": 1080 },
                    "pixelDensity": { "dpiX": 1, "dpiY": 1 }
                },
                "browser": { "browserName": "chrome", "browserVersion": "130.0" }
            }
        }
        
        url = "https://xhome.gssv-play-prod.xboxlive.com/v6/servers/home?mr=50"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={
                    "Authorization": f"Bearer {gs_token}",
                    "Content-Type": "application/json",
                    "X-MS-Device-Info": json.dumps(device_info),
                    "Accept": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"发现主机失败: {resp.status}, {text}")
                    raise Exception(f"发现主机失败: {resp.status}")
                
                data = await resp.json()
                consoles = data.get('results', [])
                
                logger.info(f"发现 {len(consoles)} 台 Xbox 主机:")
                for console in consoles:
                    logger.info(f"  - {console.get('id')}: {console.get('name', 'Unknown')}")
                
                return consoles
