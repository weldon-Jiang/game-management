"""
使用 Refresh Token 检查 Xbox 账号信息
=======================================

使用已保存的 refresh token 获取 Xbox 账号信息
"""

import asyncio
import aiohttp
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


async def check_account_with_refresh_token():
    """使用 Refresh Token 检查账号信息"""
    
    print("="*70)
    print(" 使用 Refresh Token 检查 Xbox 账号信息")
    print("="*70)
    
    try:
        # 读取 Refresh Token
        tokens_file = "d:/auto-xbox/team-management/bend-agent/tokens/refresh_tokens.json"
        
        print(f"\n[1] 读取 Refresh Token...")
        
        with open(tokens_file, 'r', encoding='utf-8') as f:
            tokens_data = json.load(f)
        
        refresh_token = tokens_data.get("jwdong1991@outlook.com")
        
        if not refresh_token:
            print("[FAIL] 未找到 jwdong1991@outlook.com 的 Refresh Token")
            return
        
        print(f"[OK] Refresh Token: {refresh_token[:30]}...")
        
        # Microsoft OAuth - 使用 Refresh Token
        print("\n[2] 使用 Refresh Token 获取 Access Token...")
        
        authority = "https://login.microsoftonline.com/consumers"
        client_id = "1f907974-e22b-4810-a9de-d9647380c97e"
        
        url = f"{authority}/oauth2/v2.0/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                result = await resp.json()
                
                if resp.status != 200:
                    print(f"[FAIL] Refresh Token 无效或已过期: {result}")
                    print("\n可能的原因:")
                    print("  1. Refresh Token 已过期（通常有效期 90 天）")
                    print("  2. 账号密码已更改")
                    print("  3. 账号被禁用")
                    print("\n解决方案:")
                    print("  需要重新进行设备码认证")
                    return
                
                access_token = result["access_token"]
                new_refresh_token = result.get("refresh_token")
                
                print(f"[OK] Access Token: {access_token[:30]}...")
                
                # 保存新的 Refresh Token
                if new_refresh_token and new_refresh_token != refresh_token:
                    print("\n[OK] Refresh Token 已更新，保存...")
                    tokens_data["jwdong1991@outlook.com"] = new_refresh_token
                    with open(tokens_file, 'w', encoding='utf-8') as f:
                        json.dump(tokens_data, f, indent=2)
                    print("[OK] 已保存新的 Refresh Token")
                
                # Xbox User Token
                print("\n[3] 获取 Xbox User Token...")
                
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
                    print("\n[4] 获取 XSTS Token...")
                    
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
                            
                            # 尝试解析错误
                            try:
                                error_data = json.loads(text)
                                xerr = error_data.get("XErr")
                                if xerr == 2148916262:
                                    print("\n❌ 错误码 2148916262 (0x800704EC):")
                                    print("   账号没有 Xbox Live 访问权限")
                                    print("\n可能的原因:")
                                    print("   1. 账号没有创建 Xbox 档案")
                                    print("   2. 账号所在地区 Xbox Live 不可用")
                                    print("   3. 账号未满 18 岁，需要家长同意")
                                    print("\n解决方案:")
                                    print("   请访问 https://account.xbox.com 检查账号状态")
                            except:
                                pass
                            
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
                            
                            print("\n【DisplayClaims.xui 字段】:")
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
                                
                                # 检查是否有 GSSV Token
                                print("\n[5] 测试获取 GSSV Token...")
                                print("   (这步可能会失败)")
                                
                                gssv_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
                                gssv_body = {
                                    "RelyingParty": "http://gssv.xboxlive.com/",
                                    "TokenType": "JWT",
                                    "Properties": {
                                        "UserTokens": [xsts_token],
                                        "SandboxId": "RETAIL"
                                    }
                                }
                                
                                async with session.post(gssv_url, json=gssv_body, headers=headers) as resp:
                                    text = await resp.text()
                                    status = resp.status
                                    
                                    if status == 200:
                                        print("✅ GSSV Token 获取成功！")
                                        print("   可以正常使用 Xbox 串流功能")
                                    else:
                                        print(f"❌ GSSV Token 获取失败: {status}")
                                        print(f"   响应: {text}")
                                        print("\n   这可能表示账号权限有问题")
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
    await check_account_with_refresh_token()


if __name__ == "__main__":
    asyncio.run(main())
