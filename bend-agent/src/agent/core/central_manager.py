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
from ..api.client import ApiClient
from ..api.websocket import WSClient
from ..core.update_manager import UpdateManager, UpdateStatus
from ..windows.stream_window import StreamWindow, WindowState
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

        self.logger = get_logger('agent')            # 日志记录器

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
        - 调用stop方法执行优雅关闭
        - 根据之前的请求决定是否卸载或清除注册表
        """
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self.stop(
            uninstall=self._uninstall_requested,
            clear_registry=self._clear_registry_requested
        ))

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
                    # 清除本地机器标识
                    from ..core.machine_identity import machine_identity
                    machine_identity.reset_machine_id()
                    self.logger.info("Machine registry has been cleared")
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
            self.ws.on('command', self._handle_command)      # 命令处理
            self.ws.on('version_update', self._handle_version_update)  # 版本更新
            self.ws.on('automation_control', self._handle_automation_control)  # 自动化控制

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

        # 取消心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 取消WebSocket任务
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        # 取消版本检查任务
        if self._update_check_task:
            self._update_check_task.cancel()
            try:
                await self._update_check_task
            except asyncio.CancelledError:
                pass

        # 停止任务执行器
        try:
            from ..task.task_executor import task_executor
            await task_executor.stop()
        except Exception as e:
            self.logger.error(f"Error stopping task executor: {e}")

        # 断开连接
        await self.ws.disconnect()
        await self.api.close()

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
            result = await self.api.register(
                registration_code=self.registration_code,
                host=self._agent_info.host,
                port=self._agent_info.port,
                version=self._agent_info.version
            )
            if result.get('code') == 0 or result.get('code') == 200:
                self._agent_info.status = 'online'
                self.logger.info(f"Agent registered successfully: {self.agent_id}")
                return True
            else:
                self.logger.error(f"Registration failed: {result.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return False

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
                await self.api.heartbeat(
                    status=self._agent_info.status,
                    current_task_id=getattr(self, '_current_task_id', None),
                    current_streaming_id=getattr(self, '_current_streaming_id', None),
                    version=self._agent_info.version,
                    running_task_count=running_task_count,
                    xbox_session_count=xbox_session_count
                )
                self._agent_info.last_heartbeat = datetime.now()
                self.logger.debug(f"Heartbeat sent (running: {running_task_count}, xbox: {xbox_session_count})")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")

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
        处理后端下发的任务

        参数说明：
        - task_data: 任务数据，包含以下字段：
          - taskId: 任务唯一标识符
          - type: 任务类型
          - params: 任务参数

        处理流程：
        1. 从任务数据中提取任务ID和类型
        2. 将任务交给任务执行器执行
        3. 根据执行结果通知后端任务完成或失败

        注意：
        - 任务执行是异步的，不会阻塞心跳等后台任务
        - 高并发场景下，多个任务可以同时执行
        """
        task_id = task_data.get('taskId')
        task_type = task_data.get('type')

        self.logger.info(f"Received task: {task_type} (ID: {task_id})")

        try:
            # 获取任务执行器并执行任务
            from ..task.task_executor import task_executor
            result = await task_executor.execute_task(task_data)

            # 通知后端任务结果
            if result.get('success'):
                await self.api.complete_task(task_id, result)
            else:
                await self.api.fail_task(task_id, result.get('error', 'Task failed'))

        except Exception as e:
            self.logger.error(f"Task execution error: {e}")
            await self.api.fail_task(task_id, str(e))

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
                # 切换游戏账号
                account_id = params.get('account_id')
                account = self.account_manager.get_account(account_id)
                if account:
                    success = await self.account_manager.switch_to_account(
                        account,
                        lambda: self.video_capture.last_frame.data
                    )
                    return {'success': success}
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
