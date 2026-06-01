"""
检查 XSTS Token 响应内容
=========================

获取完整的 XSTS Token 响应，查看所有字段
"""

import asyncio
import aiohttp
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator


async def check_xsts_response():
    """检查 XSTS Token 响应"""
    
    print("="*70)
    print(" 检查 XSTS Token 响应内容")
    print("="*70)
    
    try:
        print("\n[1] 尝试 Microsoft OAuth 认证...")
        authenticator = MicrosoftMsalAuthenticator()
        
        auth_result = await authenticator.login_with_credentials(
            "jwdong1991@outlook.com",
            "jwdong@666"
        )
        
        if not auth_result or not auth_result.success:
            print("[FAIL] Microsoft OAuth 登录失败")
            return
        
        print("[OK] Microsoft OAuth 登录成功")
        
        # 获取 MSAL Token
        msal_token = auth_result.microsoft_tokens.access_token
        xbox_auth = authenticator._xbox_client
        
        # 获取 Xbox User Token
        print("\n[2] 获取 Xbox User Token...")
        try:
            user_token = await xbox_auth._get_xbox_user_token(msal_token)
            if user_token:
                print(f"[OK] Xbox User Token: {user_token[:30]}...")
            else:
                print("[FAIL] Xbox User Token 获取失败")
                return
        except Exception as e:
            print(f"[FAIL] Xbox User Token 异常: {e}")
            return
        
        # 获取 XSTS Token (打印完整响应)
        print("\n[3] 获取 XSTS Token 并打印完整响应...")
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        body = {
            "RelyingParty": "http://xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "UserTokens": [user_token],
                "SandboxId": "RETAIL"
            }
        }
        headers = {
            "x-xbl-contract-version": "1"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as resp:
                print(f"\n状态码: {resp.status}")
                print("\n响应头:")
                for key, value in resp.headers.items():
                    if key.lower() not in ['content-length', 'content-type']:
                        print(f"  {key}: {value}")
                
                text = await resp.text()
                print(f"\n响应体 ({len(text)} 字符):")
                print("-"*70)
                
                try:
                    data = json.loads(text)
                    print(json.dumps(data, indent=2))
                    
                    # 解析关键字段
                    print("\n" + "="*70)
                    print(" 关键字段解析:")
                    print("="*70)
                    
                    print(f"\nToken: {data.get('Token', 'N/A')[:50]}...")
                    
                    display_claims = data.get('DisplayClaims', {})
                    print(f"\nDisplayClaims: {json.dumps(display_claims, indent=2)}")
                    
                    xui_list = display_claims.get('xui', [])
                    if xui_list:
                        xui = xui_list[0]
                        print(f"\nXUI (用户信息):")
                        print(f"  - uhs (User Hash): {xui.get('uhs', 'N/A')}")
                        print(f"  - xid (Xbox User ID): {xui.get('xid', 'N/A')}")
                        print(f"  - gamertag: {xui.get('gtg', 'N/A')}")  # gtg 可能是 gamertag
                        print(f"  - age: {xui.get('age', 'N/A')}")
                        print(f"  - privilege: {xui.get('priv', 'N/A')}")
                        print(f"  - unique_user_identifier: {xui.get('uid', 'N/A')}")
                        
                        # 打印所有字段
                        print(f"\n所有 XUI 字段:")
                        for key, value in xui.items():
                            print(f"  {key}: {value}")
                    else:
                        print("\n[注意] DisplayClaims.xui 为空")
                        
                except json.JSONDecodeError:
                    print(text)
                
                print("\n" + "-"*70)
                
                # 尝试获取 GSSV Token
                print("\n[4] 尝试获取 GSSV Token...")
                print("     (这里可能会失败)")
                gssv_token = await xbox_auth._get_gssv_token(data.get('Token'))
                
                if gssv_token:
                    print(f"[OK] GSSV Token: {gssv_token[:30]}...")
                else:
                    print("[FAIL] GSSV Token 获取失败")
                    print("\n这是预期的失败，因为我们还没有处理这个错误")
        
    except Exception as e:
        print(f"\n[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await check_xsts_response()


if __name__ == "__main__":
    asyncio.run(main())
