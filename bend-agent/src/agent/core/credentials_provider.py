"""
凭证管理器
==========

功能说明：
- 集中管理 Agent 凭证（agentId 和 agentSecret）
- 从 agent_credentials.json 文件加载凭证
- 提供凭证给所有需要回调平台的模块使用

使用方式：
- 在应用启动时初始化一次
- 通过 get_credentials() 获取凭证
- 回调平台接口时自动带上凭证

作者：技术团队
版本：1.0
"""

import os
import sys
import json
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from ..core.config import config


@dataclass
class AgentCredentials:
    """Agent凭证数据类"""
    agent_id: str
    agent_secret: str
    merchant_id: str
    registration_code: str


class CredentialsProvider:
    """
    凭证管理器
    
    职责：
    - 从配置文件加载 Agent 凭证
    - 提供凭证给所有需要认证的模块
    - 确保凭证只加载一次，全局共享
    
    单例模式：整个应用只存在一个实例
    """
    
    _instance: Optional['CredentialsProvider'] = None
    _credentials: Optional[AgentCredentials] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger('credentials')
        self._config_dir = self._get_config_dir()
        self._credentials_file = os.path.join(self._config_dir, 'agent_credentials.json')
        self._load_credentials()
    
    def _get_config_dir(self) -> str:
        """
        获取配置目录
        
        优先级：
        1. 打包后的可执行文件目录下的 credentials 文件夹
        2. 开发环境下项目根目录下的 credentials 文件夹
        3. APPDATA/BendPlatform/Agent
        """
        # 是否 PyInstaller 打包运行
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            config_dir = os.path.join(exe_dir, 'credentials')
            self.logger.info(f"Running as frozen executable, using credentials directory: {config_dir}")
            return config_dir
        
        # 开发模式：从项目目录定位
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            parent_dir = os.path.dirname(current_dir)
            if os.path.exists(os.path.join(parent_dir, 'configs', 'agent.yaml')):
                config_dir = os.path.join(parent_dir, 'credentials')
                self.logger.info(f"Running in development mode, using credentials directory: {config_dir}")
                return config_dir
            current_dir = parent_dir
        
        # 兜底：APPDATA 目录
        fallback_dir = os.path.join(os.environ.get('APPDATA', ''), 'BendPlatform', 'Agent')
        self.logger.info(f"Using fallback credentials directory: {fallback_dir}")
        return fallback_dir
    
    def _load_credentials(self):
        """从文件加载凭证"""
        try:
            if not os.path.exists(self._credentials_file):
                self.logger.warning(f"凭证文件不存在: {self._credentials_file}")
                return
            
            with open(self._credentials_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._credentials = AgentCredentials(
                agent_id=data.get('agentId', ''),
                agent_secret=data.get('agentSecret', ''),
                merchant_id=data.get('merchantId', ''),
                registration_code=data.get('registrationCode', '')
            )
            
            if self._credentials.agent_id and self._credentials.agent_secret:
                self.logger.info(f"凭证加载成功: agentId={self._credentials.agent_id}")
            else:
                self.logger.warning("凭证文件内容不完整，缺少agentId或agentSecret")
                
        except Exception as e:
            self.logger.error(f"加载凭证失败: {e}")
            self._credentials = None
    
    def get_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取 Agent 凭证（每次都从文件读取，不使用缓存）

        返回：
        - Tuple[str, str]: (agent_id, agent_secret)
        - 如果文件不存在或内容无效则返回 (None, None)
        """
        # 每次都重新从文件读取，不使用缓存
        credentials = self._read_credentials_from_file()
        if credentials:
            self.logger.debug(f"返回凭证: agentId={credentials.agent_id}")
            return credentials.agent_id, credentials.agent_secret
        self.logger.warning("凭证文件不存在或内容无效，返回 (None, None)")
        return None, None
    
    def _read_credentials_from_file(self) -> Optional[AgentCredentials]:
        """
        从文件读取凭证（不缓存，每次调用都读取）
        
        返回：
        - AgentCredentials: 凭证对象
        - None: 读取失败
        """
        try:
            if not os.path.exists(self._credentials_file):
                self.logger.debug(f"凭证文件不存在: {self._credentials_file}")
                return None
            
            with open(self._credentials_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            agent_id = data.get('agentId', '')
            agent_secret = data.get('agentSecret', '')
            merchant_id = data.get('merchantId', '')
            registration_code = data.get('registrationCode', '')
            
            if agent_id and agent_secret:
                return AgentCredentials(
                    agent_id=agent_id,
                    agent_secret=agent_secret,
                    merchant_id=merchant_id,
                    registration_code=registration_code
                )
            else:
                self.logger.debug("凭证文件内容不完整，缺少agentId或agentSecret")
                return None
                
        except Exception as e:
            self.logger.error(f"读取凭证文件失败: {e}")
            return None
    
    @property
    def agent_id(self) -> Optional[str]:
        """获取 Agent ID"""
        if self._credentials:
            return self._credentials.agent_id
        return None
    
    @property
    def agent_secret(self) -> Optional[str]:
        """获取 Agent Secret"""
        if self._credentials:
            return self._credentials.agent_secret
        return None
    
    @property
    def merchant_id(self) -> Optional[str]:
        """获取商户 ID"""
        if self._credentials:
            return self._credentials.merchant_id
        return None
    
    @property
    def registration_code(self) -> Optional[str]:
        """获取注册码"""
        if self._credentials:
            return self._credentials.registration_code
        return None
    
    def reload(self):
        """重新加载凭证"""
        self._load_credentials()


# 全局单例
_provider: Optional[CredentialsProvider] = None


def get_credentials_provider() -> CredentialsProvider:
    """
    获取凭证管理器单例
    
    返回：
    - CredentialsProvider 实例
    """
    global _provider
    if _provider is None:
        _provider = CredentialsProvider()
    return _provider


def get_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    快速获取凭证的便捷函数
    
    返回：
    - Tuple[str, str]: (agent_id, agent_secret)
    """
    return get_credentials_provider().get_credentials()