"""
直接检查 Xbox 账号信息（使用原生 HTTP）
========================================

绕过高层认证，直接获取 XSTS Token 查看账号信息
"""

import asyncio
import aiohttp
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


async def check_account():
    """直接检查账号信息"""
    
    print("="*70)
    print(" 直接检查 Xbox 账号信息")
    print("="*70)
    
    try:
        from agent.core.logger import get_logger
        
        logger = get_logger('check_account')
        
        # Microsoft OAuth (使用原生 HTTP)
        print("\n[1] Microsoft OAuth 认证...")
        
        authority = "https://login.microsoftonline.com/consumers"
        client_id = "1f907974-e22b-4810-a9de-d9647380c97e"
        scopes = "xboxlive.signin openid profile offline_access"
        
        # 获取设备码
        url = f"{authority}/oauth2/v2.0/devicecode"
        data = {
            "client_id": client_id,
            "scope": scopes
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                result = await resp.json()
                
                if "device_code" not in result:
                    print(f"[FAIL] 获取设备码失败: {json.dumps(result, indent=2)}")
                    return
                
                print(f"\n请访问: {result.get('verification_url', result.get('verification_uri', 'N/A'))}")
                print(f"输入验证码: {result.get('user_code', 'N/A')}")
                print("\n等待认证完成...")
                
                # 轮询获取 Token
                token_url = f"{authority}/oauth2/v2.0/token"
                token_data = {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": client_id,
                    "device_code": result["device_code"]
                }
                
                expires_in = result.get("expires_in", 300)
                max_attempts = int(expires_in / 5) + 10
                
                for attempt in range(max_attempts):
                    await asyncio.sleep(5)
                    
                    async with session.post(token_url, data=token_data) as resp:
                        token_result = await resp.json()
                        
                        if resp.status == 200:
                            access_token = token_result["access_token"]
                            print(f"\n[OK] Microsoft OAuth 成功")
                            print(f"Token: {access_token[:30]}...")
                            break
                        elif token_result.get("error") == "authorization_pending":
                            print(".", end="", flush=True)
                            continue
                        else:
                            print(f"\n[FAIL] OAuth 失败: {token_result}")
                            return
                else:
                    print("\n[FAIL] 认证超时")
                    return
                
                # Xbox User Token
                print("\n[2] 获取 Xbox User Token...")
                
                url = "https://user.auth.xboxlive.com/user/authenticate"
                body = {
                    "RelyingParty": "http://auth.xboxlive.com",
                    "TokenType": "JWT",
                    "Properties": {
                        "AuthMethod": "RPS",
                        "SiteName": "user.auth.xboxlive.com",
                        "RpsTicket": f"d={access_token}"
                    }
                }
                headers = {"Content-Type": "application/json"}
                
                async with session.post(url, json=body, headers=headers) as resp:
                    text = await resp.text()
                    
                    if resp.status != 200:
                        print(f"[FAIL] Xbox User Token 失败: {resp.status}")
                        print(f"响应: {text}")
                        return
                    
                    data = json.loads(text)
                    user_token = data.get("Token")
                    print(f"[OK] Xbox User Token: {user_token[:30]}...")
                    
                    # XSTS Token
                    print("\n[3] 获取 XSTS Token...")
                    
                    url = "https://xsts.auth.xboxlive.com/xsts/authorize"
                    body = {
                        "RelyingParty": "http://xboxlive.com",
                        "TokenType": "JWT",
                        "Properties": {
                            "UserTokens": [user_token],
                            "SandboxId": "RETAIL"
                        }
                    }
                    headers = {"x-xbl-contract-version": "1"}
                    
                    async with session.post(url, json=body, headers=headers) as resp:
                        text = await resp.text()
                        status = resp.status
                        
                        print(f"\n状态码: {status}")
                        
                        if status != 200:
                            print(f"[FAIL] XSTS Token 失败")
                            print(f"响应: {text}")
                            return
                        
                        data = json.loads(text)
                        xsts_token = data.get("Token")
                        print(f"[OK] XSTS Token: {xsts_token[:30]}...")
                        
                        # 解析账号信息
                        display_claims = data.get("DisplayClaims", {})
                        xui_list = display_claims.get("xui", [])
                        
                        print("\n" + "="*70)
                        print(" Xbox 账号信息")
                        print("="*70)
                        
                        if xui_list:
                            xui = xui_list[0]
                            
                            print("\n所有字段:")
                            for key, value in xui.items():
                                print(f"  {key}: {value}")
                            
                            gamertag = xui.get("gtg")
                            user_hash = xui.get("uhs")
                            
                            print("\n" + "-"*70)
                            print(" 关键信息:")
                            print("-"*70)
                            print(f"  Gamertag (gtg): {gamertag or '❌ 未找到'}")
                            print(f"  User Hash (uhs): {user_hash or '❌ 未找到'}")
                            print(f"  Xbox User ID (xid): {xui.get('xid', 'N/A')}")
                            
                            if gamertag:
                                print(f"\n✅ 账号有 Gamertag: {gamertag}")
                                print("   这个 Gamertag 可以用于 Xbox 串流认证")
                            else:
                                print(f"\n❌ 账号没有 Gamertag!")
                                print("   这可能表示账号没有创建 Xbox 档案")
                                print("   请访问 https://account.xbox.com 创建 Xbox 档案")
                        else:
                            print("\n❌ DisplayClaims.xui 为空")
                            print("   账号可能没有 Xbox Live 访问权限")
        
    except Exception as e:
        print(f"\n[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await check_account()


if __name__ == "__main__":
    asyncio.run(main())
