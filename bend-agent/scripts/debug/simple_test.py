"""
简单验证修复
============

直接测试 GSSV Token 获取
"""

import asyncio
import aiohttp
import json

async def test():
    # 读取 Refresh Token
    with open("d:/auto-xbox/team-management/bend-agent/tokens/refresh_tokens.json") as f:
        tokens = json.load(f)
    
    refresh_token = tokens.get("jwdong1991@outlook.com")
    print(f"Refresh Token: {refresh_token[:30]}...")
    
    # 获取 Access Token
    print("\n[1] 获取 Access Token...")
    url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": "1f907974-e22b-4810-a9de-d9647380c97e",
        "refresh_token": refresh_token
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            result = await resp.json()
            access_token = result["access_token"]
            print(f"OK: {access_token[:30]}...")
        
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
        
        async with session.post(url, json=body, headers={"Content-Type": "application/json"}) as resp:
            data = await resp.json()
            user_token = data.get("Token")
            print(f"OK: {user_token[:30]}...")
        
        # GSSV Token (使用修复后的方式)
        print("\n[3] 获取 GSSV Token (修复后)...")
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        body = {
            "RelyingParty": "http://gssv.xboxlive.com/",
            "TokenType": "JWT",
            "Properties": {
                "UserTokens": [user_token],  # 直接使用 Xbox User Token
                "SandboxId": "RETAIL"
            }
        }
        headers = {
            "x-xbl-contract-version": "1",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/"
        }
        
        async with session.post(url, json=body, headers=headers) as resp:
            print(f"状态码: {resp.status}")
            text = await resp.text()
            
            if resp.status == 200:
                data = json.loads(text)
                gssv_token = data.get("Token")
                print(f"OK: {gssv_token[:30]}...")
                
                # 获取 gsToken
                print("\n[4] 获取 gsToken...")
                url = "https://xhome.gssv-play-prod.xboxlive.com/v2/login/user"
                body = {
                    "token": gssv_token,
                    "offeringId": "xhome"
                }
                headers = {
                    "Content-Type": "application/json",
                    "x-gssv-client": "XboxComBrowser"
                }
                
                async with session.post(url, json=body, headers=headers) as resp:
                    data = await resp.json()
                    gs_token = data.get("gsToken")
                    
                    if gs_token:
                        print("\n" + "="*70)
                        print(" ✅ 修复成功！gsToken 获取到了！")
                        print("="*70)
                        print(f"\ngsToken: {gs_token[:50]}...")
                    else:
                        print(f"\n响应: {json.dumps(data, indent=2)}")
            else:
                print(f"失败: {text}")

if __name__ == "__main__":
    asyncio.run(test())
