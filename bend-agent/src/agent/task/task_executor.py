"""
Bend Agent 任务执行器
=====================

接收平台 WS 任务并分发到注册的 handler。
生产串流任务走 handle_stream_control → AutomationScheduler。
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
import threading
import time

from ..core.logger import get_logger
from ..core.config import config
from ..core.concurrency_limits import resolve_concurrency_limit


class TaskStatus(Enum):
    """
    任务执行状态枚举

    状态流转：
    PENDING（待执行）→ RUNNING（运行中）→ COMPLETED（已完成）
                             ↓
                         FAILED（失败）
                             ↓
                    可重试回到 PENDING

    CANCELLED 表示任务被主动取消
    """
    IDLE = "idle"              # 空闲状态
    PENDING = "pending"        # 等待执行
    RUNNING = "running"        # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


@dataclass
class Task:
    """
    任务数据类

    属性说明：
    - task_id: 任务唯一标识符
    - name: 任务名称（人类可读）
    - type: 任务类型（stream_control, template_match 等）
    - params: 任务参数字典（包含流媒体账号、游戏账号等信息）
    - priority: 任务优先级（数值越大优先级越高）
    - streaming_account_id: 关联的流媒体账号ID
    - game_account_ids: 关联的游戏账号ID列表
    - created_at: 任务创建时间戳
    """
    task_id: str
    name: str
    type: str
    params: Dict[str, Any]
    priority: int = 0
    streaming_account_id: Optional[str] = None
    game_account_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class HighConcurrencyTaskExecutor:
    """高并发任务执行器：信号量控制并发，handler 分发任务类型。"""

    def __init__(self, max_concurrent: int = 100, max_xbox_sessions: int = 100):
        self.logger = get_logger('task_executor')
        self._max_concurrent = max_concurrent
        self._max_xbox_sessions = max_xbox_sessions  # 保留配置键，心跳兼容

        self._api_client = None

        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._task_status: Dict[str, TaskStatus] = {}
        self._task_results: Dict[str, Dict[str, Any]] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._task_create_times: Dict[str, float] = {}

        self._lock = threading.Lock()
        self._task_semaphore = asyncio.Semaphore(max_concurrent)

        self._cleanup_task: Optional[asyncio.Task] = None
        self._result_ttl = config.get('task.result_ttl', 3600)
        self._cleanup_interval = config.get('task.cleanup_interval', 300)

    def set_api_client(self, api_client):
        """
        设置API客户端

        用于任务处理器与后端通信（如令牌交换）

        参数：
        - api_client: ApiClient实例
        """
        self._api_client = api_client
        self.logger.info("API客户端已设置")

    def register_handler(self, task_type: str, handler: Callable):
        """
        注册任务处理器

        参数：
        - task_type: 任务类型字符串
        - handler: 异步处理函数，签名为 async def handler(params, check_cancel)
        """
        self._task_handlers[task_type] = handler
        self.logger.info(f"已注册任务处理器: {task_type}")

    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个任务

        工作流程：
        1. 解析任务数据创建 Task 对象
        2. 获取信号量许可（阻塞直到获得）
        3. 创建取消事件
        4. 启动异步任务执行
        5. 等待执行结果或取消

        参数：
        - task_data: 平台下发的任务数据字典

        返回：
        - 任务执行结果字典
        """
        params = task_data.get('params')
        if not isinstance(params, dict):
            params = {}

        # 平台当前将自动化载荷字段放在消息顶层；同时兼容旧版嵌套 params 并归一化为同一 dict。
        for key in (
            'taskId',
            'streamingAccount',
            'gameAccounts',
            'xboxHosts',
            'xboxInfo',
            'taskType',
            'gameActionType',
            'merchantId',
            'keyboardMapping',
        ):
            if key in task_data and key not in params:
                params[key] = task_data.get(key)

        task = Task(
            task_id=task_data.get('taskId'),
            name=task_data.get('name', ''),
            type=task_data.get('type', ''),
            params=params,
            priority=task_data.get('priority', 0),
            streaming_account_id=task_data.get('streamingAccountId'),
            game_account_ids=task_data.get('gameAccountIds', [])
        )

        self.logger.info(f"收到任务: {task.task_id}, 类型: {task.type}, 流媒体账号: {task.streaming_account_id}")

        # 获取信号量（控制并发数）
        await self._task_semaphore.acquire()

        # 创建取消事件
        cancel_event = asyncio.Event()
        self._cancel_events[task.task_id] = cancel_event
        self._task_status[task.task_id] = TaskStatus.RUNNING
        self._task_create_times[task.task_id] = time.time()

        # 创建异步任务
        asyncio_task = asyncio.create_task(self._run_task(task, cancel_event))
        self._running_tasks[task.task_id] = asyncio_task

        try:
            result = await asyncio_task
            return result
        except asyncio.CancelledError:
            self._task_status[task.task_id] = TaskStatus.CANCELLED
            return {
                'success': False,
                'taskId': task.task_id,
                'error': '任务被取消'
            }
        finally:
            # 清理任务状态
            self._running_tasks.pop(task.task_id, None)
            self._cancel_events.pop(task.task_id, None)
            self._task_semaphore.release()

    async def _run_task(self, task: Task, cancel_event: asyncio.Event):
        """运行单个任务并记录终态。"""
        try:
            handler = self._task_handlers.get(task.type)
            if not handler:
                raise Exception(f"未注册的任务类型: {task.type}")

            def check_cancel():
                return cancel_event.is_set()

            task.params['_check_cancel'] = check_cancel
            task.params['_task_executor'] = self

            result = await handler(task.params, check_cancel)

            handler_success = not (
                isinstance(result, dict) and result.get('success') is False
            )

            # 更新任务状态
            if cancel_event.is_set():
                self._task_status[task.task_id] = TaskStatus.CANCELLED
                self._task_results[task.task_id] = {
                    'success': False,
                    'taskId': task.task_id,
                    'error': '任务被取消'
                }
            elif not handler_success:
                self._task_status[task.task_id] = TaskStatus.FAILED
                self._task_results[task.task_id] = {
                    'success': False,
                    'taskId': task.task_id,
                    'error': result.get('message') or result.get('error') or '任务执行失败',
                    'result': result
                }
            else:
                self._task_status[task.task_id] = TaskStatus.COMPLETED
                self._task_results[task.task_id] = {
                    'success': True,
                    'taskId': task.task_id,
                    'result': result
                }

            self.logger.info(f"任务结束: {task.task_id}, success={self._task_results[task.task_id].get('success')}")
            return self._task_results[task.task_id]

        except asyncio.CancelledError:
            self._task_status[task.task_id] = TaskStatus.CANCELLED
            raise

        except Exception as e:
            self._task_status[task.task_id] = TaskStatus.FAILED
            self._task_results[task.task_id] = {
                'success': False,
                'taskId': task.task_id,
                'error': str(e)
            }
            self.logger.error(f"任务失败: {task.task_id}: {e}")
            return self._task_results[task.task_id]

        finally:
            pass

    def request_cancel(self, task_id: str):
        """请求取消指定任务。"""
        event = self._cancel_events.get(task_id)
        if event:
            event.set()
            self.logger.info(f"已请求取消任务: {task_id}")

        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()

    def cancel_all(self):
        """取消所有正在运行的任务"""
        for task_id in list(self._running_tasks.keys()):
            self.request_cancel(task_id)
        self.logger.info("已请求取消所有任务")

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取指定任务的状态"""
        return self._task_status.get(task_id)

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务的结果"""
        return self._task_results.get(task_id)

    def get_running_count(self) -> int:
        """获取当前正在运行的任务数量"""
        return len(self._running_tasks)

    def get_xbox_session_count(self) -> int:
        """兼容心跳字段：云端串流会话由 AutomationScheduler 管理，此处恒为 0。"""
        return 0

    def get_task_ids(self) -> List[str]:
        """获取所有任务的ID列表"""
        return list(self._task_status.keys())

    def get_detailed_status(self) -> Dict[str, Any]:
        """获取执行器详细状态（用于监控）。"""
        return {
            'running_tasks': len(self._running_tasks),
            'max_concurrent': self._max_concurrent,
        }

    def cleanup_old_results(self):
        """
        清理过期的任务结果

        目的：防止内存泄漏
        机制：删除超过 TTL 的结果记录
        """
        current_time = time.time()
        keys_to_remove = []

        for task_id, create_time in self._task_create_times.items():
            if current_time - create_time > self._result_ttl:
                keys_to_remove.append(task_id)

        for task_id in keys_to_remove:
            self._task_results.pop(task_id, None)
            self._task_status.pop(task_id, None)
            self._task_create_times.pop(task_id, None)

        if keys_to_remove:
            self.logger.info(f"清理了 {len(keys_to_remove)} 条过期任务记录")

    async def start_cleanup_timer(self):
        """
        启动定期清理定时器

        机制：
        - 每隔 cleanup_interval 秒执行一次清理
        - 无限循环，直到被取消
        """
        while True:
            await asyncio.sleep(self._cleanup_interval)
            self.cleanup_old_results()

    def start_cleanup(self):
        """启动后台清理任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self.start_cleanup_timer())
            self.logger.info("已启动任务结果清理定时器")

    async def stop(self):
        """
        停止执行器

        清理内容：
        1. 取消所有运行中的任务
        2. 关闭所有 Xbox 会话
        3. 取消清理定时器
        """
        self.cancel_all()
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self.logger.info("任务执行器已停止")

    @property
    def max_concurrent(self) -> int:
        """获取最大并发数"""
        return self._max_concurrent

    @property
    def max_xbox_sessions(self) -> int:
        """获取最大 Xbox 会话数"""
        return self._max_xbox_sessions


# =============================================
# 任务处理器实现
# =============================================

async def handle_stream_control(params: Dict[str, Any], check_cancel: Callable) -> Dict[str, Any]:
    """
    Xbox 流控制任务处理器

    功能：
    - 调用自动化调度器执行四步骤串行流程
    - 微软账号登录 -> Xbox绑定 -> 串流环境初始化 -> 游戏自动化

    参数说明：
    - streamingAccount: 流媒体账号信息（包含 Xbox IP 等）
    - gameAccounts: 游戏账号列表
    - taskId: 任务ID

    流程：
    【步骤一】自动登录 - 微软账号认证获取Token
    【步骤二】自动串流 - Xbox主机连接与认证
    【步骤三】串流环境初始化 - 准备画面捕获能力
    【步骤四】游戏自动化操控 - 执行游戏比赛等操作

    注意：
    - 四步骤串行执行，任一步骤失败则任务失败
    - 无需 Xbox App 窗口，纯协议控制
    """
    streaming_account = params.get('streamingAccount', {})
    game_accounts = params.get('gameAccounts', [])
    task_id = params.get('taskId', '')

    auto_match_host = params.get('autoMatchHost', True)
    if isinstance(auto_match_host, str):
        auto_match_host = auto_match_host.lower() not in ('false', '0', 'no')

    assigned_xbox = params.get('host') or params.get('xboxInfo')
    platform_xbox_hosts = params.get('xboxHosts') or []
    if not assigned_xbox and not auto_match_host:
        xbox_hosts = params.get('xboxHosts') or []
        if xbox_hosts:
            assigned_xbox = xbox_hosts[0]

    account_platform = (
        params.get('platform')
        or streaming_account.get('platform')
        or 'xbox'
    )

    game_action_type = params.get('gameActionType') or ''
    two_phase = not bool(game_action_type)
    phase_mode = params.get('phase') or params.get('sessionPhase')
    if phase_mode == 'streaming_only':
        two_phase = True
        game_action_type = ''

    relaunch = bool(params.get('relaunch'))

    if not streaming_account:
        raise Exception("缺少流媒体账号信息")

    if check_cancel():
        raise asyncio.CancelledError()

    # 获取Agent凭证用于HTTP认证（从集中式凭证管理器获取）
    from ..core.credentials_provider import get_credentials
    agent_id, agent_secret = get_credentials()

    from ..task.automation_scheduler import AutomationScheduler, get_active_scheduler

    scheduler = get_active_scheduler()
    if scheduler is None:
        scheduler = AutomationScheduler(agent_id=agent_id, agent_secret=agent_secret)
    else:
        scheduler.set_credentials(agent_id, agent_secret)

    keyboard_mapping = params.get('keyboardMapping')
    if not isinstance(keyboard_mapping, dict):
        keyboard_mapping = None

    try:
        # 启动自动化任务
        success = await scheduler.start_task(
            task_id=task_id,
            streaming_account_id=streaming_account.get('id', ''),
            streaming_account_email=streaming_account.get('email', ''),
            streaming_account_password=streaming_account.get('passwordToken', ''),
            streaming_account_auto_code=streaming_account.get('authCode', ''),
            game_accounts=game_accounts,
            assigned_xbox=assigned_xbox,
            game_action_type=game_action_type or "",
            account_platform=account_platform,
            auto_match_host=auto_match_host,
            two_phase=two_phase,
            relaunch=relaunch,
            platform_xbox_hosts=platform_xbox_hosts,
            keyboard_mapping=keyboard_mapping,
        )

        if not success:
            raise Exception("启动自动化任务失败")

        if two_phase and not game_action_type:
            return {
                'success': True,
                'message': 'long-lived streaming session started; waiting for automation',
                'sessionPhase': 'opening',
                'totalMatches': 0,
                'errorCode': None
            }

        # 等待任务完成（最多等待3600秒）
        timeout = 3600
        start_time = time.time()
        while time.time() - start_time < timeout:
            if check_cancel():
                await scheduler.stop_task(task_id)
                raise asyncio.CancelledError()

            result = scheduler.get_task_result(task_id)
            if result is not None:
                break

            await asyncio.sleep(1)

        if time.time() - start_time >= timeout:
            await scheduler.stop_task(task_id)
            raise Exception("任务执行超时")

        result = scheduler.get_task_result(task_id)
        if result:
            return {
                'success': result.success,
                'message': result.message,
                'totalMatches': result.total_matches if hasattr(result, 'total_matches') else 0,
                'errorCode': result.error_code if not result.success else None
            }
        else:
            raise Exception("任务执行结果为空")

    except asyncio.CancelledError:
        await scheduler.stop_task(task_id)
        raise

    except Exception as e:
        await scheduler.stop_task(task_id)
        raise Exception(f"流控制任务执行失败: {e}")

    # 注意：scheduler 为共享单例，支持多串流账号并发执行。
    # 此处禁止调用 scheduler.close()——它会触发 stop_all_tasks() 误杀其他并发任务，
    # 并关闭共享的 PlatformApiClient。当前任务的资源已由 _run_task 的 finally
    # 及各步骤（窗口关闭 / 串流断开）自行清理，无需在此关闭整个调度器。


async def handle_template_match(params: Dict[str, Any], check_cancel: Callable) -> Dict[str, Any]:
    """
    模板匹配任务处理器

    功能：
    - 在屏幕截图中查找指定模板图片
    - 返回匹配位置和置信度

    限制：
    - 需要 Xbox App 窗口可见
    - CPU 密集型，并发受限
    """
    if check_cancel():
        raise asyncio.CancelledError()

    from ..vision.template_matcher import TemplateMatcher
    from ..vision.frame_capture import VideoFrameCapture
    from ..windows.stream_window import StreamWindow

    template_name = params.get('template')
    threshold = params.get('threshold', 0.8)

    window = StreamWindow()
    capture = VideoFrameCapture(window)
    matcher = TemplateMatcher()

    frame = await capture.capture_frame()
    if not frame:
        raise Exception("截取帧失败")

    if check_cancel():
        raise asyncio.CancelledError()

    result = await matcher.find_template(frame.data, template_name, threshold)

    return {
        'found': result.found,
        'confidence': result.confidence,
        'location': result.location,
        'center': result.center
    }


async def handle_input_sequence(params: Dict[str, Any], check_cancel: Callable) -> Dict[str, Any]:
    """
    输入序列任务处理器

    功能：
    - 按顺序执行一系列输入操作
    - 支持点击、按键、文本输入、延时

    特点：
    - 纯输入操作，可以高并发执行
    - 不需要 Xbox 连接
    """
    if check_cancel():
        raise asyncio.CancelledError()

    from ..input.input_controller import InputController

    input_ctrl = InputController()
    sequence = params.get('sequence', [])

    for action in sequence:
        if check_cancel():
            raise asyncio.CancelledError()

        action_type = action.get('type')

        if action_type == 'click':
            await input_ctrl.click(action.get('x'), action.get('y'))
        elif action_type == 'key':
            await input_ctrl.press_key(action.get('key'))
        elif action_type == 'text':
            await input_ctrl.type_text(action.get('text'))
        elif action_type == 'wait':
            await asyncio.sleep(action.get('duration', 1))

        await asyncio.sleep(0.05)  # 操作间隔

    return {'success': True, 'actions_executed': len(sequence)}


async def handle_scene_detection(params: Dict[str, Any], check_cancel: Callable) -> Dict[str, Any]:
    """
    场景检测任务处理器

    功能：
    - 持续监控画面，等待特定场景出现
    - 可设置超时时间

    限制：
    - 需要 Xbox App 窗口可见
    - 长时间运行，占用资源
    """
    if check_cancel():
        raise asyncio.CancelledError()

    from ..scene.scene_detector import SceneDetector
    from ..vision.frame_capture import VideoFrameCapture
    from ..windows.stream_window import StreamWindow

    target_scene = params.get('scene')
    timeout = params.get('timeout', 30)

    window = StreamWindow()
    capture = VideoFrameCapture(window)
    detector = SceneDetector(None)

    found = await detector.wait_for_scene(
        lambda: capture.capture_frame().data,
        target_scene,
        timeout
    )

    return {
        'found': found,
        'scene': target_scene
    }


# =============================================
# 全局任务执行器实例
# =============================================

# 从配置文件读取并发参数（0=压测不限制）
max_concurrent = resolve_concurrency_limit(config.get('task.max_concurrent', 0))
max_xbox_sessions = resolve_concurrency_limit(config.get('task.max_xbox_sessions', 0))

# 创建全局任务执行器实例
task_executor = HighConcurrencyTaskExecutor(
    max_concurrent=max_concurrent,
    max_xbox_sessions=max_xbox_sessions
)

# 注册所有任务处理器
task_executor.register_handler('stream_control', handle_stream_control)
task_executor.register_handler('xbox_automation', handle_stream_control)  # 别名
task_executor.register_handler('automation', handle_stream_control)       # 别名，自动化任务
task_executor.register_handler('template_match', handle_template_match)
task_executor.register_handler('input_sequence', handle_input_sequence)
task_executor.register_handler('scene_detection', handle_scene_detection)

# 启动自动清理
task_executor.start_cleanup()
