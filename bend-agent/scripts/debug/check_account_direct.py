"""
直接检查 Xbox 账号信息
=======================

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
        # 导入需要的模块
        import msal
        
        # Microsoft OAuth
        print("\n[1] Microsoft OAuth 认证...")
        
        app = msal.ConfidentialClientApplication(
            client_id="1f907974-e22b-4810-a9de-d9647380c97e",
            authority="https://login.microsoftonline.com/consumers",
            client_credential="JDnwH4eGh2eqU2e5wP7wP8eR6wP4wP7w"
        )
        
        # 尝试使用设备码流程
        print("使用设备码认证...")
        flow = app.initiate_device_flow(scopes=[
            "XboxLive.signin",
            "openid",
            "profile",
            "offline_access"
        ])
        
        if "user_code" not in flow:
            print(f"[FAIL] 设备码流程失败: {flow}")
            return
        
        print(f"\n请访问: {flow['verification_url']}")
        print(f"输入验证码: {flow['user_code']}")
        
        result = app.acquire_token_by_device_flow(flow)
        
        if "access_token" not in result:
            print(f"[FAIL] OAuth 失败: {result}")
            return
        
        access_token = result["access_token"]
        print(f"\n[OK] Microsoft OAuth 成功")
        print(f"Token: {access_token[:30]}...")
        
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
        
        async with aiohttp.ClientSession() as session:
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
                    
                    print(f"状态码: {status}")
                    
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
                        
                        print("\n关键信息:")
                        print(f"  Gamertag (gtg): {gamertag or '❌ 未找到'}")
                        print(f"  User Hash (uhs): {user_hash or '❌ 未找到'}")
                        print(f"  Xbox User ID (xid): {xui.get('xid', 'N/A')}")
                        
                        if gamertag:
                            print(f"\n✅ 账号有 Gamertag: {gamertag}")
                        else:
                            print(f"\n❌ 账号没有 Gamertag!")
                            print("   这可能表示账号没有创建 Xbox 档案")
                    else:
                        print("\n❌ DisplayClaims.xui 为空")
        
    except Exception as e:
        print(f"\n[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await check_account()


if __name__ == "__main__":
    asyncio.run(main())
