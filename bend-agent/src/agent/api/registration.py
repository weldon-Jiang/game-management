"""
Registration Code Activator for Bend Agent
Handles the registration code activation flow
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
from ..core.system_resource_detector import SystemResourceDetector


@dataclass
class AgentCredentials:
    """Agent credentials after activation"""
    agent_id: str
    agent_secret: str
    merchant_id: str
    registration_code: str


@dataclass
class AgentSystemInfo:
    """
    Agent system information for registration
    Only includes static fields that don't change frequently
    """
    os_type: str
    os_version: str
    cpu_count: int
    max_concurrent_tasks: int

    def to_dict(self):
        """Convert to dictionary for API request"""
        return {
            'osType': self.os_type,
            'osVersion': self.os_version,
            'cpuCount': self.cpu_count,
            'maxConcurrentTasks': self.max_concurrent_tasks
        }


class RegistrationActivator:
    """
    Handles Agent registration code activation
    Manages credentials storage and validation
    """

    def __init__(self):
        self.logger = get_logger('activation')
        self._config_dir = self._get_config_dir()
        os.makedirs(self._config_dir, exist_ok=True)
        self._credentials_file = os.path.join(self._config_dir, 'agent_credentials.json')
        self._credentials: Optional[AgentCredentials] = None

    def _get_config_dir(self) -> str:
        """
        Determine the appropriate configuration directory based on runtime environment.
        
        Returns:
            Path to the credentials directory:
            - Development: Project root / credentials
            - Production (frozen): Executable directory / credentials
            - Fallback: APPDATA / BendPlatform / Agent
        """
        # Check if running from a frozen executable (PyInstaller)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            exe_dir = os.path.dirname(sys.executable)
            config_dir = os.path.join(exe_dir, 'credentials')
            self.logger.info(f"Running as frozen executable, using credentials directory: {config_dir}")
            return config_dir
        
        # Check if running from project directory (development)
        # Try to find the project root by looking for known files/directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up several levels to find the project root
        for _ in range(5):
            parent_dir = os.path.dirname(current_dir)
            # Check for project markers
            if os.path.exists(os.path.join(parent_dir, 'configs', 'agent.yaml')):
                config_dir = os.path.join(parent_dir, 'credentials')
                self.logger.info(f"Running in development mode, using credentials directory: {config_dir}")
                return config_dir
            current_dir = parent_dir
        
        # Fallback to APPDATA directory (original behavior)
        fallback_dir = os.path.join(os.environ.get('APPDATA', ''), 'BendPlatform', 'Agent')
        self.logger.info(f"Using fallback credentials directory: {fallback_dir}")
        return fallback_dir

    @classmethod
    def get_system_info(cls) -> AgentSystemInfo:
        """
        Get system information for registration
        
        Returns:
            AgentSystemInfo containing static system details
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
        Activate Agent using registration code

        Args:
            registration_code: The registration code provided by merchant

        Returns:
            AgentCredentials containing agent_id, agent_secret, merchant_id

        Raises:
            Exception if activation fails
        """
        self.logger.info("Starting Agent activation with registration code...")

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
        """Send activation request to backend"""
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
        Get or generate a persistent agent ID based on machine identity.
        The agent ID is derived from the machine's unique identifier,
        ensuring the same ID is generated even after reinstalling in different paths.
        """
        existing = self._load_existing_agent_id()
        if existing:
            self.logger.info(f"Using existing agent ID: {existing}")
            return existing

        new_id = machine_identity.get_machine_id()
        self._save_agent_id(new_id)
        return new_id

    def _load_existing_agent_id(self) -> Optional[str]:
        """Load existing agent ID from credentials file"""
        if os.path.exists(self._credentials_file):
            try:
                with open(self._credentials_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('agentId')
            except Exception:
                pass
        return None

    def _save_agent_id(self, agent_id: str):
        """Save agent ID for future use"""
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
        """Generate agent secret key"""
        import secrets
        return secrets.token_hex(32)

    def _save_credentials(self):
        """Save credentials to file"""
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
        """Load credentials from file"""
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
        """Get current credentials"""
        if self._credentials is None:
            self._credentials = self.load_credentials()
        return self._credentials

    def has_credentials(self) -> bool:
        """Check if credentials exist"""
        return self.get_credentials() is not None

    def clear_credentials(self):
        """Clear stored credentials"""
        self._credentials = None
        if os.path.exists(self._credentials_file):
            os.remove(self._credentials_file)
            self.logger.info("Credentials cleared")
