# Agent窗口显示控制功能实现计划

## 需求分析

在平台的Agent任务中增加显示/隐藏窗口的开关功能：

* ✅ 默认打开显示窗口

* ✅ 可以在平台上隐藏窗口

* ✅ 隐藏对应任务打开的窗口

* ✅ Agent对应电脑上的窗口不能有最大化、最小化、关闭按钮

* ✅ 让平台来控制显示隐藏

* ✅ **窗口标题显示为流媒体账号名称（邮箱前缀）**

* ✅ **按任务ID或流媒体账号控制对应窗口的显示/隐藏**

## 需求细化

### 窗口标题显示规则
```
流媒体账号邮箱: user@example.com
窗口标题显示: user@example.com
或显示账号名称: StreamWindow_user@example.com
```

### 窗口控制粒度
- **按任务ID控制**: `task_id` → 窗口（一对一关系）
- **按流媒体账号控制**: 由于一个流媒体账号同时只能有一个任务，效果等同于按任务ID控制

### 核心业务规则（✅ 必须遵守）

#### 规则1：一对一关系
```
一个流媒体账号 = 一个任务 = 一个窗口
```

#### 规则2：Agent关闭时清理所有窗口
```python
async def shutdown(self):
    """优雅关闭Agent服务"""
    # 1. 停止所有任务
    await self.stop_all_tasks()

    # 2. 关闭所有窗口
    await self.window_manager.close_all_windows()

    # 3. 断开WebSocket连接
    await self.ws_client.disconnect()

    # 4. 清理资源
    await self.cleanup()
```

#### 规则3：任务步骤四完成后自动关闭窗口
```python
async def step4_execute_game_automation(context: AgentTaskContext):
    """步骤四：游戏比赛自动化"""

    try:
        # 1. 遍历所有游戏账号执行比赛
        for game_account in context.game_accounts:
            # 执行比赛
            await execute_match(game_account)

        # 2. 所有游戏账号完成比赛
        # 3. 完成所有场景处理（退出游戏、返回主界面等）

        # 4. ✅ 自动关闭窗口
        logger.info("所有游戏账号完成比赛，自动关闭窗口")
        await window_manager.close_window_by_task(context.task_id)

        return Step4Result(success=True, message="任务完成，窗口已关闭")

    except Exception as e:
        # 发生错误时也要关闭窗口
        await window_manager.close_window_by_task(context.task_id)
        raise
```

### Agent端数据结构

```python
# task_context.py
@dataclass
class WindowInfo:
    window_id: str
    streaming_account_id: str
    streaming_account_email: str  # 新增：用于显示窗口标题
    task_id: str
    window_handle: Optional[int] = None
    state: str = "created"
    created_time: Optional[float] = None
```

## 现状分析

### Agent端

* `task_context.py` 中已有 `enable_window_display: bool = True` 字段

* `task_window_manager.py` 负责窗口生命周期管理

* `sdl_window.py` 负责SDL窗口创建和渲染

### 数据库

* `task` 表有 `params` JSON字段，可存储自定义参数

* 当前没有专门的 `enable_window_display` 字段

### 前端

* 暂无窗口显示开关控件

## 实现方案

### 第一阶段：后端改动

#### 1.1 修改任务创建接口

**文件**: `bend-platform/src/main/java/com/bend/platform/service/TaskService.java`

新增任务创建时支持 `enable_window_display` 参数：

```java
// 在 TaskCreateDTO 中添加字段
private Boolean enableWindowDisplay = true;  // 默认显示窗口
```

#### 1.2 修改任务参数处理

**文件**: `bend-platform/src/main/java/com/bend/platform/service/impl/TaskServiceImpl.java`

* 在创建任务时将 `enable_window_display` 存入 `params` 字段

* 提供获取任务窗口显示状态的接口

#### 1.3 修改任务下发逻辑

**文件**: `bend-platform/src/main/java/com/bend/platform/websocket/AgentWebSocketHandler.java`

* 在下发任务时，将 `enable_window_display` 从 `params` 中取出

* 通过 WebSocket 消息传递给 Agent

***

### 第二阶段：Agent端改动

#### 2.1 修改窗口信息结构

**文件**: `bend-agent/src/agent/task/task_context.py`

扩展 `WindowInfo` 数据类：

```python
@dataclass
class WindowInfo:
    window_id: str
    streaming_account_id: str
    streaming_account_email: str  # 新增：用于窗口标题显示
    task_id: str
    window_handle: Optional[int] = None
    state: str = "created"
    is_visible: bool = True  # 新增：窗口可见性状态
    created_time: Optional[float] = None
```

#### 2.2 修改窗口创建逻辑

**文件**: `bend-agent/src/agent/windows/task_window_manager.py`

创建窗口时使用流媒体账号作为标题：

```python
async def _create_physical_window(self, window_info: WindowInfo, context: AgentTaskContext) -> int:
    """创建物理窗口，使用流媒体账号作为标题"""
    # 使用流媒体账号邮箱作为窗口标题
    window_title = context.streaming_account_email

    hwnd = win32gui.CreateWindow(
        class_atom,
        window_title,  # 窗口标题 = 流媒体账号
        win32con.WS_POPUP | win32con.WS_SYSMENU,  # 无边框，带系统菜单
        ...
    )
```

#### 2.3 实现窗口隐藏/显示控制

**文件**: `bend-agent/src/agent/windows/task_window_manager.py`

```python
async def show_window(self, window_id: str) -> bool:
    """显示指定窗口"""
    if window_id not in self._windows:
        return False

    window = self._windows[window_id]
    try:
        import win32gui
        win32gui.ShowWindow(window.window_handle, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(window.window_handle)
        window.is_visible = True
        return True
    except Exception as e:
        self.logger.error(f"显示窗口失败: {e}")
        return False

async def hide_window(self, window_id: str) -> bool:
    """隐藏指定窗口"""
    if window_id not in self._windows:
        return False

    window = self._windows[window_id]
    try:
        import win32gui
        win32gui.ShowWindow(window.window_handle, win32con.SW_HIDE)
        window.is_visible = False
        return True
    except Exception as e:
        self.logger.error(f"隐藏窗口失败: {e}")
        return False

async def show_window_by_task_id(self, task_id: str) -> bool:
    """根据任务ID显示窗口"""
    window = self.get_window_by_task(task_id)
    if window:
        return await self.show_window(window.window_id)
    return False

async def hide_window_by_task_id(self, task_id: str) -> bool:
    """根据任务ID隐藏窗口"""
    window = self.get_window_by_task(task_id)
    if window:
        return await self.hide_window(window.window_id)
    return False

async def show_window_by_streaming_account(self, streaming_account_id: str) -> List[bool]:
    """根据流媒体账号ID显示所有关联窗口"""
    windows = [w for w in self._windows.values()
               if w.streaming_account_id == streaming_account_id]
    return [await self.show_window(w.window_id) for w in windows]

async def hide_window_by_streaming_account(self, streaming_account_id: str) -> List[bool]:
    """根据流媒体账号ID隐藏所有关联窗口"""
    windows = [w for w in self._windows.values()
               if w.streaming_account_id == streaming_account_id]
    return [await self.hide_window(w.window_id) for w in windows]
```

#### 2.4 修改WebSocket消息处理

**文件**: `bend-agent/src/agent/api/websocket_client.py`

新增消息类型处理：

```python
# 新增消息类型
MessageType.WINDOW_SHOW = "window_show"
MessageType.WINDOW_HIDE = "window_hide"
MessageType.WINDOW_SHOW_BY_STREAMING = "window_show_by_streaming"
MessageType.WINDOW_HIDE_BY_STREAMING = "window_hide_by_streaming"

# 处理窗口控制消息
async def handle_window_control(self, message: dict):
    msg_type = message.get('type')
    task_id = message.get('task_id')
    streaming_account_id = message.get('streaming_account_id')

    if msg_type == MessageType.WINDOW_SHOW:
        await self.window_manager.show_window_by_task_id(task_id)
    elif msg_type == MessageType.WINDOW_HIDE:
        await self.window_manager.hide_window_by_task_id(task_id)
    elif msg_type == MessageType.WINDOW_SHOW_BY_STREAMING:
        await self.window_manager.show_window_by_streaming_account(streaming_account_id)
    elif msg_type == MessageType.WINDOW_HIDE_BY_STREAMING:
        await self.window_manager.hide_window_by_streaming_account(streaming_account_id)
```

#### 2.2 实现无按钮窗口

**文件**: `bend-agent/src/agent/windows/task_window_manager.py`

创建窗口时使用无边框、无按钮样式：

```python
# WS_POPUP | WS_VISIBLE | WS_SYSMENU (带系统菜单但无按钮)
style = win32con.WS_POPUP | win32con.WS_VISIBLE | win32con.WS_SYSMENU
# 或者使用扩展样式去除按钮
ex_style = win32con.WS_EX_TOOLWINDOW  # 工具窗口，不显示在任务栏
```

#### 2.3 修改WebSocket消息处理

**文件**: `bend-agent/src/agent/api/websocket_client.py`

新增消息类型处理：

```python
# 新增消息类型
MessageType.WINDOW_SHOW = "window_show"
MessageType.WINDOW_HIDE = "window_hide"

# 处理窗口控制消息
async def handle_window_control(self, task_id: str, show: bool):
    if show:
        await window_manager.show_window(task_id)
    else:
        await window_manager.hide_window(task_id)
```

#### 2.5 任务创建时应用窗口显示设置

**文件**: `bend-agent/src/agent/task/task_executor.py`

在创建任务时应用窗口显示设置，并将 streaming\_account\_email 传入窗口创建：

```python
async def execute_task(self, task_id: str, params: dict):
    # 获取窗口显示设置和流媒体账号信息
    enable_window_display = params.get('enable_window_display', True)
    streaming_account_email = params.get('streaming_account_email', '')
    streaming_account_id = params.get('streaming_account_id', '')

    # 创建任务上下文
    context = AgentTaskContext(
        task_id=task_id,
        streaming_account_id=streaming_account_id,
        streaming_account_email=streaming_account_email,  # 传递给上下文
        ...
        enable_window_display=enable_window_display
    )

    # 创建窗口（使用流媒体账号作为标题）
    if enable_window_display:
        # 创建窗口并显示
        window_info = WindowInfo(
            window_id=f"window_{task_id}",
            streaming_account_id=streaming_account_id,
            streaming_account_email=streaming_account_email,  # 用于窗口标题
            task_id=task_id
        )
        window_info = await self.window_manager.create_window_for_task(context, window_info)
    else:
        # 创建隐藏窗口
        window_info = WindowInfo(
            window_id=f"window_{task_id}",
            streaming_account_id=streaming_account_id,
            streaming_account_email=streaming_account_email,
            task_id=task_id
        )
        window_info = await self.window_manager.create_hidden_window_for_task(context, window_info)

    # 立即上报窗口信息给平台
    await self.report_window_info(window_info, context)

    # ✅ 检查该流媒体账号是否已有活跃窗口（业务规则校验）
    existing_windows = await self.window_manager.get_windows_by_streaming_account(streaming_account_id)
    if existing_windows:
        # 理论上不应该发生，因为平台应该阻止重复任务
        logger.warning(f"流媒体账号 {streaming_account_id} 已存在活跃窗口，将关闭旧窗口")
        for old_window in existing_windows:
            await self.window_manager.close_window(old_window.window_id)

#### 2.6 步骤四完成后自动关闭窗口
**文件**: `bend-agent/src/agent/automation/step4_game_automation.py`

```python
async def step4_execute_game_automation(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> Step4Result:
    """
    步骤四执行：游戏比赛自动化

    核心流程：
    1. 遍历所有游戏账号执行比赛
    2. 等待所有账号完成比赛
    3. 完成场景处理（退出游戏、返回主界面）
    4. ✅ 自动关闭窗口
    """

    logger = get_logger(f'step4_game_{context.task_id}')

    try:
        # 1. 遍历游戏账号执行比赛
        for game_account in context.game_accounts:
            logger.info(f"开始处理游戏账号: {game_account.gamertag}")

            # 执行比赛...
            await execute_match_for_account(game_account, context)

            # 检查是否取消
            if check_cancel():
                await close_window_on_error(context, "任务被取消")
                return Step4Result(success=False, error_code="CANCELLED")

        # 2. 所有游戏账号完成比赛
        logger.info(f"所有 {len(context.game_accounts)} 个游戏账号完成比赛")

        # 3. 场景处理：退出游戏，返回Xbox主界面
        await handle_exit_game_scenario(context)

        # 4. ✅ 自动关闭窗口（任务完成）
        logger.info("任务完成，自动关闭窗口")
        await context.window_manager.close_window_by_task(context.task_id)

        # 5. 上报窗口关闭事件
        await report_progress(context.task_id, "WINDOW_CLOSED", "CLOSED", "窗口已关闭")
        await self.report_window_closed(context.task_id, "task_completed")

        return Step4Result(
            success=True,
            message="所有游戏账号完成比赛，窗口已关闭",
            total_matches=context.matches_completed_today
        )

    except asyncio.CancelledError:
        logger.warning("任务被取消")
        await close_window_on_error(context, "任务被取消")
        raise

    except Exception as e:
        logger.error(f"步骤四执行失败: {e}")
        await close_window_on_error(context, str(e))
        return Step4Result(success=False, error_code="EXCEPTION", message=str(e))


async def close_window_on_error(context: AgentTaskContext, reason: str):
    """发生错误时关闭窗口"""
    try:
        logger = get_logger(f'cleanup_{context.task_id}')
        logger.info(f"发生错误，关闭窗口: {reason}")

        # 尝试场景处理，退出游戏
        await handle_exit_game_scenario(context)

        # 关闭窗口
        await context.window_manager.close_window_by_task(context.task_id)

        # 上报窗口关闭事件
        await self.report_window_closed(context.task_id, "error")
    except Exception as e:
        logger.error(f"关闭窗口失败: {e}")
```

#### 2.7 Agent关闭时清理所有窗口
**文件**: `bend-agent/src/agent/core/agent_main.py` 或 `shutdown_manager.py`

```python
class AgentShutdownManager:
    """Agent优雅关闭管理器"""

    def __init__(self, window_manager: TaskWindowManager):
        self.window_manager = window_manager
        self.logger = get_logger('shutdown_manager')

    async def shutdown(self, reason: str = "normal_shutdown"):
        """
        优雅关闭Agent服务

        关闭顺序：
        1. 停止所有正在执行的任务
        2. 关闭所有窗口
        3. 断开WebSocket连接
        4. 清理资源
        """
        self.logger.info(f"开始关闭Agent服务，原因: {reason}")

        try:
            # 1. 停止所有任务
            self.logger.info("停止所有任务...")
            await self.stop_all_tasks()

            # 2. 关闭所有窗口
            self.logger.info("关闭所有窗口...")
            await self.window_manager.close_all_windows()

            # 3. 断开WebSocket连接
            self.logger.info("断开WebSocket连接...")
            await self.ws_client.disconnect()

            # 4. 清理资源
            self.logger.info("清理资源...")
            await self.cleanup()

            self.logger.info("Agent服务已关闭")

        except Exception as e:
            self.logger.error(f"关闭过程中发生错误: {e}")
            # 强制关闭所有窗口
            await self.force_close_all_windows()
            raise

    async def stop_all_tasks(self):
        """停止所有正在执行的任务"""
        # 向平台发送任务取消请求
        for task_id in self.running_tasks:
            try:
                await self.task_scheduler.cancel_task(task_id)
            except Exception as e:
                self.logger.error(f"停止任务 {task_id} 失败: {e}")

    async def close_all_windows(self):
        """关闭所有窗口"""
        windows = self.window_manager.get_all_windows()
        self.logger.info(f"准备关闭 {len(windows)} 个窗口")

        for window in windows:
            try:
                await self.window_manager.close_window(window.window_id)
                self.logger.info(f"窗口 {window.window_id} 已关闭")
            except Exception as e:
                self.logger.error(f"关闭窗口 {window.window_id} 失败: {e}")

        self.logger.info("所有窗口已关闭")
```

***

### 第三阶段：前端改动

#### 3.1 添加开关控件

**文件**: `bend-platform-web/src/views/automation/TaskCreateDialog.vue`

```vue
<el-form-item label="显示游戏窗口">
  <el-switch
    v-model="taskForm.enableWindowDisplay"
    :active-value="true"
    :inactive-value="false"
  />
</el-form-item>
```

#### 3.2 任务详情页添加控制按钮

**文件**: `bend-platform-web/src/views/automation/TaskDetailDialog.vue`

添加按任务ID控制窗口的按钮：

```vue
<el-button @click="handleShowWindow(task.id)">显示窗口</el-button>
<el-button @click="handleHideWindow(task.id)">隐藏窗口</el-button>
```

#### 3.3 流媒体账号详情页添加窗口控制

**文件**: `bend-platform-web/src/views/streaming/StreamingAccountDetail.vue`

在流媒体账号详情页显示关联窗口的状态，并提供控制按钮：

```vue
<div class="window-control">
  <span>关联窗口：{{ taskWindowCount }} 个</span>
  <el-button @click="handleShowAllWindows(streamingAccount.id)">全部显示</el-button>
  <el-button @click="handleHideAllWindows(streamingAccount.id)">全部隐藏</el-button>
</div>
```

实现方法：

```javascript
const handleShowAllWindows = async (streamingAccountId) => {
  await agentApi.showWindowsByStreamingAccount(streamingAccountId)
}

const handleHideAllWindows = async (streamingAccountId) => {
  await agentApi.hideWindowsByStreamingAccount(streamingAccountId)
}
```

***

### 第四阶段：数据库改动

#### 4.1 数据库迁移脚本

**文件**: `bend-platform/db/migration/V2.3__add_window_display_flag.sql`

```sql
-- 窗口显示功能已通过 params JSON 字段实现，无需新增字段
-- 如需优化查询性能，可添加虚拟列或索引
```

说明：使用现有的 `params` JSON 字段存储 `enable_window_display`，无需修改表结构。

***

## 技术实现细节

### WebSocket 消息协议扩展

#### 按任务ID控制的消息格式（同时适用于流媒体账号）
```json
{
  "type": "window_control",
  "task_id": "task_123456",
  "action": "show"
}
```

```json
{
  "type": "window_control",
  "task_id": "task_123456",
  "action": "hide"
}
```

> **说明**: 由于一个流媒体账号同时只能有一个任务，按任务ID控制就等于按流媒体账号控制。

#### 任务下发消息扩展
```json
{
  "type": "task",
  "task_id": "task_123456",
  "params": {
    "streaming_account_id": "streaming_789",
    "streaming_account_email": "user@example.com",
    "enable_window_display": false
  }
}
```

#### 窗口信息上报消息
```json
{
  "type": "window_info",
  "task_id": "task_123456",
  "streaming_account_email": "user@example.com",
  "window_handle": 123456,
  "is_visible": true,
  "state": "running"
}
```

#### 窗口关闭事件上报
```json
{
  "type": "window_closed",
  "task_id": "task_123456",
  "reason": "task_completed"
}
```

### 窗口样式设置

使用 Windows API 控制窗口样式：

```python
import win32gui
import win32con

# 创建无按钮窗口（WS_POPUP：无边框窗口）
style = win32con.WS_POPUP | win32con.WS_SYSMENU
# WS_POPUP: 弹出式窗口
# WS_SYSMENU: 显示系统菜单（右键菜单仍可用）

# 或者使用 WS_OVERLAPPEDWINDOW 去除按钮
# WS_OVERLAPPED: 有标题栏
# ~WS_THICKFRAME: 去除可调整大小的边框
# ~WS_MINIMIZEBOX: 去除最小化按钮
# ~WS_MAXIMIZEBOX: 去除最大化按钮
style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU | win32con.WS_CAPTION
style = style & ~win32con.WS_THICKFRAME & ~win32con.WS_MINIMIZEBOX & ~win32con.WS_MAXIMIZEBOX

# 扩展样式
ex_style = win32con.WS_EX_TOOLWINDOW  # 工具窗口，不显示在任务栏

hwnd = win32gui.CreateWindowEx(
    ex_style,
    class_atom,
    "user@example.com",  # 窗口标题 = 流媒体账号邮箱
    style,
    0, 0,  # x, y
    1280, 720,  # width, height
    None,
    None,
    None,
    None
)

# 显示/隐藏窗口
win32gui.ShowWindow(hwnd, win32con.SW_SHOW)     # 显示窗口
win32gui.ShowWindow(hwnd, win32con.SW_HIDE)     # 隐藏窗口
win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE) # 最小化到任务栏
win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)  # 恢复正常/从隐藏恢复

# 更新窗口标题
win32gui.SetWindowText(hwnd, "new_title@example.com")
```

***

## 风险评估

| 风险项            | 影响 | 缓解措施             |
| -------------- | -- | ---------------- |
| 窗口隐藏后无法恢复      | 高  | 提供前端控制按钮，确保有恢复机制 |
| 窗口样式设置不当导致无法交互 | 中  | 使用标准窗口样式，仅隐藏按钮   |
| WebSocket连接不稳定 | 中  | 实现消息重发和状态同步      |
| Agent端窗口创建失败   | 中  | 添加详细日志和错误处理      |
| ✅ **步骤四执行过程中异常退出** | 高 | 添加异常处理，确保错误时也关闭窗口 |
| ✅ **Agent异常关闭导致窗口未清理** | 高 | Agent启动时检查并清理残留窗口 |
| ✅ **重复任务导致窗口冲突** | 中 | 任务创建时检查并关闭旧窗口 |

***

## 测试计划

### 单元测试
- [ ] Agent端窗口显示/隐藏功能测试
- [ ] WebSocket消息处理测试
- [ ] 后端任务创建和参数传递测试
- [ ] 步骤四完成后自动关闭窗口逻辑测试

### 集成测试
- [ ] 平台创建任务时设置窗口显示
- [ ] 平台实时切换窗口显示状态
- [ ] 任务执行时窗口样式正确（无按钮）
- [ ] 窗口隐藏后能正常恢复显示
- [ ] ✅ **步骤四完成后自动关闭窗口**
- [ ] ✅ **Agent关闭时自动关闭所有窗口**

### 手动测试
- [ ] 在Agent机器上验证窗口无最大化/最小化/关闭按钮
- [ ] 测试窗口隐藏和显示的视觉效果
- [ ] ✅ 验证一个流媒体账号只有一个窗口
- [ ] ✅ 验证Agent重启后所有窗口被清理
- [ ] ✅ 验证任务完成后窗口自动关闭

### 业务规则测试重点

#### ✅ 测试场景1：一对一关系验证
```
1. 创建一个流媒体账号的任务
2. 验证创建了一个窗口
3. 尝试再创建同一个流媒体账号的任务
4. 验证旧窗口被关闭，新窗口被创建
```

#### ✅ 测试场景2：步骤四完成后自动关闭窗口
```
1. 创建一个任务，包含多个游戏账号
2. 执行任务，完成所有游戏账号的比赛
3. 验证步骤四执行完成后窗口自动关闭
4. 验证平台收到窗口关闭事件
```

#### ✅ 测试场景3：Agent关闭时清理窗口
```
1. Agent上有多个运行中的任务和窗口
2. 关闭Agent服务
3. 验证所有窗口在关闭前被清理
4. 验证没有遗留窗口
```

#### ✅ 测试场景4：窗口标题显示流媒体账号
```
1. 创建一个流媒体账号的任务
2. 验证窗口标题显示为流媒体账号邮箱
3. 验证窗口标题正确显示中文
```

***

## 完整流程图

### 按流媒体账号控制窗口流程

```
┌─────────────┐
│  平台前端   │
│ 流媒体账号  │
│   详情页    │
└──────┬──────┘
       │
       │ 1. 点击"全部隐藏"
       │    streaming_account_id
       ▼
┌──────────────────────────────┐
│       平台后端API           │
│ StreamingAccountController  │
│                              │
│ 2. 查找流媒体账号绑定的Agent │
│ 3. 构造窗口控制消息         │
└──────────┬───────────────────┘
           │
           │ 4. WebSocket消息
           │    type: "window_control"
           │    streaming_account_id: "xxx"
           │    action: "hide"
           ▼
┌──────────────────────────────┐
│      Agent WebSocket         │
│   websocket_client.py       │
│                              │
│ 5. 解析消息类型              │
│ 6. 调用窗口管理器            │
└──────────┬───────────────────┘
           │
           │ 7. hide_window_by_streaming_account()
           ▼
┌──────────────────────────────┐
│    TaskWindowManager         │
│                              │
│ 8. 遍历所有窗口              │
│ 9. 找到匹配的streaming_id    │
│ 10. 调用win32gui.ShowWindow │
│     (hwnd, SW_HIDE)         │
└──────────────────────────────┘
           │
           │ 11. 窗口隐藏成功
           ▼
        完成
```

### 按任务ID控制窗口流程

```
┌─────────────┐
│  平台前端   │
│ 任务详情页  │
└──────┬──────┘
       │
       │ 1. 点击"隐藏窗口"
       │    task_id
       ▼
┌──────────────────────────────┐
│       平台后端API           │
│    TaskController           │
│                              │
│ 2. 查找任务绑定的Agent      │
│ 3. 构造窗口控制消息         │
└──────────┬───────────────────┘
           │
           │ 4. WebSocket消息
           │    type: "window_control"
           │    task_id: "xxx"
           │    action: "hide"
           ▼
┌──────────────────────────────┐
│      Agent WebSocket         │
│                              │
│ 5. 解析消息类型              │
│ 6. 调用窗口管理器            │
└──────────┬───────────────────┘
           │
           │ 7. hide_window_by_task_id()
           ▼
┌──────────────────────────────┐
│    TaskWindowManager         │
│                              │
│ 8. 根据task_id查找窗口        │
│ 9. 调用win32gui.ShowWindow   │
│    (hwnd, SW_HIDE)          │
└──────────────────────────────┘
```

## 部署顺序

1. **第一阶段**: 部署后端改动（支持窗口参数）
2. **第二阶段**: 部署Agent改动（窗口控制逻辑）
3. **第三阶段**: 部署前端改动（开关控件）
4. **验证**: 通过 Docker Compose 完整验证流程

***

## 关键文件清单

### 后端 (Java)

* `bend-platform/src/main/java/com/bend/platform/entity/Task.java` - 任务实体（params字段）

* `bend-platform/src/main/java/com/bend/platform/dto/TaskCreateDTO.java` - enableWindowDisplay字段

* `bend-platform/src/main/java/com/bend/platform/service/impl/TaskServiceImpl.java` - 任务创建和参数处理

* `bend-platform/src/main/java/com/bend/platform/websocket/AgentWebSocketHandler.java` - WebSocket消息转发

#### 后端关键实现：按流媒体账号找到对应Agent

**文件**: `bend-platform/src/main/java/com/bend/platform/service/impl/StreamingAccountServiceImpl.java`

```java
// 根据流媒体账号ID查找绑定的Agent
public AgentInstance findAgentByStreamingAccount(String streamingAccountId) {
    StreamingAccount account = streamingAccountMapper.selectById(streamingAccountId);
    if (account == null || account.getAgentId() == null) {
        return null;
    }
    return agentInstanceMapper.selectByAgentId(account.getAgentId());
}

// 处理窗口控制请求（按流媒体账号）
public void handleWindowControlByStreamingAccount(String streamingAccountId, String action) {
    AgentInstance agent = findAgentByStreamingAccount(streamingAccountId);
    if (agent == null) {
        throw new BusinessException("Streaming account not bound to any agent");
    }

    // 构造WebSocket消息
    Map<String, Object> message = new HashMap<>();
    message.put("type", "window_control");
    message.put("streaming_account_id", streamingAccountId);
    message.put("action", action);

    // 发送到对应Agent
    webSocketHandler.sendMessageToAgent(agent.getAgentId(), message);
}
```

#### 后端关键实现：按任务ID找到对应Agent

**文件**: `bend-platform/src/main/java/com/bend/platform/service/impl/TaskServiceImpl.java`

```java
// 根据任务ID查找绑定的Agent
public AgentInstance findAgentByTask(String taskId) {
    Task task = taskMapper.selectById(taskId);
    if (task == null || task.getTargetAgentId() == null) {
        return null;
    }
    return agentInstanceMapper.selectByAgentId(task.getTargetAgentId());
}

// 处理窗口控制请求（按任务ID）
public void handleWindowControlByTask(String taskId, String action) {
    AgentInstance agent = findAgentByTask(taskId);
    if (agent == null) {
        throw new BusinessException("Task not assigned to any agent");
    }

    Map<String, Object> message = new HashMap<>();
    message.put("type", "window_control");
    message.put("task_id", taskId);
    message.put("action", action);

    webSocketHandler.sendMessageToAgent(agent.getAgentId(), message);
}
```

### Agent端 (Python)
- `bend-agent/src/agent/task/task_context.py` - WindowInfo新增streaming_account_email字段
- `bend-agent/src/agent/windows/task_window_manager.py` - 窗口标题、隐藏/显示、按流媒体账号控制
- `bend-agent/src/agent/api/websocket_client.py` - 消息类型和处理逻辑
- `bend-agent/src/agent/task/task_executor.py` - 任务创建时传入窗口参数
- `bend-agent/src/agent/automation/step4_game_automation.py` - ✅ 步骤四完成后自动关闭窗口
- `bend-agent/src/agent/core/agent_main.py` - ✅ Agent关闭时清理所有窗口
- `bend-agent/src/agent/core/shutdown_manager.py` - ✅ Agent优雅关闭管理器（可选单独文件）

### 前端 (Vue)
- `bend-platform-web/src/views/automation/TaskCreateDialog.vue` - 添加窗口显示开关
- `bend-platform-web/src/views/automation/TaskDetailDialog.vue` - 添加窗口控制按钮

### 数据库

* `bend-platform/db/migration/V2.3__add_window_display_flag.sql` (可选)

