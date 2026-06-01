"""
检查 Xbox 账号信息
==================

检查账号的 Gamertag 和用户信息
"""

import asyncio
import aiohttp
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


async def check_account_info():
    """检查 Xbox 账号信息"""
    
    print("="*70)
    print(" 检查 Xbox 账号信息")
    print("="*70)
    
    try:
        from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator
        
        print("\n[1] Microsoft OAuth 认证...")
        authenticator = MicrosoftMsalAuthenticator()
        
        auth_result = await authenticator.login_with_credentials(
            "jwdong1991@outlook.com",
            "jwdong@666"
        )
        
        if not auth_result or not auth_result.success:
            print("[FAIL] Microsoft OAuth 登录失败")
            return
        
        print("[OK] Microsoft OAuth 登录成功")
        
        msal_token = auth_result.microsoft_tokens.access_token
        xbox_auth = authenticator._xbox_client
        
        print("\n[2] 获取 Xbox User Token...")
        user_token = await xbox_auth._get_xbox_user_token(msal_token)
        if not user_token:
            print("[FAIL] Xbox User Token 获取失败")
            return
        print(f"[OK] Xbox User Token: {user_token[:30]}...")
        
        print("\n[3] 获取 XSTS Token (Xbox Live)...")
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
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as resp:
                status = resp.status
                text = await resp.text()
                
                print(f"状态码: {status}")
                
                if status != 200:
                    print(f"[FAIL] XSTS Token 获取失败")
                    print(f"错误响应: {text}")
                    return
                
                data = json.loads(text)
                xsts_token = data.get("Token")
                print(f"[OK] XSTS Token: {xsts_token[:30]}...")
                
                # 解析 DisplayClaims
                display_claims = data.get("DisplayClaims", {})
                xui_list = display_claims.get("xui", [])
                
                print("\n" + "="*70)
                print(" Xbox 账号信息 (来自 XSTS 响应)")
                print("="*70)
                
                if xui_list:
                    xui = xui_list[0]
                    
                    print("\n【DisplayClaims.xui 字段】:")
                    for key, value in xui.items():
                        print(f"  {key}: {value}")
                    
                    print("\n关键信息:")
                    print(f"  - uhs (User Hash): {xui.get('uhs', 'N/A')}")
                    print(f"  - xid (Xbox User ID): {xui.get('xid', 'N/A')}")
                    print(f"  - gtg (Gamertag): {xui.get('gtg', 'N/A')}")
                    print(f"  - usr (User ID): {xui.get('usr', 'N/A')}")
                    print(f"  - age: {xui.get('age', 'N/A')}")
                    print(f"  - pri (Privileges): {xui.get('priv', 'N/A')}")
                    
                    gamertag = xui.get('gtg', 'N/A')
                    
                    if gamertag and gamertag != 'N/A':
                        print(f"\n[OK] ✓ 找到 Gamertag: {gamertag}")
                    else:
                        print(f"\n[WARN] ✗ 未找到 Gamertag!")
                        print("     这可能表示账号没有创建 Xbox 档案")
                else:
                    print("\n[WARN] ✗ DisplayClaims.xui 为空")
                    print("     账号可能没有 Xbox Live 访问权限")
                
                # 尝试获取 GSSV Token
                print("\n" + "="*70)
                print(" 尝试获取 GSSV Token...")
                print("="*70)
                
                gssv_token = await xbox_auth._get_gssv_token(xsts_token)
                
                if gssv_token:
                    print(f"[OK] GSSV Token: {gssv_token[:30]}...")
                else:
                    print("[FAIL] GSSV Token 获取失败")
                    print(f"\n完整响应: {text}")
        
    except Exception as e:
        print(f"\n[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await check_account_info()


if __name__ == "__main__":
    asyncio.run(main())
