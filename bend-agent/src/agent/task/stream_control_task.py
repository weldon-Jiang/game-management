"""
Stream Control Task Handler
===========================

功能说明：
- 处理流媒体自动化任务
- 多线程并发执行多个流媒体账号
- 微软账号登录 -> Xbox 绑定 -> 任务执行

流程：
1. 解析任务参数（流媒体账号、游戏账号）
2. 多线程并发处理：
   a. 登录模块：微软账号认证
   b. 串流模块：Xbox 绑定
3. 返回执行结果

作者：技术团队
版本：1.0
"""

import asyncio
import json
import traceback
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..core.logger import get_logger
from ..core.config import config
from ..auth.microsoft_auth import (
    MicrosoftAuthenticator,
    AuthenticationResult,
    AuthStatus
)
from ..utils.crypto_util import decrypt_password, get_aes_key


@dataclass
class StreamingAccountTask:
    """
    流媒体账号任务

    属性：
    - streaming_account_id: 流媒体账号ID
    - email: 微软账号邮箱
    - encrypted_password: 加密的密码
    - game_accounts: 关联的游戏账号列表
    - xbox_info: Xbox 主机信息（可选）
    - task_id: 对应的任务ID
    """
    streaming_account_id: str
    email: str
    encrypted_password: str
    game_accounts: List[Dict[str, Any]] = field(default_factory=list)
    xbox_info: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None


@dataclass
class StreamingTaskResult:
    """
    流媒体账号任务结果

    属性：
    - streaming_account_id: 流媒体账号ID
    - success: 是否成功
    - message: 结果消息
    - microsoft_auth: 微软认证结果
    - xbox_bound: Xbox绑定是否成功
    - error_code: 错误代码
    """
    streaming_account_id: str
    success: bool
    message: str
    microsoft_auth: Optional[AuthenticationResult] = None
    xbox_bound: bool = False
    xbox_host: Optional[str] = None
    error_code: Optional[str] = None
    error_details: Optional[str] = None


class StreamControlTaskHandler:
    """
    流控制任务处理器

    功能：
    - 多线程并发处理多个流媒体账号
    - 每个账号独立执行：登录 -> Xbox绑定
    - 失败时返回详细错误信息

    使用示例：
        handler = StreamControlTaskHandler()
        results = await handler.handle_batch_tasks(task_params)
    """

    def __init__(self, max_workers: int = 10):
        """
        初始化处理器

        Args:
            max_workers: 最大并发线程数
        """
        self.logger = get_logger('stream_control_task')
        self._max_workers = max_workers
        self._aes_key = get_aes_key()

        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def handle_batch_tasks(
        self,
        params: Dict[str, Any],
        check_cancel: Callable[[], bool]
    ) -> Dict[str, Any]:
        """
        处理批量流控制任务（多线程）

        Args:
            params: 任务参数字典
                - streamingAccount: 流媒体账号信息
                - gameAccounts: 游戏账号列表
            check_cancel: 取消检查函数

        Returns:
            执行结果字典
        """
        # 解析参数
        streaming_account = params.get('streamingAccount', {})
        game_accounts = params.get('gameAccounts', [])

        if not streaming_account:
            return {
                'success': False,
                'message': '缺少流媒体账号信息',
                'results': []
            }

        # 构建流媒体账号任务
        task = StreamingAccountTask(
            streaming_account_id=streaming_account.get('id'),
            email=streaming_account.get('email'),
            encrypted_password=streaming_account.get('passwordToken', ''),
            game_accounts=game_accounts,
            xbox_info=self._extract_xbox_info(streaming_account),
            task_id=params.get('taskId')
        )

        self.logger.info(
            f"开始处理流媒体账号: {task.email}, "
            f"游戏账号数: {len(task.game_accounts)}"
        )

        # 在线程池中执行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self._execute_streaming_task(task, check_cancel)
            )
        finally:
            loop.close()

        return self._build_response(result)

    async def _execute_streaming_task(
        self,
        task: StreamingAccountTask,
        check_cancel: Callable[[], bool]
    ) -> StreamingTaskResult:
        """
        执行单个流媒体账号任务

        流程：
        1. 检查取消
        2. 解密密码
        3. 微软账号登录
        4. Xbox 绑定

        Args:
            task: 流媒体账号任务
            check_cancel: 取消检查函数

        Returns:
            执行结果
        """
        result = StreamingTaskResult(
            streaming_account_id=task.streaming_account_id,
            success=False,
            message="任务未开始"
        )

        try:
            # Step 1: 检查取消
            if check_cancel():
                result.message = "任务被取消"
                result.error_code = "CANCELLED"
                return result

            # Step 2: 解密密码
            password = self._decrypt_password(task.encrypted_password)
            if not password:
                result.message = "密码解密失败"
                result.error_code = "PASSWORD_DECRYPT_ERROR"
                return result

            self.logger.info(f"开始微软登录: {task.email}")

            # Step 3: 微软账号登录
            auth = MicrosoftAuthenticator()
            auth_result = await auth.login_with_credentials(
                email=task.email,
                password=password,
                encrypted_password=None,  # 已解密
                aes_key=None
            )

            if not auth_result.success:
                result.message = f"微软登录失败: {auth_result.message}"
                result.error_code = "MICROSOFT_AUTH_FAILED"
                result.error_details = auth_result.error_details
                result.microsoft_auth = auth_result
                return result

            result.microsoft_auth = auth_result
            self.logger.info(f"微软登录成功: {task.email}")

            # Step 4: Xbox 绑定
            if task.xbox_info:
                xbox_ip = task.xbox_info.get('ip')
                if xbox_ip:
                    bound = await self._bind_xbox(auth, xbox_ip, task)
                    if bound:
                        result.xbox_bound = True
                        result.xbox_host = xbox_ip
                        self.logger.info(f"Xbox绑定成功: {xbox_ip}")
                    else:
                        result.message = f"Xbox绑定失败: {xbox_ip}"
                        result.error_code = "XBOX_BIND_FAILED"
                        return result

            # 全部成功
            result.success = True
            result.message = "自动化启动成功"

            return result

        except asyncio.CancelledError:
            result.message = "任务被取消"
            result.error_code = "CANCELLED"
            return result

        except Exception as e:
            result.message = f"执行异常: {str(e)}"
            result.error_code = "EXCEPTION"
            result.error_details = traceback.format_exc()
            self.logger.error(f"流媒体账号任务异常: {task.email}: {e}")
            return result

    async def _bind_xbox(
        self,
        auth: MicrosoftAuthenticator,
        xbox_ip: str,
        task: StreamingAccountTask
    ) -> bool:
        """
        绑定 Xbox 主机

        使用 Xbox Live Token 通过 SmartGlass 协议连接并绑定

        Args:
            auth: 微软认证器
            xbox_ip: Xbox IP 地址
            task: 流媒体账号任务

        Returns:
            True: 绑定成功
            False: 绑定失败
        """
        try:
            from ..xbox.stream_controller import XboxStreamController

            # 获取 Xbox Token
            if not auth.is_authenticated:
                self.logger.error("认证器未认证，无法绑定Xbox")
                return False

            xbox_token = auth.xbox_token
            user_hash = auth.user_hash

            if not xbox_token:
                self.logger.error("无Xbox Token，无法绑定")
                return False

            # 创建 SmartGlass 连接
            controller = XboxStreamController()
            connected = await controller.connect_with_token(
                xbox_ip,
                xbox_token,
                user_hash
            )

            if not connected:
                self.logger.error(f"Xbox连接失败: {xbox_ip}")
                return False

            # 执行 Xbox 绑定操作
            # 这里需要根据实际的绑定协议实现
            bound = await controller.bind_streaming_account(
                streaming_account_id=task.streaming_account_id,
                email=task.email
            )

            await controller.disconnect()
            return bound

        except Exception as e:
            self.logger.error(f"Xbox绑定异常: {xbox_ip}: {e}")
            return False

    def _decrypt_password(self, encrypted_password: str) -> Optional[str]:
        """
        解密密码

        Args:
            encrypted_password: 加密的密码

        Returns:
            明文密码或None
        """
        if not encrypted_password:
            return None

        try:
            # 如果是 token 格式，需要先换取实际密码
            if encrypted_password.startswith('token:'):
                # 需要调用平台API换取实际密码
                # 这里暂时返回 None，实际需要实现 token 交换
                self.logger.warning("需要实现token交换逻辑")
                return None

            # 直接解密
            return decrypt_password(encrypted_password)

        except Exception as e:
            self.logger.error(f"密码解密失败: {e}")
            return None

    def _extract_xbox_info(self, streaming_account: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从流媒体账号信息中提取 Xbox 信息

        Args:
            streaming_account: 流媒体账号信息

        Returns:
            Xbox 信息字典或 None
        """
        # 尝试从多个位置获取 Xbox 信息
        xbox_info = streaming_account.get('xboxInfo')
        if xbox_info:
            return xbox_info

        # 尝试从其他字段获取
        xbox_ip = streaming_account.get('xboxIp') or streaming_account.get('xbox_ip')
        if xbox_ip:
            return {'ip': xbox_ip, 'port': 5050}

        return None

    def _build_response(self, result: StreamingTaskResult) -> Dict[str, Any]:
        """
        构建响应结果

        Args:
            result: 任务执行结果

        Returns:
            响应字典
        """
        response = {
            'success': result.success,
            'streamingAccountId': result.streaming_account_id,
            'message': result.message,
            'xboxBound': result.xbox_bound
        }

        if result.error_code:
            response['errorCode'] = result.error_code

        if result.error_details and self.logger.level <= 10:  # DEBUG
            response['errorDetails'] = result.error_details

        return response

    async def handle_single_account(
        self,
        params: Dict[str, Any],
        check_cancel: Callable[[], bool]
    ) -> Dict[str, Any]:
        """
        处理单个流媒体账号（用于 WebSocket 实时反馈）

        Args:
            params: 任务参数
            check_cancel: 取消检查函数

        Returns:
            执行结果
        """
        return self.handle_batch_tasks(params, check_cancel)


def create_stream_control_handler(max_workers: int = 10) -> StreamControlTaskHandler:
    """
    创建流控制任务处理器工厂函数

    Args:
        max_workers: 最大并发数

    Returns:
        StreamControlTaskHandler 实例
    """
    return StreamControlTaskHandler(max_workers=max_workers)
