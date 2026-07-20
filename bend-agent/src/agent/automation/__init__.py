"""
Bend Agent 自动化模块
====================

自动化四步骤，每步一个独立子包:

  step1/  — 串流账号认证（xblive SISU 全链路）
  step2/  — 串流握手（GSSV 发现 + WebRTC 握手 / PlayStation）
  step3/  — 串流环境初始化（SDL 窗口 + 帧捕获 + 输入通道）
  step4/  — 游戏比赛自动化（FC 启动 + 转会/SQB/DR/WL）

所有入口统一从子包导入: from .step1 import step1_execute_login 等。

作者：技术团队
版本：3.0
"""

__all__ = []
