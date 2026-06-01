"""
验证 GSSV Token 修复
====================

验证修复后的 GSSV Token 获取
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator


async def verify_fix():
    """验证修复"""
    
    print("="*70)
    print(" 验证 GSSV Token 修复")
    print("="*70)
    
    try:
        print("\n[1] Microsoft OAuth 认证...")
        authenticator = MicrosoftMsalAuthenticator()
        
        auth_result = await authenticator.login_with_credentials(
            "jwdong1991@outlook.com",
            "jwdong@666"
        )
        
        if not auth_result or not auth_result.success:
            print("[FAIL] 认证失败")
            return False
        
        print("[OK] 认证成功")
        
        print("\n[2] 检查 Xbox Tokens...")
        xbox_tokens = auth_result.xbox_tokens
        
        if not xbox_tokens:
            print("[FAIL] Xbox Tokens 为空")
            return False
        
        print(f"  user_token: {'✓' if xbox_tokens.user_token else '✗'}")
        print(f"  xsts_token: {'✓' if xbox_tokens.xsts_token else '✗'}")
        print(f"  user_hash: {xbox_tokens.user_hash}")
        print(f"  gs_token: {'✓' if xbox_tokens.gs_token else '✗'}")
        
        if xbox_tokens.gs_token:
            print("\n" + "="*70)
            print(" ✅ 修复成功！所有 Token 都获取到了！")
            print("="*70)
            print(f"\ngsToken: {xbox_tokens.gs_token[:50]}...")
            return True
        else:
            print("\n" + "="*70)
            print(" ❌ 修复失败，gsToken 仍然为空")
            print("="*70)
            return False
        
    except Exception as e:
        print(f"\n[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    result = await verify_fix()
    
    print("\n" + "="*70)
    if result:
        print("✓ 验证通过！")
    else:
        print("✗ 验证失败")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
