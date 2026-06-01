"""
Xbox 串流 Token 修复脚本
======================

使用方法:
1. 直接运行此脚本自动修复
2. 或手动编辑 src/agent/auth/microsoft_auth_msal.py

修复内容:
- 第 1065 行：将 get_xbox_tokens() 改为 get_xbox_tokens_with_gssv()
"""

import os
import sys


def fix_token_issue():
    """修复 Xbox 串流 Token 获取问题"""
    
    print("="*60)
    print("Xbox 串流 Token 修复脚本")
    print("="*60)
    
    # 文件路径
    file_path = os.path.join(
        os.path.dirname(__file__),
        'src', 'agent', 'auth', 'microsoft_auth_msal.py'
    )
    
    if not os.path.exists(file_path):
        print(f"\n[错误] 文件不存在: {file_path}")
        print("请确保在 bend-agent 目录下运行此脚本")
        return False
    
    print(f"\n[1] 读取文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"[OK] 成功读取文件，共 {len(lines)} 行")
        
        # 查找需要修改的行
        target_line_old = "return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)"
        target_line_new = "return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)"
        
        found = False
        line_number = None
        
        for i, line in enumerate(lines):
            if target_line_old in line and '_get_xbox_live_tokens' in ''.join(lines[max(0, i-5):i+1]):
                found = True
                line_number = i + 1  # 行号从 1 开始
                print(f"\n[2] 找到需要修复的代码 (第 {line_number} 行):")
                print(f"    {lines[i].strip()}")
                break
        
        if not found:
            print("\n[警告] 未找到需要修复的代码")
            print("可能已经修复，或者代码格式不同")
            
            # 尝试查找 get_xbox_tokens_with_gssv 是否已存在
            for i, line in enumerate(lines):
                if 'get_xbox_tokens_with_gssv' in line and '_get_xbox_live_tokens' in ''.join(lines[max(0, i-5):i+1]):
                    print(f"\n[提示] 似乎已经使用了 get_xbox_tokens_with_gssv (第 {i+1} 行)")
                    print(f"    {lines[i].strip()}")
                    return True
            
            return False
        
        # 执行修复
        print(f"\n[3] 执行修复...")
        
        # 备份原文件
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"[OK] 已创建备份: {backup_path}")
        
        # 修改文件
        lines[line_number - 1] = lines[line_number - 1].replace(
            target_line_old,
            target_line_new
        )
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"[OK] 文件已更新")
        
        # 验证修复
        print(f"\n[4] 验证修复...")
        with open(file_path, 'r', encoding='utf-8') as f:
            new_lines = f.readlines()
        
        if target_line_new in new_lines[line_number - 1]:
            print(f"[OK] ✓ 修复成功！第 {line_number} 行已更新")
            print(f"\n[修复后的代码]:")
            print(f"    {new_lines[line_number - 1].strip()}")
            return True
        else:
            print(f"[错误] 修复验证失败")
            return False
        
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fix():
    """测试修复后的 Token 获取"""
    
    print("\n" + "="*60)
    print("测试修复后的 Token 获取")
    print("="*60)
    
    # 检查模块是否可导入
    try:
        from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator
        print("[OK] 模块导入成功")
    except ImportError as e:
        print(f"[错误] 模块导入失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    # 执行修复
    success = fix_token_issue()
    
    if success:
        print("\n" + "="*60)
        print("✓ 修复完成！")
        print("="*60)
        print("\n下一步操作:")
        print("1. 运行测试脚本验证修复:")
        print("   python test_xbox_auth_debug.py")
        print("")
        print("2. 运行串流测试:")
        print("   python -m agent.automation.step2_xbox_streaming")
        print("")
        print("3. 如果仍有问题，请检查:")
        print("   - Token 是否过期 (需要重新认证)")
        print("   - 网络连接是否正常")
        print("   - Xbox 主机是否在线")
        print("")
        print("4. 如需回滚，运行:")
        print("   copy src\\agent\\auth\\microsoft_auth_msal.py.backback src\\agent\\auth\\microsoft_auth_msal.py")
    else:
        print("\n" + "="*60)
        print("✗ 修复失败，请手动检查代码")
        print("="*60)
        print("\n手动修复方法:")
        print("1. 打开文件: src/agent/auth/microsoft_auth_msal.py")
        print("2. 找到方法: _get_xbox_live_tokens")
        print("3. 找到代码行: return await xbox_client.get_xbox_tokens(...)")
        print("4. 改为: return await xbox_client.get_xbox_tokens_with_gssv(...)")
