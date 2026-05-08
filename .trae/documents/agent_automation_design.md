# Agent 自动化任务实现计划

## 一、需求概述

根据用户需求，Agent自动化任务分为**三个步骤**，每个步骤需要独立方法实现，代码需要详细注释并做好任务拆分。

### 核心原则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     核心原则：一个串流账号 = 一个任务 = 一个窗口              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【并发模型】                                                                 │
│  • 平台触发Agent启动任务后，传入多个串流账号                                    │
│  • Agent并发处理每个串流账号，每个串流账号创建独立窗口                          │
│  • 每个窗口独立执行：登录 → Xbox串流 → 游戏比赛 → 关闭窗口                      │
│                                                                             │
│  【窗口隔离】                                                                 │
│  • 每个串流账号任务运行在独立窗口中                                            │
│  • 窗口包含完整的串流连接和游戏操作                                            │
│  • 任务完成后窗口自动关闭                                                     │
│                                                                             │
│  【任务生命周期】                                                             │
│  • 一个串流账号 → 一个任务对象 → 一个执行窗口                                  │
│  • 任务之间相互独立，互不影响                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 核心功能流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent 自动化任务流程                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  平台触发Agent启动任务（多个串流账号）                                        │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐          │
│  │                    并发处理每个串流账号                          │          │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │          │
│  │  │ 串流账号#1   │  │ 串流账号#2   │  │ 串流账号#N   │          │          │
│  │  │ 窗口#1      │  │ 窗口#2      │  │ 窗口#N      │          │          │
│  │  │ 执行任务#1   │  │ 执行任务#2   │  │ 执行任务#N   │          │          │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │          │
│  └─────────┼────────────────┼────────────────┼─────────────────┘          │
│            │                │                │                            │
│            ▼                ▼                ▼                            │
│  ┌─────────────────────────────────────────────────────────────┐          │
│  │ 每个窗口独立执行四步骤：                                        │          │
│  │                                                              │          │
│  │  【步骤一】串流账号自动登录                                     │          │
│  │  • 使用ROPC流程获取Microsoft Token                             │          │
│  │  • 获取Xbox Live Token                                        │          │
│  │                                                              │          │
│  │  【步骤二】串流Xbox主机                                         │          │
│  │  • 匹配Xbox（指定或自动发现）                                   │          │
│  │  • 建立SmartGlass连接                                          │          │
│  │                                                              │          │
│  │  【步骤三】显卡解码流转                                         │          │
│  │  • GPU解码视频流                                                │          │
│  │  • 窗口显示解码后的画面                                         │          │
│  │                                                              │          │
│  │  【步骤四】截图模板处理与自动化                                 │          │
│  │  • 截图当前画面                                                │          │
│  │  • 模板匹配定位元素                                            │          │
│  │  • OCR识别文字（如账号名称）                                    │          │
│  │  • 手柄操作自动化                                              │          │
│  └────────┬────────────────────────────────────────────────────┘          │
│           │                                                                   │
│           ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐          │
│  │ 任务隔离与异常处理                                             │          │
│  │  • 每个串流账号任务完全隔离，互不影响                          │          │
│  │  • 一个任务异常中断不影响其他任务                              │          │
│  │  • 任务状态和异常信息实时上报平台                              │          │
│  │  • 平台可查看每个任务的执行状态和异常情况                      │          │
│  └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────┐          │
│  │ 任务监控与控制                                                 │          │
│  │  • 平台可查看每个Agent下每个窗口中的执行中的任务               │          │
│  │  • 支持暂停、停止、恢复操作                                     │          │
│  └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 四大核心步骤（最重要）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          四大核心步骤                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【步骤一】串流账号自动登录                                                   │
│  • 使用账号密码直接获取Microsoft OAuth Token                                   │
│  • 绕过微软设备代码登录窗口（ROPC流程）                                        │
│  • 复用现有 MicrosoftAuthenticator 模块                                       │
│                                                                             │
│  【步骤二】串流Xbox主机                                                      │
│  • 与Xbox建立SmartGlass串流连接                                               │
│  • 复用现有 XboxStreamController 模块                                        │
│  • 复用现有 XboxDiscovery 模块（发现局域网Xbox）                               │
│                                                                             │
│  【步骤三】显卡解码流转                                                       │
│  • 接收显卡解码后的视频流（GPU解码）                                           │
│  • 通过Moonlight/Xbox App窗口显示                                             │
│  • 复用现有 VideoFrameCapture 模块（窗口截图）                                │
│                                                                             │
│  【步骤四】截图模板处理与自动化操作                                           │
│  • 模板匹配定位游戏界面元素（复用 TemplateMatcher）                            │
│  • OCR文字识别定位游戏账号名称                                                │
│  • 手柄操作自动化（实体手柄或虚拟手柄）                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent主动上报机制（实时双向同步）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent ⟷ Platform 实时双向同步                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【Agent → Platform 主动上报】                                                │
│                                                                             │
│  • 任务开始时上报                                                            │
│  • 每个步骤完成时上报                                                        │
│  • 比赛完成时立即上报（当前账号、已完成场次）                                  │
│  • 任务异常时上报（包含详细错误信息）                                          │
│  • 任务完成时上报                                                            │
│                                                                             │
│  【Agent → Platform 实时查询】                                                │
│                                                                             │
│  • 比赛开始前：查询游戏账号当天已完成场次（从Platform获取）                     │
│  • 比赛完成后：更新游戏账号当天已完成场次（推送到Platform）                     │
│  • 切换账号前：查询串流账号下所有游戏账号完成情况                               │
│  • 任务结束前：确认所有游戏账号是否都完成当日目标                               │
│                                                                             │
│  【Platform → Agent 下发控制命令】                                            │
│                                                                             │
│  • pause: 暂停任务                                                          │
│  • resume: 恢复任务                                                         │
│  • stop: 停止任务                                                           │
│  • resume_from_breakpoint: 从断点重新执行                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 实时同步数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     游戏账号比赛次数实时同步流程                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【比赛完成时】                                                               │
│                                                                             │
│  Agent                                        Platform                      │
│    │                                              │                          │
│    │  1.比赛完成                                   │                          │
│    │       ↓                                      │                          │
│    │  2.POST /api/task/{taskId}/match/complete   │                          │
│    │     {                                        │                          │
│    │       gameAccountId: "ga_001",              │                          │
│    │       completedCount: 2                     │                          │
│    │     }                                        │                          │
│    │  ─────────────────────────────────────────→ │                          │
│    │                                              ↓                          │
│    │                                   更新 GameAccount.dailyMatchCount        │
│    │                                              │                          │
│    │  3.返回更新后的串流账号下所有游戏账号状态       │                          │
│    │     {                                        │                          │
│    │       allAccounts: [                         │                          │
│    │         {id: "ga_001", completed: 2, target: 3},│                        │
│    │         {id: "ga_002", completed: 3, target: 3},│                        │
│    │         {id: "ga_003", completed: 1, target: 3} │                        │
│    │       ],                                      │                          │
│    │       allCompleted: false  // ga_003未完成    │                          │
│    │     }                                        │                          │
│    │  ←────────────────────────────────────────── │                          │
│    │       ↓                                                              │
│    │  4.判断：是否所有账号都完成？                                          │
│    │       • 未全部完成：切换到下一个未完成的账号继续比赛                    │
│    │       • 全部完成：任务结束，关闭窗口                                   │
│                                                                             │
│  【任务开始时/断点恢复时】                                                     │
│                                                                             │
│  Agent                                        Platform                      │
│    │                                              │                          │
│    │  GET /api/task/{taskId}/game-accounts/status │                          │
│    │  ─────────────────────────────────────────→ │                          │
│    │                                              ↓                          │
│    │                                   查询每个游戏账号当天完成数              │
│    │                                              │                          │
│    │  返回所有账号状态                             │                          │
│    │  ←───────────────────────────────────────── │                          │
│    │       ↓                                                              │
│    │  Agent根据数据决定：                                                  │
│    │       • 从哪个账号开始                                                │
│    │       • 哪些账号已完成目标跳过                                         │
│    │       • 是否需要结束任务                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
```

---

## 二、详细设计

### 2.1 数据结构设计

#### 2.1.1 窗口与任务关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      一个串流账号 = 一个任务 = 一个窗口                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【数据结构映射】                                                            │
│                                                                             │
│  串流账号#1  ──────────────────────────────────────────────────────────     │
│     │                                                                    │
│     ├───→ AgentTaskContext(task_id="task_001")                           │
│     │         │                                                           │
│     │         ├─── streaming_account_id = "sa_001"                       │
│     │         ├─── window_id = "window_001"                               │
│     │         ├─── game_accounts = [ga_1, ga_2, ga_3]                     │
│     │         └─── 执行三步骤                                              │
│     │                                                                    │
│     └───→ 独立窗口(window_001)                                            │
│               └─── Moonlight/Xbox App窗口                                 │
│                                                                             │
│  串流账号#2  ──────────────────────────────────────────────────────────     │
│     │                                                                    │
│     ├───→ AgentTaskContext(task_id="task_002")                           │
│     ...                                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 2.1.2 Agent端新增数据结构

**AgentTaskContext** - Agent任务上下文（贯穿四步骤，每个串流账号独有一份）
```python
@dataclass
class AgentTaskContext:
    """Agent自动化任务上下文

    重要原则：一个AgentTaskContext对象对应一个串流账号、一个任务、一个窗口
    """
    task_id: str                              # 任务ID（唯一标识）
    streaming_account_id: str                 # 串流账号ID
    streaming_account_email: str              # 串流账号邮箱
    streaming_account_password: str           # 串流账号密码（已解密）
    window_id: str                            # 关联的窗口ID（用于窗口管理）
    game_accounts: List[GameAccountInfo]     # 游戏账号列表（该串流账号下的）
    assigned_xbox: Optional[XboxInfo]        # 指定Xbox主机（可选）
    current_xbox: Optional[XboxInfo]         # 当前连接的Xbox主机
    microsoft_auth: Optional[AuthenticationResult]  # 微软认证结果
    xbox_session: Optional[XboxSession]      # Xbox会话
    frame_capture: Any = None                # 画面捕获器（VideoFrameCapture）
    current_game_account_index: int = 0      # 当前处理的游戏账号索引
    current_step: str = "PENDING"            # 当前步骤: STEP1/STEP2/STEP3/STEP4
    matches_completed_today: Dict[str, int] = None  # 每个游戏账号今日完成的比赛数
    task_status: str = "pending"              # 任务状态
    pause_event: asyncio.Event = None         # 暂停事件
    # 用于主动上报
    last_report_time: float = 0              # 上次上报时间
    report_interval: float = 5.0             # 上报间隔（秒）
```

**WindowInfo** - 窗口信息
```python
@dataclass
class WindowInfo:
    """窗口信息

    每个串流账号任务关联一个独立窗口
    """
    window_id: str              # 窗口唯一ID
    streaming_account_id: str   # 关联的串流账号ID
    task_id: str                # 关联的任务ID
    window_handle: int = None   # 窗口句柄
    state: str = "created"      # 窗口状态: created/opening/connected/running/closed
    created_time: float = None # 创建时间
```

**GameAccountInfo** - 游戏账号信息
```python
@dataclass
class GameAccountInfo:
    """游戏账号信息"""
    id: str
    gamertag: str                              # 游戏昵称
    email: str                                 # Xbox Live邮箱
    password: str                             # 密码（已解密）
    is_primary: bool = False                   # 是否为主账号
    matches_today: int = 0                     # 今日已完成比赛数
    target_matches: int = 3                    # 目标比赛数（每天3场）
```

**XboxMatchResult** - Xbox匹配结果
```python
@dataclass
class XboxMatchResult:
    """Xbox匹配结果"""
    success: bool
    xbox_info: Optional[XboxInfo]
    match_type: str  # "assigned" / "discovered" / "random_selected"
    message: str
```

### 2.2 任务状态设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           任务状态流转图                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   PENDING ──→ STEP1_LOGIN ──→ STEP2_STREAM ──→ STEP3_DECODE ──→ STEP4_GAME ──→ COMPLETED  │
│     │             │              │               │                │                  │
│     │             │              │               │                │                  │
│     ▼             ▼              ▼               ▼                ▼                  │
│   FAILED      PAUSED         PAUSED          PAUSED           PAUSED                │
│     │             │              │               │                │                  │
│     │             ▼              ▼               ▼                ▼                  │
│     └──────────→ RUNNING ◄───────┴───────────────┴────────────────┘                  │
│                                │                                              │
│                                ▼                                              │
│                             CANCELLED                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**状态说明：**
- `PENDING`: 任务等待开始
- `STEP1_LOGIN`: 步骤一执行中（串流账号登录）
- `STEP2_STREAM`: 步骤二执行中（Xbox串流连接）
- `STEP3_DECODE`: 步骤三执行中（显卡解码流转）
- `STEP4_GAME`: 步骤四执行中（游戏比赛自动化）
- `PAUSED`: 任务已暂停
- `RUNNING`: 任务运行中（通用）
- `COMPLETED`: 任务已完成
- `FAILED`: 任务失败
- `CANCELLED`: 任务被取消

### 2.3 平台端数据结构扩展

#### 2.3.1 Task实体扩展字段
```java
// 在现有Task实体中增加字段
private String currentStep;          // 当前步骤: STEP1/STEP2/STEP3
private String currentGameAccountId;  // 当前执行的 游戏账号ID
private Integer matchesCompleted;     // 已完成比赛数
private String boundXboxId;          // 绑定的Xbox主机ID（防止抢夺）
```

#### 2.3.2 新增WebSocket消息类型
```java
// Agent -> Platform 消息
public class AgentTaskProgressMessage {
    String taskId;
    String step;                      // 当前步骤
    String status;
    String currentGameAccountId;
    Integer matchesCompleted;
    String message;
}

// Platform -> Agent 消息
public class AgentControlMessage {
    String taskId;
    String action;                    // "pause" / "resume" / "stop"
}
```

---

## 三、Agent端代码实现

### 3.1 现有模块复用

Agent已有以下成熟模块可供复用：

```
bend-agent/src/agent/
├── auth/
│   └── microsoft_auth.py               # ✅ 微软账号认证（已有ROPC流程）
├── xbox/
│   ├── stream_controller.py            # ✅ Xbox SmartGlass串流控制
│   └── xbox_discovery.py                # ✅ Xbox主机发现
├── vision/
│   ├── template_matcher.py             # ✅ 模板匹配（OpenCV）
│   └── frame_capture.py                 # ✅ 窗口截图捕获
├── input/
│   ├── input_controller.py             # ✅ 鼠标键盘控制
│   └── input_controller.py             # ⚠️ 游戏手柄控制（需增加虚拟手柄）
└── windows/
    └── stream_window.py                 # ✅ 窗口管理
```

### 3.2 新增自动化模块目录结构

```
bend-agent/src/agent/
├── automation/                          # 新增：自动化模块
│   ├── __init__.py
│   ├── agent_automation_task.py         # 主自动化任务类（拆分为四个独立步骤）
│   ├── step1_stream_account_login.py    # 步骤一：串流账号登录
│   ├── step2_xbox_streaming.py         # 步骤二：Xbox串流连接
│   ├── step3_gpu_decode.py             # 步骤三：显卡解码流转
│   ├── step4_game_automation.py        # 步骤四：游戏比赛自动化
│   ├── task_context.py                 # 任务上下文管理
│   ├── task_window_manager.py          # 窗口管理器（一个任务一个窗口）
│   ├── xbox_matcher.py                 # Xbox主机匹配器
│   ├── template_manager.py             # 模板管理器（游戏界面模板）
│   ├── ocr_recognizer.py               # OCR文字识别
│   └── virtual_gamepad.py              # 虚拟手柄（无实体手柄时使用）
```

**窗口管理器职责**：
- 为每个串流账号任务创建独立窗口
- 维护窗口与任务的映射关系
- 管理窗口的生命周期（创建、执行、关闭）
- 支持暂停/恢复操作（暂停窗口画面输入）

### 3.2 核心类实现

#### 3.2.1 Step1: 串流账号登录 (step1_stream_account_login.py)

```python
"""
第一步骤：串流账号自动登录
==========================

功能说明：
- 使用账号密码直接获取Microsoft OAuth Token
- 绕过微软登录窗口（Device Code Flow）
- 获取Xbox Live Token用于后续串流

方法拆分：
- step1_execute_login(): 执行登录主流程
- _validate_account_info(): 验证账号信息
- _get_microsoft_token(): 获取微软访问令牌
- _get_xbox_live_token(): 获取Xbox Live令牌
- _report_progress(): 上报进度到平台
"""

async def step1_execute_login(context: AgentTaskContext, check_cancel: Callable) -> Step1Result:
    """
    第一步骤执行：串流账号自动登录

    流程：
    1. 验证账号信息完整性
    2. 使用ROPC流程获取Microsoft Token（绕过设备代码授权）
    3. 使用Microsoft Token获取Xbox Live Token
    4. 上报进度到平台

    参数：
    - context: 任务上下文
    - check_cancel: 取消检查函数

    返回：
    - Step1Result: 包含认证结果的Step1Result
    """
    # ========== 步骤1.1: 验证账号信息 ==========
    if check_cancel():
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    validation = await _validate_account_info(context)
    if not validation.is_valid:
        return Step1Result(success=False, error_code="INVALID_ACCOUNT", message=validation.error_msg)

    # ========== 步骤1.2: 获取Microsoft访问令牌 ==========
    if check_cancel():
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP1_LOGGING", "正在登录微软账号...")
    microsoft_tokens = await _get_microsoft_token(context)

    if not microsoft_tokens:
        return Step1Result(success=False, error_code="MICROSOFT_TOKEN_FAILED",
                          message="获取Microsoft Token失败")

    # ========== 步骤1.3: 获取Xbox Live令牌 ==========
    if check_cancel():
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP1_LOGGING", "正在获取Xbox Live令牌...")
    xbox_tokens = await _get_xbox_live_token(microsoft_tokens.access_token)

    if not xbox_tokens:
        return Step1Result(success=False, error_code="XBOX_TOKEN_FAILED",
                          message="获取Xbox Live Token失败")

    # 保存认证结果到上下文
    context.microsoft_auth = AuthenticationResult(
        success=True,
        microsoft_tokens=microsoft_tokens,
        xbox_tokens=xbox_tokens
    )

    # ========== 步骤1.4: 上报进度到平台 ==========
    await _report_progress(context, "STEP1_COMPLETED", "微软账号登录完成")

    return Step1Result(success=True, message="串流账号登录成功", xbox_tokens=xbox_tokens)
```

#### 3.2.2 Step2: Xbox串流连接 (step2_xbox_streaming.py)

```python
"""
第二步骤：Xbox串流连接
=====================

功能说明：
- 根据条件匹配Xbox主机
- 建立与Xbox的串流连接
- 回传主机信息到平台并标记防止抢夺

方法拆分：
- step2_execute_streaming(): 执行串流主流程
- _match_xbox_host(): 匹配Xbox主机
- _connect_to_xbox(): 连接到Xbox主机
- _bind_xbox_to_platform(): 绑定Xbox到平台（防止抢夺）
- _report_progress(): 上报进度到平台
"""

async def step2_execute_streaming(context: AgentTaskContext, check_cancel: Callable) -> Step2Result:
    """
    第二步骤执行：Xbox串流连接

    流程：
    1. 检查是否指定了Xbox主机
       - 已指定：直接使用指定主机
       - 未指定：解析串流账号已登录的Xbox信息，匹配局域网在线Xbox
    2. 如果多个Xbox匹配，随机选择一个
    3. 建立与Xbox的串流连接
    4. 回传主机信息到平台并标记

    参数：
    - context: 任务上下文（包含第一步的认证结果）
    - check_cancel: 取消检查函数

    返回：
    - Step2Result: 包含Xbox连接结果的Step2Result
    """
    # ========== 步骤2.1: 匹配Xbox主机 ==========
    if check_cancel():
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP2_STREAM", "正在匹配Xbox主机...")
    match_result = await _match_xbox_host(context)

    if not match_result.success:
        return Step2Result(success=False, error_code="XBOX_MATCH_FAILED",
                          message=match_result.message)

    context.current_xbox = match_result.xbox_info
    logger.info(f"Xbox匹配成功: {match_result.xbox_info.name} ({match_result.xbox_info.ip_address}), "
               f"匹配方式: {match_result.match_type}")

    # ========== 步骤2.2: 绑定Xbox到平台（防止抢夺） ==========
    if check_cancel():
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    bind_success = await _bind_xbox_to_platform(context)
    if not bind_success:
        logger.warning(f"Xbox绑定平台失败，但继续执行: {context.current_xbox.ip_address}")

    # ========== 步骤2.3: 连接到Xbox主机 ==========
    if check_cancel():
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP2_STREAM", f"正在连接{context.current_xbox.name}...")
    connect_success = await _connect_to_xbox(context)

    if not connect_success:
        return Step2Result(success=False, error_code="XBOX_CONNECT_FAILED",
                          message=f"连接Xbox失败: {context.current_xbox.ip_address}")

    # ========== 步骤2.4: 上报进度到平台 ==========
    await _report_progress(context, "STEP2_COMPLETED",
                          f"Xbox串流连接完成: {context.current_xbox.name}")

    return Step2Result(success=True, message="Xbox串流连接成功", xbox_info=context.current_xbox)
```

#### 3.2.3 Step3: 显卡解码流转 (step3_gpu_decode.py)

```python
"""
步骤三：显卡解码流转
=====================

功能说明：
- 接收显卡解码后的视频流
- 通过Moonlight/Xbox App窗口显示
- 持续捕获画面供后续模板匹配使用

技术实现：
- 复用现有 VideoFrameCapture 模块进行窗口截图
- GPU解码后的画面通过窗口展示
- 截图用于后续的模板匹配和OCR识别

方法拆分：
- step3_execute_decode(): 执行显卡解码流转主流程
- _start_stream_display(): 启动串流显示
- _capture_loop(): 持续捕获画面
- _detect_game_scene(): 检测游戏场景
- _report_progress(): 上报进度到平台
"""

async def step3_execute_decode(context: AgentTaskContext, check_cancel: Callable) -> Step3Result:
    """
    步骤三执行：显卡解码流转

    流程：
    1. 启动Moonlight/Xbox App窗口显示串流
    2. 建立持续的画面捕获循环
    3. 捕获首帧确认串流正常
    4. 检测游戏主界面
    5. 上报进度到平台

    参数：
    - context: 任务上下文
    - check_cancel: 取消检查函数

    返回：
    - Step3Result: 包含解码流转结果的Step3Result
    """
    from ..vision.frame_capture import VideoFrameCapture
    from ..windows.stream_window import StreamWindow

    # ========== 步骤3.1: 创建窗口和捕获器 ==========
    if check_cancel():
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP3_DECODE", "正在启动串流显示...")
    window = StreamWindow(window_title="Xbox")
    await window.find_window()
    await window.activate()

    capture = VideoFrameCapture(window)
    context.frame_capture = capture  # 保存到上下文供后续使用

    # ========== 步骤3.2: 捕获首帧确认串流 ==========
    if check_cancel():
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP3_DECODE", "正在验证串流...")
    frame = await capture.capture_frame()

    if frame is None or frame.data is None:
        return Step3Result(success=False, error_code="DECODE_FAILED",
                          message="无法捕获串流画面")

    # ========== 步骤3.3: 检测游戏主界面 ==========
    if check_cancel():
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP3_DECODE", "正在检测游戏界面...")
    game_detected = await _detect_game_scene(capture, check_cancel)

    if not game_detected:
        return Step3Result(success=False, error_code="SCENE_NOT_FOUND",
                          message="未检测到游戏主界面")

    # ========== 步骤3.4: 上报进度到平台 ==========
    await _report_progress(context, "STEP3_COMPLETED", "显卡解码流转正常，已进入游戏")

    return Step3Result(success=True, message="串流显示正常", frame=frame)
```

#### 3.2.4 Step4: 游戏比赛自动化 (step4_game_automation.py)

```python
"""
步骤四：自动游戏比赛动作
=========================

功能说明：
- 根据游戏账号列表依次执行比赛
- 每个游戏账号每天完成3场比赛
- 记录每个游戏账号当天比赛次数
- 完成当天最大次数后切换到下一个账号
- 如果游戏账号未在Xbox登录，先自动化登录再进行比赛

技术实现：
- 复用现有 TemplateMatcher 进行模板匹配
- 复用现有 InputController/GamepadController 进行手柄操作
- OCR识别游戏账号名称进行定位

方法拆分：
- step4_execute_gaming(): 执行游戏自动化主流程
- _check_and_login_game_account(): 检查账号是否已登录，未登录则自动化登录
- _execute_match_for_account(): 为指定账号执行一场比赛
- _check_match_completion(): 检查比赛是否完成
- _should_continue_gaming(): 判断是否继续执行
- _report_progress(): 上报进度到平台
"""

async def step4_execute_gaming(context: AgentTaskContext, check_cancel: Callable) -> Step4Result:
    """
    步骤四执行：自动游戏比赛动作

    实时同步机制：
    1. 初始化时：从平台获取所有游戏账号当天已完成场次
    2. 比赛完成后：实时推送完成场次到平台
    3. 切换账号前：从平台获取最新状态，判断是否需要继续
    4. 任务结束前：从平台确认所有账号是否都完成

    流程：
    1. 从平台获取串流账号下所有游戏账号的当天完成情况
    2. 循环处理每个游戏账号：
       a. 检查该账号当天是否已达最大次数(3场)
          - 已达最大次数：跳过该账号，切换下一个
          - 未达最大次数：继续执行
       b. 检查账号是否已在Xbox登录
          - 未登录：执行自动化登录游戏账号
       c. 执行一场比赛
       d. 比赛完成后立即推送完成场次到平台
       e. 从平台获取所有账号最新状态，判断是否全部完成
       f. 如全部完成则结束任务；否则切换下一个账号继续
    3. 所有账号完成后，任务结束

    参数：
    - context: 任务上下文（包含frame_capture捕获器）
    - check_cancel: 取消检查函数

    返回：
    - Step4Result: 包含游戏自动化结果的Step4Result
    """
    from ..platform_api import PlatformApiClient

    platform_client = PlatformApiClient()

    # ========== 步骤4.1: 从平台获取所有游戏账号当天完成情况 ==========
    if check_cancel():
        return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

    context.update_status("STEP4_GAME", "从平台获取游戏账号状态...")

    # 调用平台API获取所有游戏账号状态
    all_accounts_status = await platform_client.get_game_accounts_status(
        context.task_id
    )

    if not all_accounts_status:
        logger.warning("无法获取游戏账号状态，使用本地初始化")
        context.matches_completed_today = {ga.id: 0 for ga in context.game_accounts}
    else:
        context.matches_completed_today = {
            acc["id"]: acc["completedCount"] for acc in all_accounts_status
        }

    # 计算总任务量
    total_remaining = sum(
        max(0, ga.target_matches - context.matches_completed_today.get(ga.id, 0))
        for ga in context.game_accounts
    )

    logger.info(f"从平台获取游戏账号状态: {context.matches_completed_today}, 今日剩余任务: {total_remaining}场")

    # ========== 步骤4.2: 检查是否所有账号都已完成 ==========
    if total_remaining == 0:
        logger.info("所有游戏账号今日已完成目标场次，任务结束")
        await _report_progress(context, "STEP4_COMPLETED", "所有游戏账号今日已完成目标场次")
        return Step4Result(success=True, message="所有游戏账号今日已完成目标场次", total_matches=0)

    # ========== 步骤4.3: 循环处理每个游戏账号 ==========
    for account_index, game_account in enumerate(context.game_accounts):
        if check_cancel():
            return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

        # ========== 步骤4.3.1: 每次开始前从平台获取最新状态 ==========
        latest_status = await platform_client.get_game_accounts_status(context.task_id)
        current_completed = latest_status.get(game_account.id, {}).get("completedCount", 0)

        # 检查该账号当天是否已达最大次数
        if current_completed >= game_account.target_matches:
            logger.info(f"账号 {game_account.gamertag} 今日已完成 {game_account.target_matches} 场（平台数据），跳过")
            continue

        context.matches_completed_today[game_account.id] = current_completed

        # 检查是否暂停
        if context.pause_event and context.pause_event.is_set():
            context.update_status("STEP4_GAME", f"任务已暂停，账号 {game_account.gamertag}")
            await _wait_for_resume(context)

        context.current_game_account_index = account_index
        remaining = game_account.target_matches - current_completed
        logger.info(f"开始处理游戏账号: {game_account.gamertag}, "
                   f"今日剩余: {remaining}场 ({account_index+1}/{len(context.game_accounts)})")

        # ========== 步骤4.3.2: 检查并登录游戏账号 ==========
        context.update_status("STEP4_GAME", f"检查账号 {game_account.gamertag} 登录状态...")
        login_success = await _check_and_login_game_account(context, game_account)

        if not login_success:
            logger.warning(f"账号 {game_account.gamertag} 登录失败，跳过")
            await _report_progress(context, "LOGIN_FAILED",
                f"账号 {game_account.gamertag} 登录失败，跳过该账号")
            continue

        # ========== 步骤4.3.3: 执行比赛直到完成当天最大次数 ==========
        while context.matches_completed_today[game_account.id] < game_account.target_matches:
            if check_cancel():
                return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

            # 检查暂停
            if context.pause_event and context.pause_event.is_set():
                context.update_status("STEP4_GAME", "任务已暂停...")
                await _wait_for_resume(context)

            current_count = context.matches_completed_today[game_account.id] + 1
            context.update_status("STEP4_GAME",
                f"账号 {game_account.gamertag} 进行第{current_count}场比赛 "
                f"(今日已完成: {context.matches_completed_today[game_account.id]}/{game_account.target_matches})")

            # 执行一场比赛
            match_success = await _execute_match_for_account(context, game_account)

            if match_success:
                # ========== 实时同步：比赛完成后立即推送完成场次到平台 ==========
                context.matches_completed_today[game_account.id] += 1
                new_completed = context.matches_completed_today[game_account.id]

                await platform_client.report_match_complete(
                    task_id=context.task_id,
                    game_account_id=game_account.id,
                    completed_count=new_completed
                )

                await _report_progress(context, "MATCH_COMPLETED",
                    f"账号 {game_account.gamertag} 完成第{new_completed}场比赛 "
                    f"(今日: {new_completed}/{game_account.target_matches})")

                logger.info(f"已推送比赛完成到平台: {game_account.gamertag} - {new_completed}场")

            else:
                logger.warning(f"比赛执行异常，重试...")
                await asyncio.sleep(5)

        # ========== 步骤4.3.4: 该账号完成，检查是否所有账号都完成 ==========
        logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 {game_account.target_matches} 场")

        # 从平台获取所有账号最新状态，判断是否结束任务
        all_status = await platform_client.get_game_accounts_status(context.task_id)
        all_done = all(acc.get("completedCount", 0) >= acc.get("targetMatches", 3)
                      for acc in all_status)

        if all_done:
            logger.info("所有游戏账号今日已完成目标场次，任务结束")
            await _report_progress(context, "STEP4_COMPLETED", "所有游戏账号今日已完成目标场次")
            return Step4Result(success=True, message="所有游戏账号今日已完成目标场次",
                             total_matches=total_remaining)

    # ========== 步骤4.4: 所有账号处理完毕 ==========
    await _report_progress(context, "STEP4_COMPLETED", f"任务完成，共完成 {total_remaining} 场比赛")
    return Step4Result(success=True, message="游戏比赛自动化完成", total_matches=total_remaining)
                            f"所有游戏账号今日比赛完成")

    return Step4Result(success=True, message="游戏比赛自动化完成",
                      total_matches=total_matches)


async def _check_and_login_game_account(context: AgentTaskContext, game_account: GameAccountInfo) -> bool:
    """
    检查游戏账号是否已在Xbox登录，未登录则执行自动化登录

    流程：
    1. 截图当前Xbox主界面
    2. 查找当前登录的账号信息
    3. 如果不是目标账号，执行自动化切换

    参数：
    - context: 任务上下文
    - game_account: 目标游戏账号

    返回：
    - True: 账号已登录或登录成功
    - False: 登录失败
    """
    from ..vision.template_matcher import TemplateMatcher
    from ..input.input_controller import InputController

    matcher = TemplateMatcher()
    input_ctrl = InputController()

    # 获取当前界面截图
    frame = await context.frame_capture.capture_frame()
    if not frame:
        logger.error("无法获取当前界面截图")
        return False

    # 查找当前登录账号的gamertag位置（使用OCR或模板匹配）
    current_gamertag = await _detect_current_gamertag(matcher, frame.data)

    if current_gamertag == game_account.gamertag:
        logger.info(f"账号 {game_account.gamertag} 已登录")
        return True

    # 当前账号不是目标账号，需要切换
    logger.info(f"当前登录账号: {current_gamertag}, 目标账号: {game_account.gamertag}，执行切换...")

    # 执行自动化账号切换流程
    # 1. 打开Xbox主界面菜单
    await input_ctrl.press_key('xbox')  # 按Xbox按钮
    await asyncio.sleep(1)

    # 2. 导航到账号切换选项
    # TODO: 根据实际UI模板定位
    await input_ctrl.press_key('down')
    await asyncio.sleep(0.3)
    await input_ctrl.press_key('down')
    await asyncio.sleep(0.3)
    await input_ctrl.press_key('a')
    await asyncio.sleep(1)

    # 3. 查找并选择目标账号
    # 使用模板匹配或OCR定位账号
    target_found = await _find_and_select_account(matcher, input_ctrl, game_account.gamertag)

    if not target_found:
        logger.error(f"无法找到目标账号: {game_account.gamertag}")
        return False

    # 4. 确认切换
    await input_ctrl.press_key('a')
    await asyncio.sleep(3)  # 等待账号切换完成

    # 5. 验证切换是否成功
    frame = await context.frame_capture.capture_frame()
    if frame:
        verified_gamertag = await _detect_current_gamertag(matcher, frame.data)
        if verified_gamertag == game_account.gamertag:
            logger.info(f"账号切换成功: {game_account.gamertag}")
            return True

    return False
```

### 3.3 主自动化任务类 (agent_automation_task.py)

```python
"""
Agent 自动化主任务类
====================

功能说明：
- 整合四个步骤的执行
- 管理任务上下文和状态流转
- 处理暂停、恢复、停止等控制命令

使用方法：
    task = AgentAutomationTask(context, window_manager)
    result = await task.execute()
"""

class AgentAutomationTask:
    """
    Agent自动化任务执行器

    整合Step1、Step2、Step3、Step4的执行，管理任务生命周期

    重要原则：
    - 一个AgentAutomationTask对象对应一个串流账号、一个任务、一个窗口
    - 任务与窗口一一对应，不可复用
    - 任务完成后窗口自动关闭
    """

    def __init__(self, context: AgentTaskContext, window_manager: 'TaskWindowManager'):
        """
        初始化自动化任务

        参数：
        - context: 任务上下文（一个串流账号对应一个context）
        - window_manager: 窗口管理器（用于管理窗口生命周期）
        """
        self.context = context
        self.window_manager = window_manager
        self.window_info = None  # 该任务关联的窗口信息
        self.context.pause_event = asyncio.Event()
        self.context.pause_event.set()  # 初始为非暂停状态
        self.logger = get_logger(f'automation_task_{context.task_id}')

    async def execute(self, check_cancel: Callable) -> AutomationResult:
        """
        执行自动化任务（四个步骤）

        流程：
        1. 步骤一：串流账号登录
        2. 步骤二：Xbox串流连接
        3. 步骤三：显卡解码流转
        4. 步骤四：游戏比赛自动化

        参数：
        - check_cancel: 取消检查函数

        返回：
        - AutomationResult: 最终执行结果
        """
        try:
            # ========== 步骤一：串流账号登录 ==========
            self.logger.info("=== 开始执行步骤一：串流账号登录 ===")
            step1_result = await step1_execute_login(self.context, check_cancel)

            if not step1_result.success:
                return AutomationResult(success=False, failed_step="STEP1",
                                       message=step1_result.message)

            # ========== 步骤二：Xbox串流连接 ==========
            self.logger.info("=== 开始执行步骤二：Xbox串流连接 ===")
            step2_result = await step2_execute_streaming(self.context, check_cancel)

            if not step2_result.success:
                return AutomationResult(success=False, failed_step="STEP2",
                                       message=step2_result.message)

            # ========== 步骤三：显卡解码流转 ==========
            self.logger.info("=== 开始执行步骤三：显卡解码流转 ===")
            step3_result = await step3_execute_decode(self.context, check_cancel)

            if not step3_result.success:
                return AutomationResult(success=False, failed_step="STEP3",
                                       message=step3_result.message)

            # ========== 步骤四：游戏比赛自动化 ==========
            self.logger.info("=== 开始执行步骤四：游戏比赛自动化 ===")
            step4_result = await step4_execute_gaming(self.context, check_cancel)

            if not step4_result.success:
                return AutomationResult(success=False, failed_step="STEP4",
                                       message=step4_result.message)

            # ========== 任务完成 ==========
            self.logger.info("=== 自动化任务全部完成 ===")
            return AutomationResult(success=True, message="自动化任务完成",
                                   total_matches=step3_result.total_matches)

        except asyncio.CancelledError:
            self.logger.info("任务被取消")
            return AutomationResult(success=False, error_code="CANCELLED",
                                   message="任务被取消")

        except Exception as e:
            self.logger.error(f"任务执行异常: {e}", exc_info=True)
            return AutomationResult(success=False, error_code="EXCEPTION",
                                   message=f"任务执行异常: {str(e)}")

        finally:
            # 清理资源
            await self._cleanup()

    async def pause(self):
        """暂停任务"""
        self.context.pause_event.clear()
        self.context.update_status("PAUSED", "任务已暂停")
        self.logger.info("任务已暂停")

    async def resume(self):
        """恢复任务"""
        self.context.pause_event.set()
        self.context.update_status("RUNNING", "任务已恢复")
        self.logger.info("任务已恢复")

    async def stop(self):
        """停止任务"""
        self.context.pause_event.set()  # 确保不是暂停状态，以便取消
        # 取消检查会被触发
        self.logger.info("任务已请求停止")

    async def _cleanup(self):
        """清理任务资源并关闭窗口"""
        try:
            # 1. 断开Xbox会话
            if self.context.xbox_session:
                await self.context.xbox_session.disconnect()

            # 2. 关闭窗口（重要：一个任务一个窗口，任务结束窗口关闭）
            if self.window_info and self.window_manager:
                await self.window_manager.close_window(self.window_info.window_id)

            self.logger.info(f"任务 {self.context.task_id} 资源已清理，窗口已关闭")
        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")


class PlatformApiClient:
    """
    Platform API客户端

    负责Agent与Platform之间的实时数据同步

    功能：
    - 获取游戏账号当天完成情况
    - 上报比赛完成信息
    - 上报任务进度
    """

    def __init__(self):
        self.logger = get_logger('platform_api_client')
        self.base_url = "http://platform:8080/api"

    async def get_game_accounts_status(self, task_id: str) -> Dict[str, dict]:
        """
        获取串流账号下所有游戏账号的当天完成情况

        参数：
        - task_id: 任务ID

        返回：
        - Dict: {gameAccountId: {id, gamertag, completedCount, targetMatches, completed}}
        """
        try:
            url = f"{self.base_url}/task/{task_id}/game-accounts/status"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("code") == 200:
                            data = result.get("data", [])
                            return {acc["id"]: acc for acc in data}
                    return {}
        except Exception as e:
            self.logger.error(f"获取游戏账号状态失败: {e}")
            return {}

    async def report_match_complete(self, task_id: str, game_account_id: str,
                                   completed_count: int) -> dict:
        """
        上报比赛完成信息到平台

        参数：
        - task_id: 任务ID
        - game_account_id: 游戏账号ID
        - completed_count: 完成后当天总场次

        返回：
        - dict: 包含allAccounts和allCompleted
        """
        try:
            url = f"{self.base_url}/task/{task_id}/match/complete"
            payload = {
                "gameAccountId": game_account_id,
                "completedCount": completed_count
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("code") == 200:
                            return result.get("data", {})
                    return {}
        except Exception as e:
            self.logger.error(f"上报比赛完成失败: {e}")
            return {}

    async def report_task_progress(self, task_id: str, step: str, status: str,
                                  message: str, **kwargs):
        """
        上报任务进度到平台（通过WebSocket）

        参数：
        - task_id: 任务ID
        - step: 当前步骤
        - status: 状态
        - message: 消息
        - **kwargs: 其他字段
        """
        try:
            payload = {
                "type": "TASK_PROGRESS",
                "taskId": task_id,
                "step": step,
                "status": status,
                "message": message,
                "timestamp": time.time(),
                **kwargs
            }
            await websocket.send(payload)
        except Exception as e:
            self.logger.error(f"上报任务进度失败: {e}")


class TaskWindowManager:
    """
    任务窗口管理器

    职责：
    - 为每个串流账号任务创建独立窗口
    - 维护 task_id -> window_id -> window_info 的映射
    - 管理窗口生命周期

    重要原则：
    - 一个任务对应一个窗口
    - 任务完成或失败时，窗口必须关闭
    - 窗口之间相互隔离，独立执行
    """

    def __init__(self, max_concurrent_windows: int = 10):
        self.logger = get_logger('task_window_manager')
        self._windows: Dict[str, WindowInfo] = {}  # window_id -> WindowInfo
        self._task_to_window: Dict[str, str] = {}  # task_id -> window_id
        self._max_concurrent = max_concurrent_windows
        self._semaphore = asyncio.Semaphore(max_concurrent_windows)

    async def create_window_for_task(self, context: AgentTaskContext) -> WindowInfo:
        """
        为任务创建独立窗口

        一个串流账号 = 一个任务 = 一个窗口

        参数：
        - context: 任务上下文

        返回：
        - WindowInfo: 创建的窗口信息
        """
        await self._semaphore.acquire()

        window_id = f"window_{context.task_id}"
        window_info = WindowInfo(
            window_id=window_id,
            streaming_account_id=context.streaming_account_id,
            task_id=context.task_id,
            state="created",
            created_time=time.time()
        )

        # 创建物理窗口（Moonlight/Xbox App窗口）
        # TODO: 调用底层窗口创建接口
        window_info.window_handle = await self._create_physical_window(window_info)

        self._windows[window_id] = window_info
        self._task_to_window[context.task_id] = window_id

        self.logger.info(f"为任务 {context.task_id} 创建窗口 {window_id}")
        return window_info

    async def close_window(self, window_id: str):
        """关闭指定窗口"""
        if window_id in self._windows:
            window = self._windows[window_id]
            window.state = "closing"

            # TODO: 关闭物理窗口

            window.state = "closed"
            task_id = window.task_id
            self._task_to_window.pop(task_id, None)
            self._windows.pop(window_id)

            self._semaphore.release()
            self.logger.info(f"窗口 {window_id} 已关闭")

    def get_window_by_task(self, task_id: str) -> Optional[WindowInfo]:
        """根据任务ID获取窗口信息"""
        window_id = self._task_to_window.get(task_id)
        return self._windows.get(window_id) if window_id else None

    async def _create_physical_window(self, window_info: WindowInfo) -> int:
        """创建物理窗口（子类实现）"""
        # TODO: 实现创建Moonlight/Xbox App窗口的逻辑
        pass
```

---

## 四、平台端代码实现

### 4.1 新增API端点

#### 4.1.1 任务控制API (TaskController.java)

```java
@PostMapping("/control/{taskId}")
public ApiResponse<Void> controlTask(
        @PathVariable String taskId,
        @RequestParam String action) {  // pause, resume, stop

    // 转发控制命令到Agent
    AgentWebSocketEndpoint.sendControlToAgent(taskId, action);
    return ApiResponse.success("任务控制命令已发送", null);
}
```

#### 4.1.2 任务进度查询API

```java
@GetMapping("/progress/{taskId}")
public ApiResponse<TaskProgressVO> getTaskProgress(@PathVariable String taskId) {
    // 从缓存或数据库获取任务进度
    TaskProgressVO progress = taskService.getTaskProgress(taskId);
    return ApiResponse.success(progress);
}
```

#### 4.1.3 获取游戏账号状态API

```java
/**
 * 获取串流账号下所有游戏账号的当天完成情况
 * Agent在比赛开始前调用此API获取最新状态
 */
@GetMapping("/task/{taskId}/game-accounts/status")
public ApiResponse<List<GameAccountStatusVO>> getGameAccountsStatus(
        @PathVariable String taskId) {

    Task task = taskService.getTask(taskId);
    List<GameAccountStatusVO> statusList = new ArrayList<>();

    for (GameAccount ga : task.getGameAccounts()) {
        GameAccountStatusVO vo = new GameAccountStatusVO();
        vo.setId(ga.getId());
        vo.setGamertag(ga.getGamertag());
        vo.setCompletedCount(ga.getDailyMatchCount());  // 当天已完成比赛数
        vo.setTargetMatches(ga.getTargetMatches());      // 目标比赛数（默认3）
        vo.setCompleted(ga.getDailyMatchCount() >= ga.getTargetMatches());
        statusList.add(vo);
    }

    return ApiResponse.success(statusList);
}
```

#### 4.1.4 比赛完成上报API

```java
/**
 * Agent比赛完成后调用此API更新平台数据
 * 实时同步游戏账号当天完成比赛次数
 */
@PostMapping("/task/{taskId}/match/complete")
public ApiResponse<MatchCompleteVO> reportMatchComplete(
        @PathVariable String taskId,
        @RequestParam String gameAccountId,
        @RequestParam Integer completedCount) {

    // 1. 更新游戏账号当天完成次数
    GameAccount ga = gameAccountService.getGameAccount(gameAccountId);
    ga.setDailyMatchCount(completedCount);
    ga.setLastMatchTime(LocalDateTime.now());
    gameAccountService.update(ga);

    // 2. 查询该串流账号下所有游戏账号状态（用于返回给Agent）
    Task task = taskService.getTask(taskId);
    List<GameAccountStatusVO> allAccountsStatus = new ArrayList<>();
    boolean allCompleted = true;

    for (GameAccount account : task.getGameAccounts()) {
        GameAccountStatusVO vo = new GameAccountStatusVO();
        vo.setId(account.getId());
        vo.setGamertag(account.getGamertag());
        vo.setCompletedCount(account.getDailyMatchCount());
        vo.setTargetMatches(account.getTargetMatches());
        vo.setCompleted(account.getDailyMatchCount() >= account.getTargetMatches());
        allAccountsStatus.add(vo);

        if (!vo.isCompleted()) {
            allCompleted = false;
        }
    }

    // 3. 返回所有账号状态
    MatchCompleteVO result = new MatchCompleteVO();
    result.setAllAccounts(allAccountsStatus);
    result.setAllCompleted(allCompleted);

    // 4. 如果全部完成，更新任务状态
    if (allCompleted) {
        taskService.updateTaskStatus(taskId, "COMPLETED");
    }

    return ApiResponse.success(result);
}
```

### 4.2 WebSocket消息扩展

#### 4.2.1 Agent上报任务进度

```java
// 消息类型: TASK_PROGRESS
{
    "type": "TASK_PROGRESS",
    "taskId": "xxx",
    "step": "STEP4",
    "status": "RUNNING",
    "currentGameAccountId": "ga_123",
    "currentGameAccountName": "Player123",
    "matchesCompleted": 2,
    "message": "账号 Player123 进行第3场比赛"
}
```

#### 4.2.2 平台下发控制命令

```java
// 消息类型: TASK_CONTROL
{
    "type": "TASK_CONTROL",
    "taskId": "xxx",
    "action": "pause"  // pause, resume, stop
}
```

### 4.3 前端Agent管理页面增强

#### 4.3.1 任务监控对话框 (AgentTaskDialog.vue)

```vue
<template>
  <!-- 在现有表格中增加操作列 -->
  <el-table-column label="操作" width="180">
    <template #default="{ row }">
      <el-button
        v-if="row.status === 'RUNNING'"
        size="small"
        @click="handlePause(row)"
      >暂停</el-button>

      <el-button
        v-if="row.status === 'PAUSED'"
        size="small"
        type="success"
        @click="handleResume(row)"
      >恢复</el-button>

      <el-button
        v-if="row.status !== 'COMPLETED' && row.status !== 'FAILED'"
        size="small"
        type="danger"
        @click="handleStop(row)"
      >停止</el-button>
    </template>
  </el-table-column>
</template>
```

---

## 五、任务拆分清单

| 任务ID | 任务描述 | 优先级 | 工作量 | 备注 |
|--------|---------|--------|--------|------|
| T1.1 | Agent: 创建automation模块目录结构 | P0 | 0.5天 | |
| T1.2 | Agent: 实现任务上下文管理 (task_context.py) | P0 | 1天 | |
| T1.3 | Agent: 实现窗口管理器 (task_window_manager.py) | P0 | 1.5天 | 核心：一个任务一个窗口 |
| T1.4 | Agent: 实现步骤一-串流账号登录 | P0 | 2天 | 复用MicrosoftAuthenticator |
| T1.5 | Agent: 实现Xbox主机匹配器 (xbox_matcher.py) | P0 | 1.5天 | |
| T1.6 | Agent: 实现步骤二-Xbox串流连接 | P0 | 2天 | 复用XboxStreamController |
| T1.7 | Agent: 实现步骤三-显卡解码流转 | P0 | 1.5天 | 复用VideoFrameCapture |
| T1.8 | Agent: 实现模板管理器 (template_manager.py) | P0 | 1天 | 游戏界面模板管理 |
| T1.9 | Agent: 实现OCR文字识别 (ocr_recognizer.py) | P0 | 1.5天 | 识别游戏账号名称 |
| T1.10 | Agent: 实现虚拟手柄 (virtual_gamepad.py) | P0 | 1天 | 无实体手柄时使用 |
| T1.11 | Agent: 实现步骤四-游戏比赛自动化 | P0 | 3天 | 复用TemplateMatcher+GamepadController |
| T1.12 | Agent: 实现主自动化任务类 | P0 | 1天 | 集成四步骤执行 |
| T1.13 | Agent: 实现PlatformApiClient | P0 | 1.5天 | 实时同步平台数据 |
| T1.14 | Agent: 实现主动上报机制 | P0 | 1天 | Agent→Platform实时上报 |
| T1.15 | Agent: 集成暂停/恢复/停止控制 | P0 | 1.5天 | |
| T2.1 | Platform: 扩展Task实体字段 | P0 | 0.5天 | |
| T2.2 | Platform: 新增任务控制API | P0 | 1天 | |
| T2.3 | Platform: 扩展WebSocket消息类型 | P0 | 1天 | |
| T2.4 | Platform: 任务进度查询API | P0 | 1天 | |
| T2.5 | Platform: 游戏账号状态API | P0 | 1天 | 实时同步比赛次数 |
| T2.6 | Platform: 比赛完成上报API | P0 | 1天 | 更新游戏账号完成数 |
| T3.1 | Frontend: Agent任务监控对话框增强 | P1 | 1天 | 增加暂停/恢复/停止按钮 |
| T3.2 | Frontend: 任务进度实时显示 | P1 | 1天 | |
| T4.1 | 集成测试 | P0 | 2天 | |
| T4.2 | 联调测试 | P0 | 2天 | |

**总计：约30天**

---

## 六、现有模块复用说明

### 6.1 复用现有模块

| 现有模块 | 用途 | 复用方式 |
|---------|------|---------|
| MicrosoftAuthenticator | 串流账号登录 | ROPC流程获取Token |
| XboxStreamController | Xbox串流连接 | SmartGlass协议 |
| XboxDiscovery | Xbox主机发现 | 局域网发现 |
| VideoFrameCapture | 窗口截图 | GPU解码后画面捕获 |
| TemplateMatcher | 模板匹配 | 游戏界面元素定位 |
| InputController | 鼠标键盘控制 | 辅助手柄操作 |
| GamepadController | 手柄控制 | 已有，需增加虚拟手柄 |
| StreamWindow | 窗口管理 | 串流窗口控制 |

### 6.2 待新增模块

| 新模块 | 用途 | 说明 |
|-------|------|------|
| template_manager | 模板管理器 | 管理游戏界面模板 |
| ocr_recognizer | OCR识别 | 识别游戏账号名称 |
| virtual_gamepad | 虚拟手柄 | 无实体手柄时使用 |

---

## 七、任务隔离与异常处理

### 7.1 任务隔离机制

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          任务隔离架构                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Agent进程                                                                    │
│     │                                                                         │
│     ├─── TaskRunner#1 ──→ Window#1 ──→ 串流账号#1                            │
│     │      (独立协程)          (独立窗口)     任务状态: RUNNING              │
│     │                                                            │           │
│     │                                                   异常 → 上报平台      │
│     │                                                            │           │
│     │                                                            ▼           │
│     │                                                    平台可见异常状态     │
│     │                                                                     │
│     ├─── TaskRunner#2 ──→ Window#2 ──→ 串流账号#2                            │
│     │      (独立协程)          (独立窗口)     任务状态: COMPLETED           │
│     │                                                                     │
│     └─── TaskRunner#N ──→ Window#N ──→ 串流账号#N                            │
│            (独立协程)          (独立窗口)     任务状态: FAILED               │
│                                                               │             │
│                                                      异常 → 上报平台        │
│                                                               │             │
│                                                               ▼             │
│                                                        平台可见失败状态     │
│                                                                             │
│  【隔离保证】                                                                 │
│  • 每个任务运行在独立协程中                                                  │
│  • 每个任务拥有独立窗口                                                      │
│  • 一个任务的异常不会传播到其他任务                                          │
│  • 任务间资源完全隔离                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 异常处理机制

```python
async def run_automation_task(context: AgentTaskContext, window_manager: TaskWindowManager):
    """
    执行单个串流账号的自动化任务

    异常处理原则：
    - 每个任务的异常被捕获，不会影响其他任务
    - 异常状态和详细信息上报到平台
    - 资源清理（窗口关闭）在finally块中执行
    """
    task = AgentAutomationTask(context, window_manager)
    try:
        result = await task.execute(check_cancel)
        if result.success:
            await report_to_platform(context.task_id, "COMPLETED", result.message)
        else:
            await report_to_platform(context.task_id, "FAILED",
                f"步骤{result.failed_step}失败: {result.message}")
    except asyncio.CancelledError:
        # 任务被取消
        logger.info(f"任务 {context.task_id} 被取消")
        await report_to_platform(context.task_id, "CANCELLED", "任务被用户取消")
    except Exception as e:
        # 其他异常
        logger.error(f"任务 {context.task_id} 执行异常: {e}", exc_info=True)
        await report_to_platform(context.task_id, "FAILED",
            f"任务异常: {str(e)}", exception_details={
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            })
    finally:
        # 确保清理资源
        await cleanup_task(context)
```

### 7.3 主动上报异常信息

```python
async def report_to_platform(task_id: str, status: str, message: str,
                            exception_details: dict = None):
    """
    上报任务状态到平台

    参数：
    - task_id: 任务ID
    - status: 状态 (RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED)
    - message: 状态描述信息
    - exception_details: 异常详情（当status为FAILED时）
    """
    payload = {
        "type": "TASK_PROGRESS",
        "taskId": task_id,
        "status": status,
        "message": message,
        "timestamp": time.time()
    }

    if exception_details:
        payload["exceptionDetails"] = exception_details

    await websocket.send(payload)
```

### 7.4 平台端异常展示

平台需要展示每个任务的：
- 任务ID和关联的串流账号
- 当前状态（RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED）
- 当前步骤和进度
- 如果失败，显示失败原因和异常详情
- 失败时间

---

## 七、关键实现细节

### 7.1 Xbox主机匹配逻辑

```python
async def _match_xbox_host(context: AgentTaskContext) -> XboxMatchResult:
    """
    Xbox主机匹配逻辑

    优先级：
    1. 如果指定了Xbox主机，直接使用
    2. 如果未指定，解析串流账号已登录过的Xbox列表
    3. 在局域网中发现在线Xbox
    4. 匹配两者，随机选择冲突的主机
    5. 回传给平台标记
    """
    # 情况1：已指定Xbox主机
    if context.assigned_xbox:
        # 验证主机是否在线
        online = await xbox_discovery.test_connection(context.assigned_xbox.ip_address)
        if online:
            return XboxMatchResult(success=True, xbox_info=context.assigned_xbox,
                                  match_type="assigned", message="使用指定的Xbox主机")
        else:
            return XboxMatchResult(success=False, message="指定的Xbox主机不在线")

    # 情况2：未指定Xbox主机，需要自动匹配
    discovered_xboxes = await xbox_discovery.discover()

    if not discovered_xboxes:
        return XboxMatchResult(success=False, message="局域网未发现Xbox主机")

    # 从微软账号信息中获取已登录过的Xbox Live设备列表
    logged_in_xboxes = await _get_logged_in_xboxes_from_ms_account(context)

    # 匹配：在线的且已登录过的
    matched = []
    for discovered in discovered_xboxes:
        for logged in logged_in_xboxes:
            if discovered.live_id == logged.live_id or discovered.name == logged.name:
                matched.append(discovered)
                break

    if not matched:
        # 没有精确匹配，随机选择一个在线的
        import random
        selected = random.choice(discovered_xboxes)
        return XboxMatchResult(success=True, xbox_info=selected,
                              match_type="random_selected",
                              message=f"随机选择Xbox: {selected.name}")

    if len(matched) == 1:
        return XboxMatchResult(success=True, xbox_info=matched[0],
                              match_type="discovered",
                              message=f"发现匹配的Xbox: {matched[0].name}")

    # 多个匹配，随机选择
    import random
    selected = random.choice(matched)
    return XboxMatchResult(success=True, xbox_info=selected,
                          match_type="random_selected",
                          message=f"多个匹配，随机选择: {selected.name}")
```

### 6.2 暂停/恢复机制

```python
class AgentTaskContext:
    def __init__(self):
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # 初始为非暂停

    def is_paused(self) -> bool:
        return not self.pause_event.is_set()

async def _wait_for_resume(context: AgentTaskContext):
    """等待恢复信号"""
    await context.pause_event.wait()
    # 恢复后继续执行
```

### 6.3 取消检查点

在每个步骤的关键位置添加取消检查点：
- 每个大步骤开始时
- 每个小步骤之间
- 每次循环开始时
- 长时间等待操作前

```python
async def some_long_operation(context, check_cancel):
    # 操作前检查
    if check_cancel():
        raise asyncio.CancelledError()

    # 执行操作
    await do_something()

    # 操作后再次检查
    if check_cancel():
        raise asyncio.CancelledError()
```

---

## 七、错误处理与重试

### 7.1 错误分类

| 错误类型 | 处理策略 | 重试次数 |
|---------|---------|---------|
| 网络超时 | 等待后重试 | 3次 |
| Xbox不在线 | 等待后重试 | 5次 |
| 账号认证失败 | 不重试，直接失败 | 0次 |
| 游戏账号切换失败 | 等待后重试 | 3次 |
| 比赛异常 | 等待后重试 | 3次 |

### 7.2 降级策略

- 如果Xbox串流连接失败，尝试重新匹配其他Xbox
- 如果游戏账号切换失败，尝试重新切换
- 如果比赛执行失败，尝试重新开始比赛

---

## 八、安全考虑

1. **密码安全**：密码在传输和存储中使用AES加密
2. **Token安全**：Refresh Token安全存储，定期刷新
3. **Xbox抢夺防护**：通过平台标记防止多个账号抢夺同一Xbox
4. **任务隔离**：每个串流账号独立窗口，资源隔离

---

## 九、测试计划

### 9.1 单元测试

- TaskContext单元测试
- XboxMatcher单元测试
- 各步骤方法单元测试

### 9.2 集成测试

- 三步骤完整流程测试
- 暂停/恢复/停止测试
- Xbox抢夺防护测试
- 多账号并发测试

### 9.3 压力测试

- 10+并发串流账号测试
- 长时间运行稳定性测试
