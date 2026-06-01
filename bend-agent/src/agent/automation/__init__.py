"""
Bend Agent 自动化模块
====================

功能说明：
- 负责执行自动化任务步骤（串流账号登录 -> Xbox串流 -> 游戏比赛）
- 支持多并发任务执行，每个串流账号对应一个独立窗口
- 实时同步任务状态到平台

模块结构：
- step1_stream_account_login: 步骤一：串流账号登录
- step2_xbox_streaming: 步骤二：Xbox串流连接
- step3_streaming_init: 步骤三：串流环境初始化
- step4_game_automation: 步骤四：游戏比赛自动化

作者：技术团队
版本：2.0
"""

# 只导出步骤函数，不导入 task 模块以避免初始化问题
__all__ = []