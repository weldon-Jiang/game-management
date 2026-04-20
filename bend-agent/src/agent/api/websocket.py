"""
WebSocket client for real-time communication with backend

功能说明：
- 建立与后端服务器的WebSocket长连接
- 支持实时双向消息通信
- 自动重连机制（指数退避策略）
- 心跳保活机制
- 消息分发到注册的处理器

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


class WSMessageType(Enum):
    """
    WebSocket消息类型枚举

    消息类型说明：
    - TASK: 后端下发的自动化任务
    - COMMAND: 后端发送的控制命令
    - VIDEO_STREAM: 视频流数据传输
    - HEARTBEAT: 心跳保活消息
    - HEARTBEAT_ACK: 心跳确认响应
    - STATUS_REPORT: 状态上报
    - XBOX_DISCOVERED: 发现新Xbox设备
    - TASK_RESULT: 任务执行结果
    - CONNECTED: 连接成功通知
    - DISCONNECT: 断开连接通知
    - ACK: 通用确认消息
    - ERROR: 错误消息
    """
    TASK = "task"                     # 任务消息
    COMMAND = "command"               # 命令消息
    VIDEO_STREAM = "video_stream"     # 视频流
    HEARTBEAT = "heartbeat"           # 心跳
    HEARTBEAT_ACK = "heartbeat_ack"   # 心跳确认
    STATUS_REPORT = "status_report"   # 状态上报
    XBOX_DISCOVERED = "xbox_discovered"  # Xbox发现
    TASK_RESULT = "task_result"       # 任务结果
    CONNECTED = "connected"           # 已连接
    DISCONNECT = "disconnect"         # 断开连接
    ACK = "ack"                       # 确认
    ERROR = "error"                   # 错误


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
        - ws://host:port/{agent_id}?agentSecret={secret}
        """
        import websockets

        url = f"{self.ws_url}/{self.agent_id}?agentSecret={self.agent_secret}"
        try:
            self._ws = await websockets.connect(url, ping_interval=None)
            self._running = True
            self.logger.info(f"WebSocket connecting to {url}")
            return True
        except Exception as e:
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
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        self.logger.info("WebSocket disconnected")

    async def reconnect(self):
        """
        重新连接（指数退避策略）

        重连策略：
        - 最多重连_max_attempts次
        - 每次失败后延迟 = 重连延迟 * min(尝试次数, 5)
        - 连接成功后启动心跳任务
        """
        import websockets

        attempt = 0
        while self._running and attempt < self._max_attempts:
            attempt += 1
            self.logger.info(f"WebSocket reconnecting... attempt {attempt}/{self._max_attempts}")
            if await self.connect():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                return True
            await asyncio.sleep(self._reconnect_delay * min(attempt, 5))
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
        if not self._ws or not self._running:
            self.logger.warning("WebSocket not connected")
            return False

        try:
            message = json.dumps({
                'type': message_type,
                'data': data
            }, ensure_ascii=False)
            await self._ws.send(message)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False

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

    async def listen(self):
        """
        开始监听WebSocket消息

        监听流程：
        1. 连接到WebSocket服务器
        2. 启动心跳任务
        3. 循环接收并处理消息
        4. 连接断开时自动重连

        注意：
        - 这是个阻塞方法，会一直运行直到_running=False
        """
        import websockets

        if not await self.connect():
            self.logger.error("Failed to connect to WebSocket server")
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        while self._running:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                if self._running:
                    await self.reconnect()
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
                if self._running and self._ws:
                    await self.send_heartbeat()
                    self.logger.debug("WebSocket heartbeat sent")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")

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
                self.logger.debug("Heartbeat acknowledged")
                return

            # 连接成功
            if msg_type == 'connected':
                self.logger.info(f"WebSocket connected: {msg_data}")
                return

            # 错误消息
            if msg_type == 'error':
                self.logger.error(f"Server error: {msg_data}")
                return

            # 分发到注册的处理器
            handler = self._message_handlers.get(msg_type)
            if handler:
                await handler(msg_data)
            else:
                self.logger.debug(f"No handler for message type: {msg_type}")

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
