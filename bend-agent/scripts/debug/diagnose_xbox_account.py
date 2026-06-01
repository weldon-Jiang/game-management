"""
Xbox 账号诊断脚本
================

诊断 Xbox 账号问题，获取详细的错误信息
"""

import asyncio
import aiohttp
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator


async def diagnose_xbox_issue():
    """诊断 Xbox 账号问题"""
    
    print("="*70)
    print(" Xbox 账号诊断")
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
            return False
        
        print("[OK] Microsoft OAuth 登录成功")
        
        # 获取各个阶段的 token
        print("\n[2] 检查 Token 获取情况...")
        
        msal_token = auth_result.microsoft_tokens.access_token
        print(f"  MSAL Token: {msal_token[:30]}...")
        
        # 尝试获取 Xbox User Token
        print("\n[3] 测试 Xbox User Token...")
        try:
            xbox_auth = authenticator._xbox_client
            user_token = await xbox_auth._get_xbox_user_token(msal_token)
            if user_token:
                print(f"[OK] Xbox User Token: {user_token[:30]}...")
            else:
                print("[FAIL] Xbox User Token 获取失败")
                return False
        except Exception as e:
            print(f"[FAIL] Xbox User Token 异常: {e}")
        
        # 尝试获取 XSTS Token
        print("\n[4] 测试 XSTS Token...")
        try:
            xsts_token, user_hash = await xbox_auth._get_xsts_token(user_token)
            if xsts_token:
                print(f"[OK] XSTS Token: {xsts_token[:30]}...")
                print(f"     User Hash: {user_hash}")
            else:
                print("[FAIL] XSTS Token 获取失败")
                return False
        except Exception as e:
            print(f"[FAIL] XSTS Token 异常: {e}")
        
        # 尝试获取 GSSV Token (这里会失败)
        print("\n[5] 测试 GSSV Token...")
        print("     ⚠️ 这步很可能会失败，显示详细的错误信息")
        try:
            gssv_token = await xbox_auth._get_gssv_token(xsts_token)
            if gssv_token:
                print(f"[OK] GSSV Token: {gssv_token[:30]}...")
            else:
                print("[FAIL] GSSV Token 获取失败")
                print("\n错误原因分析:")
                print("="*70)
                print("GSSV Token 获取失败通常有以下原因:")
                print("")
                print("1. 【最可能】账号没有 Xbox Live 访问权限")
                print("   → 请检查账号是否:")
                print("     a) 在 account.xbox.com 创建了 Xbox 档案")
                print("     b) 设置了 Gamertag（玩家代号）")
                print("     c) 接受了 Xbox 服务条款")
                print("")
                print("2. 账号地区限制")
                print("   → Xbox Live 在某些地区不可用")
                print("   → 账号注册地区与当前登录地区不一致")
                print("")
                print("3. 未成年人账号")
                print("   → 未满 18 岁需要家长同意")
                print("   → 需要家长添加家庭账户")
                print("")
                print("4. 账号安全问题")
                print("   → 账号被微软临时限制")
                print("   → 需要在 account.microsoft.com 完成验证")
                print("")
                print("="*70)
                
                print("\n[6] 建议的解决步骤:")
                print("="*70)
                print("1. 打开浏览器访问: https://account.xbox.com")
                print("2. 登录账号 jwdong1991@outlook.com")
                print("3. 检查是否需要:")
                print("   - 创建 Xbox 档案")
                print("   - 设置 Gamertag")
                print("   - 接受服务条款")
                print("   - 完成年龄验证")
                print("4. 如果账号是未成年人:")
                print("   - 需要家长账户添加家庭成员")
                print("   - 或者家长同意 Xbox Live 使用")
                print("5. 如果地区不支持:")
                print("   - 可能需要使用其他地区的账号")
                print("="*70)
                
                return False
        except Exception as e:
            print(f"[FAIL] GSSV Token 异常: {e}")
            return False
        
        # 如果 GSSV 成功，尝试获取 gsToken
        print("\n[7] 测试 gsToken...")
        try:
            gs_token = await xbox_auth._get_xhome_token(gssv_token)
            if gs_token:
                print(f"[OK] gsToken: {gs_token[:30]}...")
            else:
                print("[WARN] gsToken 获取失败")
        except Exception as e:
            print(f"[WARN] gsToken 异常: {e}")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 诊断异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n开始诊断...")
    
    result = await diagnose_xbox_issue()
    
    print("\n" + "="*70)
    if result:
        print("✓ 诊断完成，账号应该可以正常使用")
    else:
        print("✗ 诊断发现问题，请查看上述建议")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
