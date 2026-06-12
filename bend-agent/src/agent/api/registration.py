"""
Bend Agent 注册码激活器。
处理注册码激活流程。
"""
import asyncio
import json
import os
import sys
from typing import Optional, Tuple
from dataclasses import dataclass

from ..core.config import config
from ..core.logger import get_logger
from ..core.machine_identity import machine_identity
from ..core.install_guard import assert_single_install
from ..core.paths import get_agent_root
from ..core.system_resource_detector import SystemResourceDetector


@dataclass
class AgentCredentials:
    """激活后的 Agent 凭证"""
    agent_id: str
    agent_secret: str
    merchant_id: str
    registration_code: str


@dataclass
class AgentSystemInfo:
    """
    注册用的 Agent 系统信息。
    仅包含不常变化的静态字段。
    """
    os_type: str
    os_version: str
    cpu_count: int
    max_concurrent_tasks: int

    def to_dict(self):
        """转换为 API 请求用的字典"""
        return {
            'osType': self.os_type,
            'osVersion': self.os_version,
            'cpuCount': self.cpu_count,
            'maxConcurrentTasks': self.max_concurrent_tasks
        }


class RegistrationActivator:
    """
    处理 Agent 注册码激活。
    管理凭证存储与校验。
    """

    def __init__(self):
        self.logger = get_logger('activation')
        self._config_dir = self._get_config_dir()
        os.makedirs(self._config_dir, exist_ok=True)
        self._credentials_file = os.path.join(self._config_dir, 'agent_credentials.json')
        self._credentials: Optional[AgentCredentials] = None

    def _get_config_dir(self) -> str:
        """
        根据运行环境确定配置目录。
        
        返回:
            凭证目录路径：
            - 开发环境：项目根目录 / credentials
            - 生产（PyInstaller 打包）：可执行文件目录 / credentials
            - 兜底：APPDATA / BendPlatform / Agent
        """
        # 是否 PyInstaller 打包运行
        if getattr(sys, 'frozen', False):
            # 打包可执行文件模式
            exe_dir = os.path.dirname(sys.executable)
            config_dir = os.path.join(exe_dir, 'credentials')
            self.logger.info(f"Running as frozen executable, using credentials directory: {config_dir}")
            return config_dir
        
        # 开发模式：从项目目录定位
        # 向上查找已知标记文件/目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 向上最多 5 层寻找项目根
        for _ in range(5):
            parent_dir = os.path.dirname(current_dir)
            # 检查项目标记
            if os.path.exists(os.path.join(parent_dir, 'configs', 'agent.yaml')):
                config_dir = os.path.join(parent_dir, 'credentials')
                self.logger.info(f"Running in development mode, using credentials directory: {config_dir}")
                return config_dir
            current_dir = parent_dir
        
        # 兜底：APPDATA 目录（原行为）
        fallback_dir = os.path.join(os.environ.get('APPDATA', ''), 'BendPlatform', 'Agent')
        self.logger.info(f"Using fallback credentials directory: {fallback_dir}")
        return fallback_dir

    @classmethod
    def get_system_info(cls) -> AgentSystemInfo:
        """
        获取注册用系统信息。
        
        返回:
            含静态系统信息的 AgentSystemInfo
        """
        detector = SystemResourceDetector()
        info = detector.get_system_info()
        
        max_concurrent = detector.recommend_concurrent_tasks(50)

        return AgentSystemInfo(
            os_type=info['platform'],
            os_version=info['platform_version'],
            cpu_count=info['cpu_count'],
            max_concurrent_tasks=max_concurrent
        )

    async def activate(self, registration_code: str) -> AgentCredentials:
        """
        使用注册码激活 Agent。

        参数:
            registration_code: 商户提供的注册码

        返回:
            含 agent_id、agent_secret、merchant_id 的 AgentCredentials

        抛出:
            激活失败时抛出 Exception
        """
        self.logger.info("Starting Agent activation with registration code...")

        assert_single_install()

        agent_id = self._get_or_generate_agent_id()
        agent_secret = self._generate_agent_secret()
        
        system_info = self.get_system_info()
        self.logger.info(f"System info for registration: {system_info.to_dict()}")

        try:
            result = await self._send_activation_request(
                registration_code,
                agent_id,
                agent_secret,
                system_info
            )

            if result['success']:
                self._credentials = AgentCredentials(
                    agent_id=agent_id,
                    agent_secret=agent_secret,
                    merchant_id=result['merchantId'],
                    registration_code=registration_code
                )
                self._save_credentials()
                machine_identity.mark_installed(str(get_agent_root()))
                self.logger.info(f"Agent activated successfully, Merchant ID: {result['merchantId']}")
                return self._credentials
            else:
                raise Exception(result.get('message', 'Activation failed'))

        except Exception as e:
            self.logger.error(f"Activation failed: {e}")
            raise

    async def _send_activation_request(
        self,
        code: str,
        agent_id: str,
        agent_secret: str,
        system_info: AgentSystemInfo
    ) -> dict:
        """向后端发送激活请求"""
        import aiohttp

        base_url = config.backend_url
        url = f"{base_url}/api/registration-codes/activate"

        payload = {
            'code': code,
            'agentId': agent_id,
            'agentSecret': agent_secret,
            'systemInfo': system_info.to_dict()
        }

        self.logger.info(f"Sending activation request to {url}")
        self.logger.debug(f"Activation payload: {json.dumps(payload, indent=2)}")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()

                if response.status == 200 and result.get('code') == 200:
                    data = result.get('data', {})
                    return {
                        'success': True,
                        'merchantId': data.get('merchantId')
                    }
                else:
                    return {
                        'success': False,
                        'message': result.get('message', 'Unknown error')
                    }

    def _get_or_generate_agent_id(self) -> str:
        """
        基于机器标识获取或生成持久 Agent ID。
        Agent ID 源自机器唯一标识，换路径重装后仍保持一致。
        """
        existing = self._load_existing_agent_id()
        if existing:
            self.logger.info(f"Using existing agent ID: {existing}")
            return existing

        new_id = machine_identity.get_machine_id()
        self._save_agent_id(new_id)
        return new_id

    def _load_existing_agent_id(self) -> Optional[str]:
        """从凭证文件加载已有 Agent ID"""
        if os.path.exists(self._credentials_file):
            try:
                with open(self._credentials_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('agentId')
            except Exception:
                pass
        return None

    def _save_agent_id(self, agent_id: str):
        """保存 Agent ID 供后续使用"""
        try:
            data = {}
            if os.path.exists(self._credentials_file):
                with open(self._credentials_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['agentId'] = agent_id
            with open(self._credentials_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save agent ID: {e}")

    def _generate_agent_secret(self) -> str:
        """生成 Agent 密钥"""
        import secrets
        return secrets.token_hex(32)

    def _save_credentials(self):
        """将凭证保存到文件"""
        if self._credentials is None:
            return

        credentials_data = {
            'agentId': self._credentials.agent_id,
            'agentSecret': self._credentials.agent_secret,
            'merchantId': self._credentials.merchant_id,
            'registrationCode': self._credentials.registration_code
        }

        with open(self._credentials_file, 'w', encoding='utf-8') as f:
            json.dump(credentials_data, f, indent=2)

        self.logger.info(f"Credentials saved to {self._credentials_file}")

    def load_credentials(self) -> Optional[AgentCredentials]:
        """从文件加载凭证"""
        if not os.path.exists(self._credentials_file):
            return None

        try:
            with open(self._credentials_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._credentials = AgentCredentials(
                agent_id=data['agentId'],
                agent_secret=data['agentSecret'],
                merchant_id=data['merchantId'],
                registration_code=data.get('registrationCode', '')
            )
            self.logger.info(f"Loaded credentials for Agent: {self._credentials.agent_id}")
            return self._credentials

        except Exception as e:
            self.logger.error(f"Failed to load credentials: {e}")
            return None

    def get_credentials(self) -> Optional[AgentCredentials]:
        """获取当前凭证"""
        if self._credentials is None:
            self._credentials = self.load_credentials()
        return self._credentials

    def has_credentials(self) -> bool:
        """检查凭证是否存在"""
        return self.get_credentials() is not None

    def clear_credentials(self):
        """清除已存储凭证"""
        self._credentials = None
        if os.path.exists(self._credentials_file):
            os.remove(self._credentials_file)
            self.logger.info("Credentials cleared")
