"""
Registration Code Activator for Bend Agent
Handles the registration code activation flow
"""
import asyncio
import json
import os
from typing import Optional, Tuple
from dataclasses import dataclass

from ..core.config import config
from ..core.logger import get_logger
from ..core.machine_identity import machine_identity


@dataclass
class AgentCredentials:
    """Agent credentials after activation"""
    agent_id: str
    agent_secret: str
    merchant_id: str


class RegistrationActivator:
    """
    Handles Agent registration code activation
    Manages credentials storage and validation
    """

    def __init__(self):
        self.logger = get_logger('activation')
        self._config_dir = os.path.join(os.environ.get('APPDATA', ''), 'BendPlatform', 'Agent')
        os.makedirs(self._config_dir, exist_ok=True)
        self._credentials_file = os.path.join(self._config_dir, 'agent_credentials.json')
        self._credentials: Optional[AgentCredentials] = None

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

        try:
            result = await self._send_activation_request(
                registration_code,
                agent_id,
                agent_secret
            )

            if result['success']:
                self._credentials = AgentCredentials(
                    agent_id=agent_id,
                    agent_secret=agent_secret,
                    merchant_id=result['merchantId']
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
        agent_secret: str
    ) -> dict:
        """Send activation request to backend"""
        import aiohttp

        base_url = config.backend_url
        url = f"{base_url}/api/registration-codes/activate"

        payload = {
            'code': code,
            'agentId': agent_id,
            'agentSecret': agent_secret
        }

        self.logger.info(f"Sending activation request to {url}")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()

                if response.status == 200 and result.get('code') == 0:
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
            'merchantId': self._credentials.merchant_id
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
                merchant_id=data['merchantId']
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
