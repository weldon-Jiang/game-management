"""
与后端实时通信的 WebSocket 客户端。

功能说明：
- 建立与后端服务器的WebSocket长连接
- 支持实时双向消息通信
- 自动重连机制（指数退避策略）
- 心跳保活机制
- 消息分发到注册的处理器

修复说明（v2.1）：
- 添加连接锁解决竞态条件
- 添加连接状态管理避免并发重连
- 优化关闭流程确保资源释放

消息类型：
- task: 后端下发的任务
- command: 后端发送的命令
- heartbeat: 心跳消息
- status_report: 状态上报
- xbox_discovered: Xbox设备发现通知
- task_result: 任务执行结果上报
"""
import asyncio
import json
from typing import Optional, Callable, Dict, Any
from enum import Enum

from ..core.config import config
from ..core.logger import get_logger
from ..core.heartbeat_logger import get_heartbeat_logger


class WSMessageType(Enum):
    """
    WebSocket消息类型枚举 v2.0

    统一消息格式：
    {
      "type": "消息类型",
      "data": {
        "taskId": "任务ID",
        "timestamp": 1234567890,
        ...其他字段
      }
    }

    消息类型说明：
    - TASK: 后端下发的自动化任务
    - COMMAND: 后端发送的控制命令
    - PROGRESS: 进度上报（新增，统一格式）
    - HEARTBEAT: 心跳保活消息
    - HEARTBEAT_ACK: 心跳确认响应
    - XBOX_DISCOVERED: 发现新Xbox设备
    - TASK_RESULT: 任务执行结果
    - CONNECTED: 连接成功通知
    - ERROR: 错误消息
    - TASK_CONTROL: 任务级控制（必须含 taskId）
    """
    TASK = "task"                     # 任务消息
    TASK_CONTROL = "task_control"     # 任务级控制
    COMMAND = "command"               # 命令消息
    PROGRESS = "progress"             # 进度上报（新增）
    HEARTBEAT = "heartbeat"           # 心跳
    HEARTBEAT_ACK = "heartbeat_ack"   # 心跳确认
    XBOX_DISCOVERED = "xbox_discovered"  # Xbox发现
    TASK_RESULT = "task_result"       # 任务结果
    CONNECTED = "connected"           # 已连接
    ERROR = "error"                   # 错误


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"


class WSClient:
    """
    WebSocket客户端

    功能说明：
    - 维护与后端的WebSocket长连接
    - 自动重连机制确保连接可靠性
    - 心跳机制保持连接活跃
    - 消息路由到注册的处理器

    使用方式：
    - 创建实例后通过 on() 注册消息处理器
    - 调用 listen() 开始监听消息
    - 使用 send() 发送消息到后端
    """

    def __init__(self, agent_id: str, agent_secret: str):
        """
        初始化WebSocket客户端

        参数说明：
        - agent_id: Agent唯一标识符
        - agent_secret: Agent密钥（用于连接认证）
        """
        self.agent_id = agent_id                            # Agent唯一标识符
        self.agent_secret = agent_secret                    # Agent密钥
        self.ws_url = config.ws_url                        # WebSocket服务器地址
        self._ws: Optional[Any] = None                     # WebSocket连接对象
        self._running = False                               # 运行状态标志
        self._reconnect_delay = config.get('agent.reconnect_delay', 5)  # 重连延迟（秒）
        self._max_attempts = config.get('agent.max_reconnect_attempts', 10)  # 最大重连次数
        self._ws_heartbeat_interval = config.get('agent.ws_heartbeat_interval', 30)  # WebSocket心跳间隔
        self._message_handlers: Dict[str, Callable] = {}   # 消息处理器字典
        self._heartbeat_task: Optional[asyncio.Task] = None  # 心跳任务
        self.logger = get_logger('ws')                      # 日志记录器
        self._heartbeat_logger = get_heartbeat_logger()   # 心跳专用日志

        # 连接管理（v2.1新增，解决竞态条件）
        self._connection_lock = asyncio.Lock()             # 连接操作锁
        self._connection_state = ConnectionState.DISCONNECTED  # 连接状态
        self._reconnect_task: Optional[asyncio.Task] = None  # 重连任务引用
        self._ws_id = 0                                    # 连接ID，用于识别过期连接

    def on(self, message_type: str, handler: Callable):
        """
        注册消息处理器

        参数说明：
        - message_type: 消息类型（如'task', 'command'）
        - handler: 处理函数，接收消息数据作为参数

        使用示例：
        - ws.on('task', self.handle_task)
        - ws.on('command', self.handle_command)
        """
        self._message_handlers[message_type] = handler

    def off(self, message_type: str):
        """
        注销消息处理器

        参数说明：
        - message_type: 要注销的消息类型
        """
        self._message_handlers.pop(message_type, None)

    async def connect(self):
        """
        连接到WebSocket服务器

        返回值：
        - True: 连接成功
        - False: 连接失败

        URL格式：
        - ws://host:port/{agent_id}  (认证: Header X-Agent-Secret Base64)
        - 兼容: ?agentSecret= 查询参数
        """
        import base64
        import websockets

        async with self._connection_lock:
            # 检查是否已在连接中
            if self._connection_state == ConnectionState.CONNECTED:
                self.logger.debug("Already connected")
                return True

            if self._connection_state == ConnectionState.CONNECTING:
                self.logger.debug("Connection in progress, waiting...")
                await asyncio.sleep(0.5)
                return self._connection_state == ConnectionState.CONNECTED

            self._connection_state = ConnectionState.CONNECTING
            self._ws_id += 1
            current_ws_id = self._ws_id

            url = f"{self.ws_url}/{self.agent_id}"
            extra_headers = {
                'X-Agent-Secret': base64.b64encode(
                    self.agent_secret.encode('utf-8')
                ).decode('ascii'),
            }
            try:
                try:
                    self._ws = await websockets.connect(
                        url, extra_headers=extra_headers, ping_interval=None
                    )
                except TypeError:
                    # 旧版 websockets 不支持 extra_headers
                    legacy_url = f"{url}?agentSecret={self.agent_secret}"
                    self._ws = await websockets.connect(legacy_url, ping_interval=None)
                # 检查连接是否被替换（可能被其他重连任务覆盖）
                if current_ws_id != self._ws_id or not self._running:
                    self.logger.debug(f"Connection {current_ws_id} superseded, closing")
                    await self._ws.close()
                    return False
                self._connection_state = ConnectionState.CONNECTED
                self.logger.info(f"WebSocket connected (id={current_ws_id})")
                return True
            except Exception as e:
                self._connection_state = ConnectionState.DISCONNECTED
                self.logger.error(f"WebSocket connection failed: {e}")
                return False

    async def disconnect(self):
        """
        断开WebSocket连接

        功能说明：
        - 停止心跳任务
        - 关闭WebSocket连接
        - 重置状态
        """
        self._running = False

        # 取消重连任务
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # 取消心跳任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await asyncio.wait_for(self._heartbeat_task, timeout=2.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                self.logger.warning("心跳任务取消超时")

        # 关闭连接（使用锁保护）
        async with self._connection_lock:
            self._connection_state = ConnectionState.CLOSING
            if self._ws:
                try:
                    await asyncio.wait_for(self._ws.close(), timeout=3.0)
                except asyncio.TimeoutError:
                    self.logger.warning("WebSocket关闭超时")
                except Exception as e:
                    self.logger.debug(f"WebSocket关闭异常: {e}")
                self._ws = None
            self._connection_state = ConnectionState.DISCONNECTED
        self.logger.info("WebSocket disconnected")

    async def reconnect(self):
        """
        重新连接（指数退避策略）

        重连策略（v2.1优化）：
        - 使用连接锁避免并发重连
        - 最多重连_max_attempts次
        - 每次失败后延迟 = 重连延迟 * min(尝试次数, 5)
        - 连接成功后启动心跳任务
        """
        import websockets

        async with self._connection_lock:
            # 检查是否正在重连
            if self._connection_state == ConnectionState.RECONNECTING:
                self.logger.debug("Reconnection already in progress")
                return False

            # 检查是否应该重连
            if not self._running:
                self.logger.debug("Not running, skipping reconnection")
                return False

            self._connection_state = ConnectionState.RECONNECTING

        attempt = 0
        while self._running and attempt < self._max_attempts:
            attempt += 1
            self.logger.info(f"WebSocket reconnecting... attempt {attempt}/{self._max_attempts}")

            async with self._connection_lock:
                # 关闭旧连接
                if self._ws:
                    try:
                        old_ws = self._ws
                        self._ws = None
                        await asyncio.wait_for(old_ws.close(), timeout=1.0)
                    except Exception:
                        pass

                if not self._running:
                    break

                # 尝试连接
                self._connection_state = ConnectionState.CONNECTING
                self._ws_id += 1
                current_ws_id = self._ws_id

            import websockets
            url = f"{self.ws_url}/{self.agent_id}?agentSecret={self.agent_secret}"
            try:
                ws = await websockets.connect(url, ping_interval=None)

                async with self._connection_lock:
                    # 检查连接是否被替换
                    if current_ws_id != self._ws_id or not self._running:
                        await ws.close()
                        continue
                    self._ws = ws
                    self._connection_state = ConnectionState.CONNECTED

                await self._ensure_heartbeat_task()
                return True

            except Exception as e:
                self.logger.warning(f"Reconnection attempt {attempt} failed: {e}")
                async with self._connection_lock:
                    self._connection_state = ConnectionState.RECONNECTING

            await asyncio.sleep(self._reconnect_delay * min(attempt, 5))

        async with self._connection_lock:
            self._connection_state = ConnectionState.DISCONNECTED
        self.logger.error("WebSocket reconnection failed after max attempts")
        return False

    async def send(self, message_type: str, data: Dict[str, Any]) -> bool:
        """
        发送消息到后端

        参数说明：
        - message_type: 消息类型
        - data: 消息数据

        返回值：
        - True: 发送成功
        - False: 发送失败（未连接等）
        """
        async with self._connection_lock:
            if self._connection_state != ConnectionState.CONNECTED or not self._ws:
                self.logger.debug("WebSocket not connected, skipping send")
                return False

            ws = self._ws
            ws_id = self._ws_id

        try:
            message = json.dumps({
                'type': message_type,
                'data': data
            }, ensure_ascii=False)
            if message_type == 'heartbeat':
                self._heartbeat_logger.debug(
                    "WebSocket heartbeat sent (agentId=%s)", self.agent_id
                )
            else:
                self.logger.info(
                    f"Sending message to backend - Type: {message_type}, Data: {message[:500]}"
                )
            await ws.send(message)
            if message_type != 'heartbeat':
                self.logger.info(f"Message sent successfully - Type: {message_type}")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to send message: {e}")
            # 触发重连
            if self._running:
                self._schedule_reconnect()
            return False

    def _schedule_reconnect(self) -> asyncio.Task:
        """最多调度一个后台重连任务。"""
        if self._reconnect_task and not self._reconnect_task.done():
            return self._reconnect_task
        self._reconnect_task = asyncio.create_task(self._trigger_reconnect())
        return self._reconnect_task

    async def _trigger_reconnect(self):
        """触发异步重连（用于send失败时）"""
        try:
            await self.reconnect()
        except Exception as e:
            self.logger.error(f"Background reconnection failed: {e}")
        finally:
            current = asyncio.current_task()
            if self._reconnect_task is current:
                self._reconnect_task = None

    async def _ensure_heartbeat_task(self):
        """保持仅一个心跳循环存活。"""
        current = asyncio.current_task()
        if self._heartbeat_task and not self._heartbeat_task.done():
            if self._heartbeat_task is current:
                return
            self._heartbeat_task.cancel()
            try:
                await asyncio.wait_for(self._heartbeat_task, timeout=2.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                self.logger.warning("旧WebSocket心跳任务取消超时")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def send_heartbeat(self):
        """
        发送心跳消息

        心跳内容：
        - agentId: Agent标识
        - timestamp: 时间戳
        """
        return await self.send("heartbeat", {
            'agentId': self.agent_id,
            'timestamp': asyncio.get_event_loop().time()
        })

    async def send_status_report(self, status: Dict[str, Any]):
        """
        发送状态上报

        参数说明：
        - status: 状态数据字典
        """
        return await self.send("status_report", {
            'agentId': self.agent_id,
            **status
        })

    async def send_xbox_discovered(self, xbox_info: Dict[str, Any]):
        """
        发送Xbox设备发现通知

        参数说明：
        - xbox_info: Xbox设备信息
        """
        return await self.send("xbox_discovered", {
            'agentId': self.agent_id,
            **xbox_info
        })

    async def send_task_result(self, task_id: str, result: Dict[str, Any]):
        """
        发送任务执行结果

        参数说明：
        - task_id: 任务ID
        - result: 执行结果数据
        """
        return await self.send("task_result", {
            'agentId': self.agent_id,
            'taskId': task_id,
            **result
        })

    async def send_progress(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        game_account_id: str = None,
        **kwargs
    ):
        """
        发送进度上报（v2.0统一格式）

        参数说明：
        - task_id: 任务ID
        - step: 当前步骤 (STEP1|STEP2|STEP3|STEP4)
        - status: 状态 (RUNNING|COMPLETED|FAILED|GAME_PREPARING|GAMING)
        - message: 状态描述
        - game_account_id: 游戏账号ID（可选）
        - **kwargs: 其他字段

        消息格式：
        {
          "type": "progress",
          "data": {
            "agentId": "agent-xxx",
            "taskId": "task-xxx",
            "timestamp": 1234567890,
            "step": "STEP4",
            "status": "RUNNING",
            "message": "游戏中",
            "gameAccountId": "game-xxx",
            ...其他字段
          }
        }
        """
        import time
        data = {
            'agentId': self.agent_id,
            'taskId': task_id,
            'timestamp': int(time.time() * 1000),
            'step': step,
            'status': status,
            'message': message
        }

        if game_account_id:
            data['gameAccountId'] = game_account_id

        data.update(kwargs)

        return await self.send("progress", data)

    async def listen(self):
        """
        开始监听WebSocket消息

        监听流程（v2.1优化）：
        1. 连接到WebSocket服务器
        2. 启动心跳任务
        3. 循环接收并处理消息
        4. 连接断开时自动重连

        注意：
        - 这是个阻塞方法，会一直运行直到_running=False
        """
        import websockets

        self._running = True

        if not await self.connect():
            self.logger.error("Failed to connect to WebSocket server")
            return

        await self._ensure_heartbeat_task()

        while self._running:
            async with self._connection_lock:
                if self._connection_state != ConnectionState.CONNECTED:
                    self.logger.debug("Not connected, stopping listen loop")
                    break
                ws = self._ws

            if not ws:
                break

            try:
                message = await ws.recv()
                await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                if self._running:
                    await self._schedule_reconnect()
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                if self._running:
                    await asyncio.sleep(1)

    async def _heartbeat_loop(self):
        """
        心跳循环

        功能说明：
        - 定期发送心跳消息
        - 保持WebSocket连接活跃
        - 防止连接因超时被关闭
        """
        while self._running:
            try:
                await asyncio.sleep(self._ws_heartbeat_interval)

                async with self._connection_lock:
                    if self._connection_state != ConnectionState.CONNECTED:
                        break
                    ws = self._ws

                if ws:
                    await self.send_heartbeat()
                    self._heartbeat_logger.debug("WebSocket heartbeat cycle ok")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._heartbeat_logger.error(f"WebSocket heartbeat error: {e}")
                self.logger.error(f"WebSocket heartbeat error: {e}")

    async def _handle_message(self, message: str):
        """
        处理接收到的WebSocket消息

        参数说明：
        - message: 原始消息字符串（JSON格式）

        处理流程：
        1. 解析JSON消息
        2. 提取消息类型和数据
        3. 调用对应的处理器

        特殊消息类型：
        - heartbeat_ack: 心跳确认，仅记录日志
        - connected: 连接成功通知
        - error: 服务器错误，记录日志
        """
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            msg_data = data.get('data', {})

            self.logger.debug(f"Received WebSocket message: {msg_type}")

            # 心跳确认
            if msg_type == 'heartbeat_ack':
                self._heartbeat_logger.debug("Heartbeat acknowledged")
                return

            # 连接成功
            if msg_type == 'connected':
                self.logger.info(f"WebSocket connected: {msg_data}")
                return

            # 错误消息
            if msg_type == 'error':
                self.logger.error(f"Server error: {msg_data}")
                return

            # 分发到注册的处理器（task / task_control 在 handler 内 create_task 放飞，此处 await 仅等入队）
            handler = self._message_handlers.get(msg_type)
            if handler:
                await handler(msg_data)
            else:
                self.logger.debug(f"No handler for message type: {msg_type}")

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
