"""
Bend Agent 任务执行器
=====================

功能说明：
- 负责接收并执行从平台下发的各类任务
- 支持高并发任务执行（默认100个并发任务）
- 通过 SmartGlass 协议同时控制多台 Xbox 主机
- 无需 Xbox App 窗口，纯 TCP 协议控制

主要组件：
- TaskStatus: 任务状态枚举
- Task: 任务数据类
- XboxSession: Xbox 智能玻璃会话（单个 TCP 连接）
- XboxSessionManager: Xbox 会话管理器（管理连接池）
- HighConcurrencyTaskExecutor: 高并发任务执行器

作者：技术团队
版本：2.0
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
from collections import defaultdict
import threading
import time

from ..core.logger import get_logger
from ..core.config import config


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


class XboxSession:
    """
    Xbox 智能玻璃会话

    功能说明：
    - 代表与一台 Xbox 主机的单个 TCP 连接
    - 通过 SmartGlass 协议与 Xbox 通信
    - 一个会话对应一台 Xbox，可以执行多次任务

    技术原理：
    - SmartGlass 是微软的远程控制协议
    - 基于 TCP Socket 通信
    - 支持发送控制指令、获取主机状态等

    重要特性：
    - 独立 TCP 连接，不依赖 Windows Xbox App
    - 可同时维护多个到不同 Xbox 的连接
    - 连接可复用，减少频繁建立/断开开销
    """

    def __init__(self, xbox_ip: str, xbox_port: int = 5050):
        """
        初始化 Xbox 会话

        参数：
        - xbox_ip: Xbox 主机 IP 地址
        - xbox_port: SmartGlass 端口，默认 5050
        """
        self.xbox_ip = xbox_ip
        self.xbox_port = xbox_port
        self.stream_ctrl = None       # Xbox 流控制器实例
        self.input_ctrl = None        # 输入控制器实例
        self.is_connected = False    # 是否已连接
        self.is_busy = False          # 是否正在执行任务
        self.current_streaming_account_id: Optional[str] = None  # 当前流媒体账号ID
        self.current_task_id: Optional[str] = None              # 当前任务ID
        self._lock = threading.Lock()                            # 线程锁
        self._connect_time: Optional[float] = None              # 连接建立时间

    async def connect(self) -> bool:
        """
        连接到 Xbox 主机

        原理：
        1. 创建 XboxStreamController 实例
        2. 通过 asyncio 建立 TCP 连接到 Xbox
        3. 成功后标记 is_connected = True

        返回：
        - True: 连接成功
        - False: 连接失败
        """
        if self.is_connected:
            return True

        try:
            from ..xbox.stream_controller import XboxStreamController
            self.stream_ctrl = XboxStreamController()
            self.is_connected = await self.stream_ctrl.connect(self.xbox_ip, self.xbox_port)
            if self.is_connected:
                self._connect_time = time.time()
            return self.is_connected
        except Exception as e:
            self.logger.error(f"连接Xbox {self.xbox_ip} 失败: {e}")
            return False

    async def disconnect(self):
        """
        断开与 Xbox 的连接

        清理内容：
        - 关闭 TCP 连接
        - 重置所有状态标志
        - 清除当前任务和账号信息
        """
        try:
            if self.stream_ctrl and self.is_connected:
                await self.stream_ctrl.disconnect()
        except Exception as e:
            pass
        finally:
            self.is_connected = False
            self.is_busy = False
            self.current_streaming_account_id = None
            self.current_task_id = None

    @property
    def logger(self):
        """获取该会话的日志记录器"""
        return get_logger(f'xbox_session_{self.xbox_ip}')


class XboxSessionManager:
    """
    Xbox 会话管理器

    功能说明：
    - 管理多个 XboxSession 实例（连接池）
    - 控制最大并发连接数
    - 提供会话的获取和释放机制

    技术实现：
    - 使用 asyncio.Lock 保证线程安全
    - 使用 Semaphore 控制并发连接数
    - 维护 IP 到会话的映射关系

    连接限制：
    - max_sessions: 最大并发连接数（默认100）
    - 每个 IP 对应一个会话，会话复用
    """

    def __init__(self, max_sessions: int = 100):
        """
        初始化会话管理器

        参数：
        - max_sessions: 最大并发会话数
        """
        self.logger = get_logger('xbox_session_manager')
        self._max_sessions = max_sessions
        self._sessions: Dict[str, XboxSession] = {}    # key: "IP:Port"
        self._session_lock = asyncio.Lock()           # 异步锁
        self._ip_to_key: Dict[str, str] = {}         # IP -> key 映射
        self._session_semaphore = asyncio.Semaphore(max_sessions)  # 并发控制信号量

    async def get_session(self, xbox_ip: str, xbox_port: int = 5050, timeout: float = 30.0) -> Optional[XboxSession]:
        """
        获取或创建 Xbox 会话

        工作流程：
        1. 如果已存在该 IP 的会话且已连接，直接返回
        2. 如果会话存在但断开，尝试重连
        3. 如果不存在，创建新会话
        4. 获取信号量许可，限制总连接数

        参数：
        - xbox_ip: Xbox 主机 IP
        - xbox_port: SmartGlass 端口
        - timeout: 获取会话超时时间（秒），默认30秒

        返回：
        - XboxSession: 会话实例
        - None: 获取失败（超时或连接失败）
        """
        key = f"{xbox_ip}:{xbox_port}"

        try:
            await asyncio.wait_for(self._session_semaphore.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning(f"获取Xbox会话信号量超时 - IP: {xbox_ip}, timeout: {timeout}s")
            return None

        async with self._session_lock:
            if key in self._sessions:
                session = self._sessions[key]
                if not session.is_connected:
                    await session.connect()
                if not session.is_connected:
                    self._session_semaphore.release()
                    return None
                return session

            session = XboxSession(xbox_ip, xbox_port)
            connected = await session.connect()

            if connected:
                self._sessions[key] = session
                self._ip_to_key[xbox_ip] = key
                self.logger.info(f"创建Xbox会话 {key} (当前总数: {len(self._sessions)})")
                return session
            else:
                self._session_semaphore.release()
                self.logger.error(f"无法连接到Xbox {key}")
                return None

    async def release_session(self, xbox_ip: str):
        """
        释放会话（断开连接并移除）

        用于：
        - 任务完成后的资源释放
        - 主动断开连接
        - 连接超时清理

        注意：会释放信号量许可，允许创建新连接
        """
        async with self._session_lock:
            key = self._ip_to_key.pop(xbox_ip, None)
            if key and key in self._sessions:
                session = self._sessions.pop(key)
                await session.disconnect()
                self._session_semaphore.release()
                self.logger.info(f"释放Xbox会话 {key} (当前总数: {len(self._sessions)})")

    def get_active_session_count(self) -> int:
        """获取当前活跃（已连接）的会话数量"""
        return sum(1 for s in self._sessions.values() if s.is_connected)

    def get_session_by_ip(self, xbox_ip: str) -> Optional[XboxSession]:
        """
        根据 IP 获取会话（不加锁，用于查询）

        注意：返回的会话可能被其他任务使用，请查看 is_busy 状态
        """
        key = self._ip_to_key.get(xbox_ip)
        if key:
            return self._sessions.get(key)
        return None

    async def close_all(self):
        """关闭所有会话（用于 Agent  shutdown）"""
        async with self._session_lock:
            for session in self._sessions.values():
                await session.disconnect()
            self._sessions.clear()
            self._ip_to_key.clear()
            self.logger.info("已关闭所有Xbox会话")


class HighConcurrencyTaskExecutor:
    """
    高并发任务执行器

    功能说明：
    - 接收平台下发的任务并执行
    - 支持100+并发任务
    - 自动管理 Xbox 会话的生命周期
    - 提供任务取消和状态查询

    架构设计：
    - 所有任务共享信号量控制并发数
    - Xbox 相关任务使用独立的会话管理器
    - 非 Xbox 任务可真正并行执行

    任务类型支持：
    - stream_control / xbox_automation: Xbox 自动化任务
    - template_match: 模板匹配任务
    - input_sequence: 输入序列任务
    - scene_detection: 场景检测任务
    """

    def __init__(self, max_concurrent: int = 100, max_xbox_sessions: int = 100):
        """
        初始化任务执行器

        参数：
        - max_concurrent: 最大并发任务数
        - max_xbox_sessions: 最大 Xbox 会话数
        """
        self.logger = get_logger('task_executor')
        self._max_concurrent = max_concurrent
        self._max_xbox_sessions = max_xbox_sessions

        # API客户端，用于与后端通信（如令牌交换）
        self._api_client = None

        # 任务状态管理
        self._running_tasks: Dict[str, asyncio.Task] = {}   # 正在运行的任务
        self._task_status: Dict[str, TaskStatus] = {}       # 任务ID -> 状态
        self._task_results: Dict[str, Dict[str, Any]] = {} # 任务ID -> 结果
        self._task_handlers: Dict[str, Callable] = {}       # 任务类型 -> 处理函数
        self._cancel_events: Dict[str, asyncio.Event] = {} # 任务ID -> 取消事件
        self._task_create_times: Dict[str, float] = {}     # 任务ID -> 创建时间
        self._task_xbox_ip: Dict[str, str] = {}             # 任务ID -> Xbox IP

        self._lock = threading.Lock()

        # Xbox 会话管理器
        self._xbox_session_manager = XboxSessionManager(max_sessions=max_xbox_sessions)

        # 任务信号量，控制总体并发
        self._task_semaphore = asyncio.Semaphore(max_concurrent)

        # 结果清理
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
        task = Task(
            task_id=task_data.get('taskId'),
            name=task_data.get('name', ''),
            type=task_data.get('type', ''),
            params=task_data.get('params', {}),
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
        """
        运行单个任务的内部方法

        工作流程：
        1. 获取任务对应的处理器
        2. 如果是 Xbox 任务，获取或创建会话
        3. 调用处理器执行
        4. 捕获异常并记录结果
        5. 清理会话占用标记
        """
        xbox_session = None

        try:
            handler = self._task_handlers.get(task.type)
            if not handler:
                raise Exception(f"未注册的任务类型: {task.type}")

            # Xbox 相关任务需要获取专用会话
            if task.type in ('stream_control', 'xbox_automation'):
                streaming_account = task.params.get('streamingAccount', {})
                xbox_ip = streaming_account.get('xboxIp', '192.168.1.100')

                xbox_session = await self._xbox_session_manager.get_session(xbox_ip)
                if not xbox_session:
                    raise Exception(f"无法连接到 Xbox {xbox_ip}")

                # 记录任务与会话的关联
                self._task_xbox_ip[task.task_id] = xbox_ip
                xbox_session.is_busy = True
                xbox_session.current_task_id = task.task_id
                xbox_session.current_streaming_account_id = task.streaming_account_id

                # 创建取消检查函数
                def check_cancel():
                    return cancel_event.is_set()

                # 将会话和取消检查器注入参数
                task.params['_xbox_session'] = xbox_session
                task.params['_check_cancel'] = check_cancel

            # 执行任务
            result = await handler(task.params, check_cancel)

            # 更新任务状态
            if cancel_event.is_set():
                self._task_status[task.task_id] = TaskStatus.CANCELLED
                self._task_results[task.task_id] = {
                    'success': False,
                    'taskId': task.task_id,
                    'error': '任务被取消'
                }
            else:
                self._task_status[task.task_id] = TaskStatus.COMPLETED
                self._task_results[task.task_id] = {
                    'success': True,
                    'taskId': task.task_id,
                    'result': result
                }

            self.logger.info(f"任务完成: {task.task_id}")
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
            # 清理会话占用
            if xbox_session:
                xbox_session.is_busy = False
                xbox_session.current_task_id = None
                xbox_session.current_streaming_account_id = None

            self._task_xbox_ip.pop(task.task_id, None)

    def request_cancel(self, task_id: str):
        """
        请求取消指定任务

        取消机制：
        1. 设置取消事件
        2. 如果任务正在运行，尝试取消 asyncio.Task
        3. 如果任务持有 Xbox 会话，释放会话占用
        """
        event = self._cancel_events.get(task_id)
        if event:
            event.set()
            self.logger.info(f"已请求取消任务: {task_id}")

        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()

        # 如果任务占用着 Xbox 会话，释放它
        xbox_ip = self._task_xbox_ip.get(task_id)
        if xbox_ip:
            session = self._xbox_session_manager.get_session_by_ip(xbox_ip)
            if session and session.current_task_id == task_id:
                session.is_busy = False
                session.current_task_id = None

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
        """获取当前活跃的 Xbox 会话数量"""
        return self._xbox_session_manager.get_active_session_count()

    def get_task_ids(self) -> List[str]:
        """获取所有任务的ID列表"""
        return list(self._task_status.keys())

    def get_detailed_status(self) -> Dict[str, Any]:
        """
        获取执行器详细状态（用于监控）

        返回：
        - running_tasks: 运行中的任务数
        - total_sessions: 会话总数
        - active_xbox_sessions: 活跃 Xbox 会话数
        - max_concurrent: 最大并发数
        - max_xbox_sessions: 最大 Xbox 会话数
        - sessions: 各会话详细信息
        """
        sessions = {}
        for key, session in self._xbox_session_manager._sessions.items():
            sessions[key] = {
                'ip': session.xbox_ip,
                'port': session.xbox_port,
                'connected': session.is_connected,
                'busy': session.is_busy,
                'current_task': session.current_task_id
            }

        return {
            'running_tasks': len(self._running_tasks),
            'total_sessions': len(self._xbox_session_manager._sessions),
            'active_xbox_sessions': self.get_xbox_session_count(),
            'max_concurrent': self._max_concurrent,
            'max_xbox_sessions': self._max_xbox_sessions,
            'sessions': sessions
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
        await self._xbox_session_manager.close_all()
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
    - 多线程并发处理多个流媒体账号
    - 微软账号登录 -> Xbox 绑定
    - 自动遍历并切换游戏账号

    参数说明：
    - streaming_account: 流媒体账号信息（包含 Xbox IP 等）
    - gameAccounts: 游戏账号列表

    流程：
    1. 登录模块：调用微软登录接口获取 Refresh Token
    2. 串流模块：使用 Refresh Token 获取 Access Token，绑定 Xbox 主机
    3. 执行游戏账号自动化操作

    注意：
    - 无需 Xbox App 窗口，纯协议控制
    - 每个游戏账号会依次登录验证
    """
    from ..task.stream_control_task import StreamControlTaskHandler

    streaming_account = params.get('streamingAccount', {})

    if not streaming_account:
        raise Exception("缺少流媒体账号信息")

    if check_cancel():
        raise asyncio.CancelledError()

    # 获取API客户端用于令牌交换
    api_client = None
    try:
        from ..task.task_executor import task_executor
        api_client = task_executor._api_client
    except Exception as e:
        logger = get_logger('task_executor')
        logger.warning(f"无法获取API客户端: {e}")

    # 创建流控制任务处理器（传入API客户端用于令牌交换）
    handler = StreamControlTaskHandler(api_client=api_client)

    try:
        # 执行流控制任务
        result = handler.handle_batch_tasks(params, check_cancel)
        return result

    except asyncio.CancelledError:
        raise

    except Exception as e:
        raise Exception(f"流控制任务执行失败: {e}")


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

# 从配置文件读取并发参数
max_concurrent = config.get('task.max_concurrent', 100)
max_xbox_sessions = config.get('task.max_xbox_sessions', 100)

# 创建全局任务执行器实例
task_executor = HighConcurrencyTaskExecutor(
    max_concurrent=max_concurrent,
    max_xbox_sessions=max_xbox_sessions
)

# 注册所有任务处理器
task_executor.register_handler('stream_control', handle_stream_control)
task_executor.register_handler('xbox_automation', handle_stream_control)  # 别名
task_executor.register_handler('template_match', handle_template_match)
task_executor.register_handler('input_sequence', handle_input_sequence)
task_executor.register_handler('scene_detection', handle_scene_detection)

# 启动自动清理
task_executor.start_cleanup()
