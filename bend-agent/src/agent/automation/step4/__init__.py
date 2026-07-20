"""
Step4 游戏自动化包
===============
从原 3158 行 step4_game_automation.py 按职责拆分为 10 个子模块:

  constants.py      — 场景ID / 游戏配置常量
  setup.py          — 模板校验 / FC 控制器初始化
  task_routing.py   — 任务类型路由与计费
  fc_launcher.py    — FC 启动 / 账号切换 / 失败上报
  transfer_phase.py — 转会阶段编排
  sqb_phase.py      — SQB 比赛阶段编排
  navigator.py      — 游戏模式导航 (转会/SQB/DR/WL)
  match_lifecycle.py — 比赛进入→等待→进行→完成
  post_match.py     — 赛后处理与资源清理

主入口 step4_execute_gaming 仍从 step4_game_automation 导入。
"""
from .orchestrator import step4_execute_gaming

__all__ = ["step4_execute_gaming"]
