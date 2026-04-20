"""
API client for Bend Agent to communicate with backend server

功能说明：
- 封装所有与后端服务器的HTTP通信
- 支持注册、心跳、状态上报、任务完成等API
- 使用aiohttp实现异步HTTP请求
- 自动管理会话和请求头

主要API接口：
- register: Agent注册
- heartbeat: 心跳检测
- report_status: 状态上报
- complete_task / fail_task: 任务结果反馈
- check_update: 版本更新检查
"""
import asyncio
import aiohttp
import json
import hashlib
import os
from typing import Optional, Dict, Any, Callable
from enum import Enum

from ..core.config import config
from ..core.logger import get_logger


class UpdateStatus(Enum):
    """
    版本更新状态枚举

    状态说明：
    - COMPATIBLE: 当前版本兼容，无需更新
    - UPDATE_OPTIONAL: 有可选更新
    - UPDATE_REQUIRED: 必须更新才能继续使用
    - DOWNLOADING: 正在下载更新
    - INSTALLING: 正在安装更新
    - FAILED: 更新失败
    """
    COMPATIBLE = "compatible"           # 版本兼容
    UPDATE_OPTIONAL = "update_optional"  # 可选更新
    UPDATE_REQUIRED = "update_required"  # 必须更新
    DOWNLOADING = "downloading"         # 下载中
    INSTALLING = "installing"           # 安装中
    FAILED = "failed"                   # 更新失败


class ApiClient:
    """
    HTTP API客户端

    功能说明：
    - 与后端服务器进行HTTP通信
    - 管理Agent的注册、心跳、状态上报
    - 处理任务结果反馈
    - 支持文件下载和版本更新

    使用方式：
    - 创建实例后调用 connect() 初始化会话
    - 使用完成后调用 close() 关闭会话
    """

    def __init__(self, agent_id: str, agent_secret: str):
        """
        初始化API客户端

        参数说明：
        - agent_id: Agent唯一标识符
        - agent_secret: Agent密钥，用于身份验证

        初始化内容：
        - 设置基础URL和API前缀
        - 配置请求头（包含Agent标识和密钥）
        - 初始化状态变量
        """
        self.agent_id = agent_id                      # Agent唯一标识符
        self.agent_secret = agent_secret              # Agent密钥
        self.base_url = config.backend_url            # 后端服务器地址
        self.api_prefix = config.get('backend.api_prefix', '/api')  # API前缀
        self._session: Optional[aiohttp.ClientSession] = None     # HTTP会话
        self._headers = {                              # 请求头
            'Content-Type': 'application/json',       # JSON内容类型
            'X-Agent-ID': agent_id,                   # Agent标识
            'X-Agent-Secret': agent_secret            # Agent密钥
        }
        self.logger = get_logger('api')                # 日志记录器
        self._current_status = 'online'               # 当前状态
        self._current_task_id = None                  # 当前任务ID
        self._current_streaming_id = None             # 当前流媒体账号ID
        self._current_version = config.get('agent.version', '1.0.0')  # 当前版本

    async def connect(self):
        """
        连接到后端服务器

        功能说明：
        - 创建aiohttp ClientSession
        - 配置请求头
        - 建立HTTP连接池

        调用时机：
        - 在Agent启动时调用
        - 如果会话已存在则跳过
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        self.logger.info(f"API client connected to {self.base_url}")

    async def close(self):
        """
        关闭HTTP会话

        功能说明：
        - 关闭aiohttp ClientSession
        - 释放连接池资源

        调用时机：
        - 在Agent停止时调用
        """
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.info("API client disconnected")

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        发送HTTP请求（内部方法）

        参数说明：
        - method: HTTP方法（GET、POST、PUT、DELETE）
        - path: API路径
        - data: 请求体数据（POST/PUT用）
        - params: URL查询参数

        返回值：
        - 响应JSON数据的字典

        异常处理：
        - HTTP状态码>=400视为错误
        - 网络错误会抛出aiohttp.ClientError
        """
        if self._session is None or self._session.closed:
            await self.connect()

        url = f"{self.base_url}{self.api_prefix}{path}"
        try:
            async with self._session.request(
                method, url, json=data, params=params
            ) as response:
                result = await response.json()
                if response.status >= 400:
                    self.logger.error(f"API error: {response.status} - {result}")
                    raise Exception(f"API error: {response.status}")
                return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Request failed: {e}")
            raise

    async def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送GET请求

        参数说明：
        - path: API路径
        - params: URL查询参数

        返回值：响应JSON数据的字典
        """
        return await self._request('GET', path, params=params)

    async def post(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送POST请求

        参数说明：
        - path: API路径
        - data: 请求体数据

        返回值：响应JSON数据的字典
        """
        return await self._request('POST', path, data=data)

    async def put(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送PUT请求

        参数说明：
        - path: API路径
        - data: 请求体数据

        返回值：响应JSON数据的字典
        """
        return await self._request('PUT', path, data=data)

    async def delete(self, path: str) -> Dict[str, Any]:
        """
        发送DELETE请求

        参数说明：
        - path: API路径

        返回值：响应JSON数据的字典
        """
        return await self._request('DELETE', path)

    async def register(self, registration_code: str, host: str, port: int, version: str = None) -> Dict[str, Any]:
        """
        向后端注册Agent

        参数说明：
        - registration_code: 注册码（从平台获取）
        - host: Agent所在主机IP
        - port: Agent监听端口
        - version: Agent版本号

        返回值：
        - 注册结果字典，包含code字段表示成功与否

        流程说明：
        1. 构建注册请求数据
        2. 发送到 /agents/register
        3. 返回注册结果
        """
        self._current_version = version or self._current_version
        data = {
            'registrationCode': registration_code,
            'host': host,
            'port': port
        }
        if self._current_version:
            data['version'] = self._current_version
        return await self.post('/agents/register', data)

    async def heartbeat(self, status: str = None, current_task_id: str = None, current_streaming_id: str = None, version: str = None, running_task_count: int = None, xbox_session_count: int = None) -> Dict[str, Any]:
        """
        发送心跳到后端

        参数说明：
        - status: Agent当前状态
        - current_task_id: 当前执行的任务ID
        - current_streaming_id: 当前流媒体账号ID
        - version: 当前版本号
        - running_task_count: 运行中的任务数
        - xbox_session_count: 当前Xbox会话数

        返回值：
        - 后端响应数据

        心跳内容：
        - 证明Agent仍然在线
        - 报告当前工作状态和负载情况
        """
        if status:
            self._current_status = status
        if current_task_id:
            self._current_task_id = current_task_id
        if current_streaming_id:
            self._current_streaming_id = current_streaming_id
        if version:
            self._current_version = version

        data = {}
        if self._current_status:
            data['status'] = self._current_status
        if self._current_task_id:
            data['currentTaskId'] = self._current_task_id
        if self._current_streaming_id:
            data['currentStreamingId'] = self._current_streaming_id
        if self._current_version:
            data['version'] = self._current_version
        if running_task_count is not None:
            data['runningTaskCount'] = running_task_count
        if xbox_session_count is not None:
            data['xboxSessionCount'] = xbox_session_count

        return await self.post('/agents/heartbeat', data)

    async def report_status(self, status: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        向后端上报Agent状态

        参数说明：
        - status: 状态字符串
        - metadata: 附加元数据

        返回值：后端响应数据
        """
        self._current_status = status
        return await self.post('/agents/status', {
            'status': status,
            'metadata': metadata or {}
        })

    async def uninstall(self, reason: str = None, clear_registry: bool = False) -> Dict[str, Any]:
        """
        通知后端Agent即将卸载

        参数说明：
        - reason: 卸载原因
        - clear_registry: 是否清除机器注册表（会导致需要重新注册）

        返回值：
        - 包含needReregister标志的响应数据

        注意：
        - 清除注册表后，Agent需要重新注册才能使用
        """
        data = {}
        if reason:
            data['reason'] = reason
        if clear_registry:
            data['clearRegistry'] = 'true'
        return await self.post('/agents/uninstall', data)

    async def offline(self) -> Dict[str, Any]:
        """
        通知后端Agent即将离线

        返回值：后端响应数据

        使用场景：
        - Agent正常关闭时调用
        - 让后端及时更新Agent状态
        """
        return await self.post('/agents/offline')

    async def check_update(self, current_version: str) -> Dict[str, Any]:
        """
        检查是否有可用更新

        参数说明：
        - current_version: 当前版本号

        返回值：
        - 包含更新信息的字典
        - code=-1表示检查失败
        """
        try:
            result = await self.get('/agents/version/check', {'currentVersion': current_version})
            return result
        except Exception as e:
            self.logger.error(f"Failed to check update: {e}")
            return {'code': -1, 'message': str(e)}

    async def get_download_info(self, version: str) -> Dict[str, Any]:
        """
        获取指定版本的下载信息

        参数说明：
        - version: 版本号

        返回值：
        - 包含下载URL、MD5等信息的字典
        """
        try:
            result = await self.get(f'/agents/version/download/{version}')
            return result
        except Exception as e:
            self.logger.error(f"Failed to get download info: {e}")
            return {'code': -1, 'message': str(e)}

    async def download_file(self, url: str, dest_path: str, md5_expected: str = None,
                           progress_callback: Optional[Callable] = None) -> bool:
        """
        下载文件（支持进度回调）

        参数说明：
        - url: 下载URL
        - dest_path: 保存路径
        - md5_expected: 期望的MD5值（用于校验）
        - progress_callback: 进度回调函数，参数为百分比(0-100)

        返回值：
        - True: 下载并校验成功
        - False: 下载或校验失败

        实现说明：
        - 分块下载避免内存占用过大
        - 支持MD5校验确保文件完整性
        - 校验失败会删除已下载文件
        """
        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"Download failed: HTTP {response.status}")
                    return False

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                hash_md5 = hashlib.md5()

                with open(dest_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        hash_md5.update(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(progress)

                # MD5校验
                if md5_expected:
                    md5_actual = hash_md5.hexdigest()
                    if md5_actual != md5_expected:
                        self.logger.error(f"MD5 mismatch: expected {md5_expected}, got {md5_actual}")
                        os.remove(dest_path)
                        return False

                return True

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

    async def report_frame_result(
        self,
        task_id: str,
        frame_id: str,
        matched: bool,
        location: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        上报模板匹配结果

        参数说明：
        - task_id: 任务ID
        - frame_id: 帧ID
        - matched: 是否匹配成功
        - location: 匹配位置坐标

        返回值：后端响应数据
        """
        return await self.post('/tasks/frame-result', {
            'taskId': task_id,
            'frameId': frame_id,
            'matched': matched,
            'location': location
        })

    async def get_task(self) -> Optional[Dict[str, Any]]:
        """
        获取待处理的任务

        返回值：
        - 任务数据字典
        - None: 没有待处理任务

        注意：
        - 由后端主动通过WebSocket下发，此方法较少使用
        """
        try:
            result = await self.get('/agents/tasks/pending')
            if result.get('code') == 0 and result.get('data'):
                return result['data']
            return None
        except Exception as e:
            self.logger.debug(f"No pending task: {e}")
            return None

    async def complete_task(self, task_id: str, result: Dict) -> Dict[str, Any]:
        """
        标记任务为已完成

        参数说明：
        - task_id: 任务ID
        - result: 任务执行结果

        返回值：后端响应数据
        """
        return await self.post(f'/tasks/{task_id}/complete', result)

    async def fail_task(self, task_id: str, error: str) -> Dict[str, Any]:
        """
        标记任务为失败

        参数说明：
        - task_id: 任务ID
        - error: 错误信息

        返回值：后端响应数据
        """
        return await self.post(f'/tasks/{task_id}/fail', {'error': error})
