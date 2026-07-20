"""
CentralManager - Bend Agent 核心编排组件

功能说明：
- 负责Agent的生命周期管理（启动、停止、注册、注销）
- 协调所有子组件的初始化和运行
- 处理与后端平台的WebSocket通信
- 管理任务分发和执行
- 发送心跳检测和版本更新检查
- 处理来自后端的命令和自动化控制指令

架构设计：
- 采用异步编程模型（asyncio），支持高并发任务处理
- WebSocket长连接保持与后端的实时通信
- 心跳机制确保Agent在线状态监控
- 模块化组件设计，便于扩展和维护
"""
import asyncio
import socket
import signal
import sys
import atexit
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from ..core.config import config
from ..core.logger import get_logger
from ..core.heartbeat_logger import get_heartbeat_logger
from ..api.client import ApiClient
from ..api.websocket import WSClient
from ..core.update_manager import UpdateManager, UpdateStatus
from ..window.stream_window import StreamWindow, WindowState
from ..vision.frame_capture import VideoFrameCapture
from ..vision.template_matcher import TemplateMatcher
from ..input.input_controller import InputController
from ..scene.scene_detector import SceneDetector
from ..game.account_manager import GameAccountManager


@dataclass
class AgentInfo:
    """
    Agent实例信息数据类

    属性说明：
    - agent_id: Agent唯一标识符，用于在后端系统识别该Agent
    - agent_secret: Agent密钥，用于API请求的身份验证
    - registration_code: 注册码，用于首次注册时的身份验证
    - host: Agent所在机器的IP地址
    - port: Agent监听的端口号（目前未使用，保留字段）
    - version: Agent当前版本号
    - status: Agent当前状态（online/offline/updating等）
    - last_heartbeat: 最后一次心跳时间
    - capabilities: Agent能力列表，包含支持的视频捕获、模板匹配等功能
    - os_type: 操作系统类型（Windows/Linux等）
    - os_version: 操作系统版本号
    - cpu_count: CPU核心数量
    - max_concurrent_tasks: 最大并发任务数
    """
    agent_id: str                          # Agent唯一标识符
    agent_secret: str                      # Agent密钥
    registration_code: str                  # 注册码
    host: str                              # 本机IP地址
    port: int                              # 监听端口
    version: str = "1.0.0"                 # 版本号
    status: str = "offline"               # 当前状态
    last_heartbeat: Optional[datetime] = None  # 最后心跳时间
    capabilities: Optional[Dict] = None    # Agent能力列表
    os_type: Optional[str] = None          # 操作系统类型
    os_version: Optional[str] = None       # 操作系统版本
    cpu_count: Optional[int] = None        # CPU核心数
    max_concurrent_tasks: Optional[int] = None  # 最大并发任务数


class CentralManager:
    """
    Bend Agent 中央管理器

    功能说明：
    - 统一管理Agent的所有组件和资源
    - 处理与后端平台的所有通信
    - 响应后端下发的任务和命令
    - 监控Agent运行状态和健康状况

    核心组件：
    - api: API客户端，用于HTTP请求
    - ws: WebSocket客户端，用于实时通信
    - window: Xbox流窗口管理
    - video_capture: 视频帧捕获
    - matcher: 模板匹配器，用于图像识别
    - input: 输入控制器，模拟用户输入
    - scene_detector: 场景检测器
    - account_manager: 游戏账号管理器
    - update_manager: 版本更新管理器
    """

    def __init__(self, agent_id: str, agent_secret: str, registration_code: str = None):
        """
        初始化中央管理器

        参数说明：
        - agent_id: Agent唯一标识符，用于在后端系统识别该Agent
        - agent_secret: Agent密钥，用于API请求的身份验证
        - registration_code: 注册码，用于首次注册时的身份验证（可选）

        初始化流程：
        1. 保存配置信息
        2. 初始化API和WebSocket客户端
        3. 初始化所有子组件（窗口、视频捕获、输入控制等）
        4. 创建Agent信息对象
        5. 注册退出处理函数
        """
        self.agent_id = agent_id                    # Agent唯一标识符
        self.agent_secret = agent_secret            # Agent密钥
        self.registration_code = registration_code or config.get('agent.registration_code', '')  # 注册码
        self._running = False                       # Agent运行状态标志
        self._heartbeat_task: Optional[asyncio.Task] = None    # 心跳任务
        self._ws_task: Optional[asyncio.Task] = None            # WebSocket监听任务
        self._update_check_task: Optional[asyncio.Task] = None  # 版本检查任务
        self._uninstall_requested = False           # 卸载请求标志
        self._clear_registry_requested = False      # 清除注册表请求标志
        # 按 taskId 跟踪后台任务协程，避免 WS 监听循环被长任务阻塞
        self._inflight_task_handles: Dict[str, asyncio.Task] = {}

        self.logger = get_logger('agent')            # 日志记录器
        self._heartbeat_logger = get_heartbeat_logger()

        # 初始化API客户端和WebSocket客户端
        self.api = ApiClient(agent_id, agent_secret)  # HTTP API客户端
        self.ws = WSClient(agent_id, agent_secret)    # WebSocket客户端

        # 设置任务执行器的API客户端（用于令牌交换）
        try:
            from ..task.task_executor import task_executor
            task_executor.set_api_client(self.api)
        except Exception as e:
            self.logger.warning(f"无法设置任务执行器的API客户端: {e}")

        # 初始化子组件
        self.window = StreamWindow()                 # Xbox流窗口管理器
        self.video_capture = VideoFrameCapture(self.window)  # 视频帧捕获器
        self.matcher = TemplateMatcher()             # 模板匹配器（图像识别）
        self.input = InputController()               # 输入控制器（模拟鼠标键盘）
        self.scene_detector = SceneDetector(self.matcher)  # 场景检测器
        self.account_manager = GameAccountManager(   # 游戏账号管理器
            self.input,
            self.scene_detector,
            self.matcher
        )

        # 创建Agent信息对象
        self._agent_info = AgentInfo(
            agent_id=agent_id,
            agent_secret=agent_secret,
            registration_code=self.registration_code,
            host=self._get_local_ip(),                # 获取本机IP地址
            port=0,                                    # 端口（未使用）
            version=config.get('agent.version', '1.0.0'),  # 版本号
            capabilities=self._get_capabilities()     # Agent能力列表
        )

        # 初始化更新管理器
        self.update_manager = UpdateManager(self.api, self._agent_info.version)
        self._update_manager_status_callback()       # 设置更新状态回调

        # 注册退出处理函数，确保Agent优雅关闭
        self._register_exit_handler()

        self.logger.info(f"CentralManager initialized for agent: {agent_id}")

    def _get_local_ip(self) -> str:
        """
        获取本机IP地址

        实现原理：
        - 创建UDP socket连接到外部DNS服务器（8.8.8.8:80）
        - 通过UDP连接获取本地socket绑定的IP地址
        - 连接外部地址不会实际发送数据，只是为了获取路由信息

        返回值：
        - 成功：返回本机IP地址字符串
        - 失败：返回127.0.0.1（本地回环地址）
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _get_capabilities(self) -> Dict[str, Any]:
        """
        获取Agent能力列表

        返回值说明：
        - video_capture: 是否支持视频捕获
        - template_matching: 是否支持模板匹配（图像识别）
        - input_control: 是否支持输入控制（鼠标键盘模拟）
        - scene_detection: 是否支持场景检测
        - game_account_management: 是否支持游戏账号管理
        - supported_games: 支持的游戏列表
        """
        return {
            'video_capture': True,                    # 视频捕获能力
            'template_matching': True,               # 模板匹配能力
            'input_control': True,                    # 输入控制能力
            'scene_detection': True,                 # 场景检测能力
            'game_account_management': True,          # 游戏账号管理能力
            'supported_games': ['fortnite', 'minecraft', 'cod', 'gta']  # 支持的游戏
        }

    def _update_manager_status_callback(self):
        """
        设置更新管理器状态回调函数

        回调说明：
        - 当更新状态发生变化时，会触发此回调
        - 用于记录日志和执行相应操作（如重启系统）
        """
        def on_status_change(status: UpdateStatus, progress: int):
            """更新状态变化回调处理"""
            self.logger.info(f"Update status: {status.value}, progress: {progress}%")
            if status == UpdateStatus.REBOOTING:
                # 更新需要重启系统
                self.logger.info("Update will reboot the system")
            elif status == UpdateStatus.FAILED:
                # 更新失败
                self.logger.error("Update failed")

        self.update_manager.set_status_callback(on_status_change)

    def _register_exit_handler(self):
        """
        注册退出处理函数

        功能说明：
        - 注册atexit回调，在程序正常退出时通知后端Agent离线
        - 注册信号处理器，处理SIGTERM和SIGINT信号
        - 确保Agent在关闭时能够优雅地通知后端

        信号说明：
        - SIGTERM: 优雅终止信号（kill命令默认发送）
        - SIGINT: Ctrl+C中断信号
        """
        def handle_exit():
            """atexit退出回调 - 通知后端Agent离线"""
            if self._running:
                asyncio.create_task(self._notify_offline())

        atexit.register(handle_exit)  # 注册退出回调

        # 注册信号处理器
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)  # 处理终止信号
            signal.signal(signal.SIGINT, self._signal_handler)   # 处理中断信号
        except (ValueError, OSError):
            # Windows环境可能不支持某些信号，跳过
            pass

    def _signal_handler(self, signum, frame):
        """
        处理系统信号

        参数说明：
        - signum: 信号编号
        - frame: 当前栈帧

        处理逻辑：
        - 收到信号后，设置运行状态为False
        - 创建停止任务（不等待，让事件循环自然处理）
        - 停止事件循环，触发main()中的KeyboardInterrupt处理
        """
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        
        # 创建停止任务（不等待，让事件循环自然处理）
        asyncio.create_task(self.stop(
            uninstall=self._uninstall_requested,
            clear_registry=self._clear_registry_requested
        ))
        
        # 停止事件循环，这会触发KeyboardInterrupt被main()捕获
        # main()的finally块会确保stop_manager被调用
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.stop()

    async def _notify_offline(self):
        """
        通知后端Agent即将离线

        功能说明：
        - 在Agent关闭前向后端发送离线通知
        - 让后端系统及时更新Agent状态

        异常处理：
        - 如果API客户端已关闭或不可用，跳过通知
        - 记录任何通知失败错误但不抛出异常
        """
        try:
            if self.api and hasattr(self.api, '_session') and self.api._session:
                await self.api.offline()
                self.logger.info("Notified backend of offline status")
        except Exception as e:
            self.logger.error(f"Failed to notify offline: {e}")

    async def _notify_uninstall(self, reason: str = None, clear_registry: bool = False):
        """
        通知后端Agent即将卸载

        参数说明：
        - reason: 卸载原因（可选）
        - clear_registry: 是否清除机器注册表（需要重新注册）

        功能说明：
        - 通知后端系统当前Agent即将被卸载
        - 如果需要清除注册表，同时清除本地机器标识
        - 后端可能返回needReregister标志，指示需要重新注册
        """
        try:
            if self.api and hasattr(self.api, '_session') and self.api._session:
                result = await self.api.uninstall(reason, clear_registry)
                if result.get('data', {}).get('needReregister'):
                    self.logger.info("Platform requires re-registration after uninstall")
                if clear_registry:
                    from ..core.machine_identity import machine_identity
                    machine_identity.clear_install_registry()
                    self.logger.info("Agent install registry has been cleared")
                self.logger.info("Notified backend of uninstall")
        except Exception as e:
            self.logger.error(f"Failed to notify uninstall: {e}")

    async def start(self):
        """
        启动Agent

        启动流程：
        1. 连接API服务器
        2. 使用注册码注册Agent
        3. 设置WebSocket事件处理器
        4. 启动WebSocket监听任务
        5. 启动心跳任务
        6. 启动版本检查任务

        返回值：
        - True: 启动成功
        - False: 启动失败
        """
        self.logger.info("Starting Bend Agent...")
        self._running = True

        try:
            # 连接API服务器
            await self.api.connect()

            # 检查注册码
            if not self.registration_code:
                self.logger.error("No registration code provided")
                return False

            # 注册Agent
            registered = await self.register()
            if not registered:
                self.logger.error("Failed to register agent")
                return False

            # 设置WebSocket事件处理器
            self.ws.on('task', self._handle_task)            # 任务处理
            self.ws.on('task_control', self._handle_task_control)  # 任务级控制
            self.ws.on('command', self._handle_command)      # 命令处理
            self.ws.on('version_update', self._handle_version_update)  # 版本更新
            self.ws.on('automation_control', self._handle_automation_control)  # 自动化控制
            self.ws.on('discover_xbox', self._handle_discover_xbox)  # Xbox发现指令
            self.ws.on('stop_task', self._handle_stop_task)  # 停止任务指令
            self.ws.on('cancel_task', self._handle_cancel_task)  # 取消任务指令

            # 启动各任务
            self._ws_task = asyncio.create_task(self.ws.listen())  # WebSocket监听
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())  # 心跳

            # 启动版本检查任务
            update_check_interval = config.get('agent.update_check_interval', 3600)
            self._update_check_task = asyncio.create_task(self._update_check_loop(update_check_interval))

            self.logger.info("Bend Agent started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start agent: {e}")
            await self.stop()
            return False

    async def stop(self, uninstall: bool = False, reason: str = None, clear_registry: bool = False):
        """
        停止Agent

        参数说明：
        - uninstall: 是否为卸载场景
        - reason: 停止/卸载原因
        - clear_registry: 是否清除注册表

        停止流程：
        1. 设置运行状态为False
        2. 如果是卸载，通知后端并处理注册表
        3. 取消所有后台任务
        4. 停止任务执行器
        5. 断开WebSocket和API连接
        """
        self.logger.info("Stopping Bend Agent...")
        self._running = False

        if uninstall:
            # 通知后端卸载
            await self._notify_uninstall(reason or "用户主动卸载", clear_registry)
            self._uninstall_requested = True

        # 收集所有需要取消的任务
        tasks_to_cancel = []
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            tasks_to_cancel.append(self._heartbeat_task)
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            tasks_to_cancel.append(self._ws_task)
        if self._update_check_task and not self._update_check_task.done():
            self._update_check_task.cancel()
            tasks_to_cancel.append(self._update_check_task)

        # 等待所有任务完成取消
        if tasks_to_cancel:
            # 使用 shield 保护取消操作不被外部取消
            try:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            except Exception as e:
                self.logger.debug(f"Task cancellation completed: {e}")

        # 停止任务执行器
        try:
            from ..task.task_executor import task_executor
            await task_executor.stop()
        except Exception as e:
            self.logger.error(f"Error stopping task executor: {e}")

        # 清理所有窗口
        try:
            from ..window.task_window_manager import TaskWindowManager
            window_manager = TaskWindowManager()
            await window_manager.close_all_windows()
            self.logger.info("All windows closed")
        except Exception as e:
            self.logger.error(f"Error closing windows: {e}")

        # 先关闭API客户端（防止任务清理时继续上报）
        await self.api.close()
        
        # 断开WebSocket连接
        await self.ws.disconnect()

        self.logger.info("Bend Agent stopped")

    async def register(self) -> bool:
        """
        向后端注册Agent

        注册流程：
        1. 构建注册信息（包含注册码、主机、端口、版本）
        2. 调用API进行注册
        3. 根据返回结果设置Agent状态

        返回值：
        - True: 注册成功
        - False: 注册失败
        """
        try:
            self._agent_info.port = config.get('agent.port', 8888)
            
            from .system_resource_detector import SystemResourceDetector
            sys_info = SystemResourceDetector.get_system_info()
            max_tasks = SystemResourceDetector.recommend_max_concurrent_tasks()
            
            self._agent_info.os_type = sys_info.get('platform')
            self._agent_info.os_version = sys_info.get('platform_version')
            self._agent_info.cpu_count = sys_info.get('cpu_count')
            self._agent_info.max_concurrent_tasks = max_tasks
            
            result = await self.api.register(
                registration_code=self.registration_code,
                host=self._agent_info.host,
                port=self._agent_info.port,
                version=self._agent_info.version,
                os_type=self._agent_info.os_type,
                os_version=self._agent_info.os_version,
                cpu_count=self._agent_info.cpu_count,
                max_concurrent_tasks=self._agent_info.max_concurrent_tasks,
                agent_id=self._agent_info.agent_id
            )
            if result.get('code') == 0 or result.get('code') == 200:
                # 检查后端是否返回了新的agentSecret
                data = result.get('data', {})
                if data.get('agentSecret'):
                    import base64
                    new_secret = data['agentSecret']
                    self.agent_secret = new_secret
                    # 同步更新API客户端（需要Base64编码）
                    self.api.agent_secret = new_secret
                    encoded_secret = base64.b64encode(new_secret.encode('utf-8')).decode('utf-8')
                    self.api._headers['X-Agent-Secret'] = encoded_secret
                    self.ws.agent_secret = new_secret
                    # 保存到凭证文件
                    await self._save_credentials()
                    self.logger.info("Agent secret updated from server and saved")
                    
                self._agent_info.status = 'online'
                self._apply_keyboard_mapping_from_payload(data)
                self.logger.info(f"Agent registered successfully: {self.agent_id}")
                return True
            else:
                self.logger.error(f"Registration failed: {result.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return False

    def _apply_keyboard_mapping_from_payload(self, payload: Dict) -> None:
        """从注册/心跳响应同步平台键盘映射。"""
        if not isinstance(payload, dict):
            return
        bindings = payload.get("keyboardMapping")
        if bindings is None:
            return
        try:
            from ..input.agent_keyboard_config import apply_platform_keyboard_mapping
            apply_platform_keyboard_mapping(bindings if isinstance(bindings, dict) else None)
        except Exception as exc:
            self.logger.warning("同步键盘映射失败: %s", exc)

    async def _heartbeat_loop(self):
        """
        心跳循环

        功能说明：
        - 定期向后端发送心跳请求
        - 报告Agent当前状态和运行指标
        - 让后端感知Agent在线状态

        心跳内容：
        - status: Agent状态
        - current_task_id: 当前任务ID
        - current_streaming_id: 当前流媒体账号ID
        - version: 版本号
        - running_task_count: 正在运行的任务数
        - xbox_session_count: 当前Xbox会话数
        """
        interval = config.get('agent.heartbeat_interval', 30)  # 心跳间隔（秒）

        while self._running:
            try:
                await asyncio.sleep(interval)

                # 获取任务执行器状态
                from ..task.task_executor import task_executor
                running_task_count = task_executor.get_running_count()
                xbox_session_count = task_executor.get_xbox_session_count()

                # 发送心跳
                hb_result = await self.api.heartbeat(
                    status=self._agent_info.status,
                    current_task_id=getattr(self, '_current_task_id', None),
                    current_streaming_id=getattr(self, '_current_streaming_id', None),
                    version=self._agent_info.version,
                    running_task_count=running_task_count,
                    xbox_session_count=xbox_session_count
                )
                if isinstance(hb_result, dict):
                    self._apply_keyboard_mapping_from_payload(hb_result.get("data") or {})
                self._agent_info.last_heartbeat = datetime.now()
                self._heartbeat_logger.debug(
                    "HTTP heartbeat ok (running=%s, xbox_sessions=%s)",
                    running_task_count,
                    xbox_session_count,
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._heartbeat_logger.error(f"HTTP heartbeat error: {e}")
                self.logger.error(f"HTTP heartbeat error: {e}")

    async def _update_check_loop(self, interval: int):
        """
        版本检查循环

        参数说明：
        - interval: 检查间隔（秒）

        功能说明：
        - 定期检查后端是否有新版本可用
        - 如果有新版本，记录日志通知
        - 支持强制更新和可选更新
        """
        while self._running:
            try:
                await asyncio.sleep(interval)
                update_info = await self.update_manager.check_update()
                if update_info:
                    self.logger.info(f"Update available: {update_info.latest_version}, mandatory: {update_info.mandatory}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Update check error: {e}")

    async def _handle_task(self, task_data: Dict):
        """
        处理后端下发的任务（非阻塞）：立即 create_task 放飞，WS 监听循环可继续收 task_control。

        参数说明：
        - task_data: 任务数据，包含 taskId、type、params 等字段

        注意：
        - 同一 taskId 若已有在途协程则忽略重复下发
        - 执行结果在子协程内通过 HTTP 回调通知平台
        """
        task_id = task_data.get('taskId')
        task_type = task_data.get('type')

        self.logger.info(f"Received task: {task_type} (ID: {task_id})")

        if not task_id:
            self.logger.warning("Task dispatch rejected: missing taskId")
            return

        existing = self._inflight_task_handles.get(task_id)
        if existing is not None and not existing.done():
            self.logger.warning(
                "Task %s already running, ignoring duplicate WS dispatch", task_id
            )
            return

        handle = asyncio.create_task(
            self._run_task_and_notify(task_data),
            name=f"task-{task_id}",
        )
        self._inflight_task_handles[task_id] = handle

    async def _run_task_and_notify(self, task_data: Dict):
        """在后台协程中执行任务并 HTTP 回调结果。"""
        task_id = task_data.get('taskId')
        try:
            from ..task.task_executor import task_executor
            result = await task_executor.execute_task(task_data)

            if result.get('success'):
                await self._notify_task_complete(task_id, result)
            else:
                await self._notify_task_fail(task_id, result.get('error', 'Task failed'))
        except Exception as e:
            self.logger.error(f"Task execution error: {e}")
            await self._notify_task_fail(task_id, str(e))
        finally:
            self._inflight_task_handles.pop(task_id, None)

    async def _notify_task_complete(self, task_id: str, result: Dict):
        """通知后端任务完成"""
        try:
            await self.api.complete_task(task_id, result)
        except Exception as e:
            self.logger.error(f"Failed to notify task complete to backend: {e}")

    async def _notify_task_fail(self, task_id: str, error: str):
        """通知后端任务失败"""
        try:
            await self.api.fail_task(task_id, error)
        except Exception as e:
            self.logger.error(f"Failed to notify task fail to backend: {e}")

    async def _handle_command(self, command_data: Dict):
        """
        处理后端下发的命令

        参数说明：
        - command_data: 命令数据，包含：
          - command: 命令名称
          - params: 命令参数

        支持的命令：
        - capture_frame: 捕获当前画面帧
        - switch_account: 切换游戏账号
        - get_scene: 获取当前场景
        - check_update: 检查版本更新
        - download_update: 下载更新
        - install_update: 安装更新

        返回值：
        - 字典，包含执行结果和可能的数据
        """
        command = command_data.get('command')
        params = command_data.get('params', {})

        self.logger.info(f"Received command: {command}")

        try:
            if command == 'capture_frame':
                # 捕获画面帧
                frame = await self.video_capture.capture_frame()
                return {'success': True, 'frame_id': frame.frame_id if frame else None}
            elif command == 'switch_account':
                # 游戏账号切换由 step4 AccountSwitcher 在自动化任务中执行
                self.logger.warning(
                    "switch_account 命令已弃用，请通过平台下发自动化任务 (step4) 切换账号"
                )
                return {
                    'success': False,
                    'error': 'switch_account 已弃用，请使用自动化任务流程',
                }
            elif command == 'get_scene':
                # 获取当前场景
                frame = await self.video_capture.capture_frame()
                if frame:
                    scene = await self.scene_detector.detect_scene(frame.data)
                    return {'success': True, 'scene': scene.value}
            elif command == 'check_update':
                # 检查更新
                update_info = await self.update_manager.check_update()
                if update_info:
                    return {
                        'success': True,
                        'hasUpdate': True,
                        'version': update_info.latest_version,
                        'mandatory': update_info.mandatory
                    }
                return {'success': True, 'hasUpdate': False}
            elif command == 'download_update':
                # 下载更新
                if self.update_manager.update_info:
                    success = await self.update_manager.download_update()
                    return {'success': success}
                return {'success': False, 'error': 'No update available'}
            elif command == 'install_update':
                # 安装更新
                success = await self.update_manager.install_update()
                return {'success': success}
            elif command == 'update_keyboard_mapping':
                bindings = params.get('bindings') if isinstance(params, dict) else None
                from ..input.agent_keyboard_config import apply_platform_keyboard_mapping
                apply_platform_keyboard_mapping(bindings)
                return {'success': True}
            return {'success': False, 'error': 'Unknown command'}

        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            return {'success': False, 'error': str(e)}

    async def _handle_version_update(self, data: Dict):
        """
        处理后端下发的版本更新通知

        参数说明：
        - data: 版本更新数据，包含：
          - version: 新版本号
          - downloadUrl: 下载地址
          - md5Checksum: MD5校验值
          - changelog: 更新日志
          - mandatory: 是否强制更新
          - forceRestart: 是否需要重启

        功能说明：
        - 将版本更新信息传递给更新管理器
        - 更新管理器会下载并安装更新
        """
        self.logger.info(f"Received version update notification: {data.get('version')}")
        self.update_manager.handle_version_update(data)

    async def _execute_template_match(self, params: Dict) -> Dict:
        """
        执行模板匹配任务

        参数说明：
        - params: 任务参数，包含：
          - template: 模板名称
          - threshold: 匹配阈值

        返回值说明：
        - found: 是否找到匹配
        - confidence: 匹配置信度
        - location: 匹配位置坐标
        - center: 匹配中心点坐标
        """
        template_name = params.get('template')
        threshold = params.get('threshold')

        frame = await self.video_capture.capture_frame()
        if not frame:
            return {'found': False, 'error': 'Failed to capture frame'}

        result = await self.matcher.find_template(frame.data, template_name, threshold)

        return {
            'found': result.found,
            'confidence': result.confidence,
            'location': result.location,
            'center': result.center
        }

    async def _execute_wait_for_scene(self, params: Dict) -> Dict:
        """
        执行等待场景任务

        参数说明：
        - params: 任务参数，包含：
          - scene: 目标场景名称
          - timeout: 超时时间（秒）

        返回值说明：
        - found: 是否找到目标场景
        - scene: 目标场景名称
        """
        target_scene = params.get('scene')
        timeout = params.get('timeout', 30)

        found = await self.scene_detector.wait_for_scene(
            lambda: self.video_capture.capture_frame().data,
            target_scene,
            timeout
        )

        return {'found': found, 'scene': target_scene}

    async def _execute_click(self, params: Dict) -> Dict:
        """
        执行点击任务

        参数说明：
        - params: 任务参数，包含：
          - x: 点击X坐标
          - y: 点击Y坐标
          - button: 鼠标按钮（left/right，默认left）

        返回值说明：
        - success: 是否执行成功
        """
        x = params.get('x')
        y = params.get('y')
        button = params.get('button', 'left')

        await self.input.click(x, y)
        return {'success': True}

    async def _execute_input_sequence(self, params: Dict) -> Dict:
        """
        执行输入序列任务

        参数说明：
        - params: 任务参数，包含：
          - sequence: 输入序列数组，每个元素包含：
            - type: 操作类型（click/key/wait）
            - x/y: 点击坐标（click类型）
            - key: 按键名称（key类型）
            - duration: 等待时间（wait类型）

        支持的操作类型：
        - click: 鼠标点击
        - key: 键盘按键
        - wait: 等待延迟

        返回值说明：
        - success: 是否执行成功
        """
        sequence = params.get('sequence', [])

        for action in sequence:
            action_type = action.get('type')
            if action_type == 'click':
                await self.input.click(action.get('x'), action.get('y'))
            elif action_type == 'key':
                await self.input.press_key(action.get('key'))
            elif action_type == 'wait':
                await asyncio.sleep(action.get('duration', 1))
            await asyncio.sleep(0.1)

        return {'success': True}

    async def _handle_automation_control(self, data: Dict):
        """
        处理后端下发的自动化控制指令

        参数说明：
        - data: 控制数据，包含：
          - action: 控制动作（如'stop'）
          - streamingAccountId: 流媒体账号ID

        支持的动作：
        - stop: 停止当前运行的自动化任务

        功能说明：
        - 用于后端主动停止正在运行的自动化任务
        - 会取消所有正在执行的任务
        """
        action = data.get('action')
        streaming_account_id = data.get('streamingAccountId')

        self.logger.info(f"Received automation control: action={action}, streamingAccountId={streaming_account_id}")

        if action == 'stop':
            from ..task.task_executor import task_executor
            running_count = task_executor.get_running_count()
            if running_count > 0:
                self.logger.info(f"Cancelling {running_count} running tasks")
                task_executor.cancel_all()
            self.logger.info("Automation stopped successfully")

    async def _handle_stop_task(self, data: Dict):
        """
        处理后端下发的停止任务指令

        参数说明：
        - data: 指令数据，包含：
          - taskId: 要停止的任务ID

        功能说明：
        - 停止指定的运行中任务
        - 释放相关资源（Xbox会话、窗口等）
        """
        task_id = data.get('taskId')
        self.logger.info(f"Received stop_task command for task: {task_id}")

        from ..task.automation_scheduler import get_active_scheduler
        from ..task.task_executor import task_executor

        scheduler = get_active_scheduler()
        if scheduler:
            await scheduler.force_terminate_task(task_id)
        else:
            task_executor.request_cancel(task_id)
        self.logger.info(f"Task stop requested: {task_id}")

    async def _handle_task_control(self, data: Dict):
        """处理 task_control WebSocket 消息（非阻塞）；taskId 必填。"""
        task_id = data.get('taskId') or data.get('task_id')
        if not task_id:
            self.logger.warning("task_control rejected: missing taskId")
            return {'success': False, 'error': 'taskId is required'}

        self.logger.info(
            "Received task_control: action=%s taskId=%s",
            data.get('action'),
            task_id,
        )
        asyncio.create_task(
            self._run_task_control_and_ack(data),
            name=f"task-control-{task_id}-{data.get('action')}",
        )

    async def _run_task_control_and_ack(self, data: Dict):
        """后台执行 task_control 并回传 ack，避免阻塞 WS 接收循环。"""
        task_id = data.get('taskId') or data.get('task_id')
        try:
            from ..task.automation_scheduler import get_active_scheduler, TaskControlHandler
            from ..runtime.task_registry import TaskRuntimeRegistry
            from ..runtime.input_focus import InputFocusManager

            scheduler = get_active_scheduler()
            if scheduler:
                result = await scheduler.handle_task_control(data)
            else:
                handler = TaskControlHandler(
                    TaskRuntimeRegistry.get_instance(),
                    InputFocusManager.get_instance(),
                )
                result = await handler.handle(data)
            await self.ws.send('task_control_ack', {
                'taskId': task_id,
                **result,
            })
        except Exception as e:
            self.logger.error("task_control handler error: %s", e, exc_info=True)

    async def _handle_cancel_task(self, data: Dict):
        """
        处理后端下发的取消任务指令

        参数说明：
        - data: 指令数据，包含：
          - taskId: 要取消的任务ID

        功能说明：
        - 取消指定的任务
        - 释放相关资源（Xbox会话、窗口等）
        """
        task_id = data.get('taskId')
        self.logger.info(f"Received cancel_task command for task: {task_id}")

        from ..task.automation_scheduler import get_active_scheduler
        from ..task.task_executor import task_executor

        scheduler = get_active_scheduler()
        if scheduler:
            await scheduler.force_terminate_task(task_id)
        else:
            task_executor.request_cancel(task_id)
        self.logger.info(f"Task cancel requested: {task_id}")

    async def _handle_discover_xbox(self, data: Dict):
        """
        处理后端下发的Xbox发现指令

        参数说明：
        - data: 指令数据，包含：
          - timestamp: 指令时间戳

        功能说明：
        - 触发局域网Xbox主机发现
        - 将发现结果上报到平台
        """
        self.logger.info("Received discover_xbox command from platform")

        try:
            from ..xbox.xbox_discovery import xbox_discovery

            xboxes = await xbox_discovery.discover()

            xbox_list = []
            seen_device_ids = set()
            
            for xbox in xboxes:
                if xbox.device_id and xbox.device_id not in seen_device_ids:
                    seen_device_ids.add(xbox.device_id)
                    xbox_list.append({
                        'device_id': xbox.device_id,
                        'name': xbox.name,
                        'ip_address': xbox.ip_address,
                        'port': xbox.port,
                        'live_id': xbox.live_id,
                        'console_type': xbox.console_type,
                        'firmware_version': xbox.firmware_version
                    })
                elif xbox.device_id:
                    self.logger.debug(f"Skipping duplicate Xbox device: {xbox.device_id}")

            await self.ws.send_xbox_discovered({
                'xboxes': xbox_list,
                'count': len(xbox_list)
            })

            self.logger.info(f"Xbox discovery completed, found {len(xbox_list)} unique devices")

        except Exception as e:
            self.logger.error(f"Xbox discovery failed: {e}")
            await self.ws.send_xbox_discovered({
                'xboxes': [],
                'count': 0,
                'error': str(e)
            })

    async def _save_credentials(self):
        """
        保存Agent凭证到文件
        
        功能说明：
        - 将agent_id和agent_secret保存到credentials/agent_credentials.json
        - 确保CredentialsProvider能读取到最新的凭证
        """
        try:
            import os
            import json
            
            # 获取凭证目录（与CredentialsProvider保持一致）
            credentials_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'credentials')
            os.makedirs(credentials_dir, exist_ok=True)
            credentials_file = os.path.join(credentials_dir, 'agent_credentials.json')
            
            credentials_data = {
                'agentId': self.agent_id,
                'agentSecret': self.agent_secret,
                'merchantId': '',
                'registrationCode': self.registration_code or ''
            }
            
            with open(credentials_file, 'w', encoding='utf-8') as f:
                json.dump(credentials_data, f, indent=2)
            
            self.logger.info(f"Credentials saved to: {credentials_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
