"""
并发控制配置说明
=================

本文档说明Agent服务的并发控制机制和配置方案。

一、并发控制位置
================

核心原则：并发控制应在任务调度器层面处理，不在认证模块内部。

任务调度器 (AutomationScheduler)
---------------------------------
位置：src/agent/task/automation_scheduler.py

并发控制机制：
- max_concurrent_tasks: 最大并发任务数（默认10）
- asyncio.Semaphore: 信号量控制并发数
- TaskWindowManager: 窗口管理器控制窗口数量

配置示例：
    scheduler = AutomationScheduler(max_concurrent_tasks=50)

认证模块 (MicrosoftMsalAuthenticator)
------------------------------------
位置：src/agent/auth/microsoft_auth_msal.py

原则：
- 不创建子线程/子协程
- 不使用信号量控制并发
- 专注于认证逻辑
- 并发控制由调用方负责

浏览器自动化 (DeviceCodeAuthenticator)
------------------------------------
位置：src/agent/auth/browser_automation.py

原则：
- 每个实例独立运行
- 无并发控制逻辑
- 由任务调度器控制实例数量

二、设备码获取机制
==================

API端点：
    POST https://login.microsoftonline.com/common/oauth2/v2.0/devicecode

请求参数：
    {
        "client_id": "固定的客户端ID",
        "scope": "固定的权限范围"
    }

关键特性：
1. 不依赖账号信息
   - 只需要client_id和scope
   - 不需要账号邮箱或密码

2. 支持并发获取
   - 微软API设计为可并发调用
   - 每个设备码独立生成
   - 可以同时获取50个设备码

3. 设备码有效期
   - 通常约5-10分钟
   - 过期后需要重新获取
   - 每个设备码只能使用一次

并发场景分析（50个账号同时首次登录）：
-------------------------------------------------
时间线：
T0:  50个任务同时启动
T0:  50个账号同时获取设备码（无限制）
T0:  任务1-50同时进行浏览器登录
T5:  前3个任务完成浏览器登录
T5:  任务4-6开始浏览器登录
T10: 任务7-9开始浏览器登录
...  （轮流进行，直到所有任务完成）

三、浏览器实例数量配置
======================

配置位置：任务调度器初始化参数

默认配置：
    AutomationScheduler(max_concurrent_tasks=10)

50个并发配置：
    AutomationScheduler(max_concurrent_tasks=50)

系统资源建议：
-----------------

内存评估（50个并发浏览器）：
- 每个Chromium实例约占用100-200MB内存
- 50个实例约需5-10GB内存
- 建议系统总内存16GB以上

CPU评估：
- 每个实例约占用5-10% CPU（峰值）
- 50个实例峰值约需250-500% CPU
- 建议多核处理器

网络评估：
- 每个浏览器约占用2-5Mbps带宽
- 50个实例约需100-250Mbps带宽
- 建议千兆网络

配置建议：
-----------

场景1: 小规模（10-20个账号）
    max_concurrent_tasks=10
    系统要求：8GB内存，4核CPU

场景2: 中等规模（20-40个账号）
    max_concurrent_tasks=25
    系统要求：16GB内存，8核CPU

场景3: 大规模（40-50个账号）
    max_concurrent_tasks=50
    系统要求：32GB内存，16核CPU，千兆网络

四、Token存储并发控制
=====================

文件锁机制：
位置：TokenStorage._file_lock (asyncio.Lock)

功能：
- 防止并发写入refresh_tokens.json冲突
- 自动合并其他账号的数据
- 异步操作，不阻塞

原理：
    async with cls._get_file_lock():
        # 读取最新文件内容
        # 合并到缓存
        # 写入文件

安全性：
- 每个写操作都是原子的
- 读操作无需加锁
- 多账号数据不会丢失

五、完整并发流程
================

任务分发层（Platform/Agent）
    │
    ├─→ 任务1 ──→ AutomationScheduler
    │              │
    ├─→ 任务2 ──→ │ ├─→ 并发控制（Semaphore）
    │              │ │
    ├─→ ...        │ ├─→ 创建协程
    │              │ │
    └─→ 任务50 ──→ │ └─→ 独立执行
                       │
                       ├─→ 获取设备码（无限制）
                       ├─→ 浏览器自动化（受限）
                       └─→ 保存Token（带锁）

六、代码示例
===========

1. 创建调度器（50个并发）
    scheduler = AutomationScheduler(max_concurrent_tasks=50)

2. 启动任务
    await scheduler.start_task(
        task_id="task_001",
        streaming_account_email="user1@example.com",
        streaming_account_password="password1",
        game_accounts=[...]
    )

3. 查询状态
    status = scheduler.get_task_status("task_001")
    print(f"任务状态: {status}")

4. 取消任务
    await scheduler.cancel_task("task_001")

七、监控和调试
==============

日志输出：
- automation_scheduler: 任务调度日志
- microsoft_msal_auth: 认证日志
- browser_automation: 浏览器自动化日志
- Token存储: 带锁标记的日志

并发状态监控：
    scheduler.active_task_count  # 当前活跃任务数
    scheduler.max_concurrent      # 最大并发数

浏览器实例监控：
    # 无直接监控，由系统资源决定

八、常见问题
============

Q1: 为什么浏览器登录有延迟？
A1: 因为并发控制，同一时间只有max_concurrent_tasks个浏览器运行。

Q2: 50个账号需要多长时间完成首次登录？
A2: 假设每个登录2分钟，3个并发，约需34分钟。
    计算公式: 50 * 2 / 3 ≈ 34分钟

Q3: 设备码过期怎么办？
A3: 每个设备码有效期约5分钟，超时后会重新获取。

Q4: Token存储冲突怎么办？
A4: 使用asyncio.Lock保护，不会冲突。

Q5: 浏览器实例崩溃会影响其他任务吗？
A5: 不会，每个任务独立协程，互不影响。
"""

# 配置说明结束
