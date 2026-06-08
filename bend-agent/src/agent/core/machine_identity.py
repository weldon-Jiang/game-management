"""
Bend Agent 机器标识模块。
基于硬件特征生成并持久化唯一机器 ID。
"""
import hashlib
import uuid
import platform
import os
import winreg
from typing import Optional

from .logger import get_logger


class MachineIdentity:
    """
    机器标识管理器。
    基于硬件特征生成并持久化唯一机器 ID。
    """

    REGISTRY_PATH = r"SOFTWARE\BendPlatform\Agent"
    MACHINE_ID_KEY = "MachineId"
    FILE_PATH = None  # 在 get_machine_id() 中设为 exe 目录

    def __init__(self):
        self.logger = get_logger('machine_identity')
        self._machine_id: Optional[str] = None

    def get_machine_id(self) -> str:
        """
        获取或生成唯一机器 ID。
        ID 持久化在 Windows 注册表，换路径重装 Agent 后仍保持不变。
        """
        if self._machine_id:
            return self._machine_id

        stored_id = self._load_from_registry()
        if stored_id:
            self._machine_id = stored_id
            self.logger.info(f"Loaded machine ID from registry: {stored_id[:8]}...")
            return stored_id

        new_id = self._generate_machine_id()
        self._save_to_registry(new_id)
        self._machine_id = new_id
        self.logger.info(f"Generated new machine ID: {new_id[:8]}...")
        return new_id

    def _load_from_registry(self) -> Optional[str]:
        """从 Windows 注册表加载机器 ID（当前用户，无需管理员）"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REGISTRY_PATH,
                0,
                winreg.KEY_READ
            )
            try:
                value, _ = winreg.QueryValueEx(key, self.MACHINE_ID_KEY)
                winreg.CloseKey(key)
                return value if value else None
            except FileNotFoundError:
                winreg.CloseKey(key)
                return None
        except WindowsError:
            return None

    def _save_to_registry(self, machine_id: str) -> bool:
        """将机器 ID 保存到 Windows 注册表（当前用户，无需管理员）"""
        try:
            key = winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                self.REGISTRY_PATH
            )
            winreg.SetValueEx(key, self.MACHINE_ID_KEY, 0, winreg.REG_SZ, machine_id)
            winreg.CloseKey(key)
            self.logger.info(f"Saved machine ID to registry: {machine_id[:8]}...")
            return True
        except WindowsError as e:
            self.logger.error(f"Failed to save machine ID to registry: {e}")
            return False

    def _generate_machine_id(self) -> str:
        """
        基于硬件特征生成唯一机器 ID。
        """
        components = []

        components.append(platform.node())

        components.append(platform.processor())

        components.append(platform.machine())

        try:
            import wmi
            c = wmi.WMI()
            for board in c.Win_BaseBoard():
                components.append(board.SerialNumber)
            for bios in c.Win_BIOS():
                components.append(bios.SerialNumber)
        except ImportError:
            pass
        except Exception as e:
            self.logger.warning(f"Failed to get hardware info: {e}")

        try:
            mac = self._get_mac_address()
            if mac:
                components.append(mac)
        except Exception:
            pass

        combined = '|'.join(components)
        hash_value = hashlib.sha256(combined.encode('utf-8')).hexdigest()

        return f"AGENT-{hash_value[:8].upper()}-{hash_value[8:16].upper()}-{hash_value[16:24].upper()}"

    def _get_mac_address(self) -> Optional[str]:
        """获取第一个非虚拟 MAC 地址"""
        import subprocess
        try:
            result = subprocess.run(
                ['getmac', '/fo', 'csv', '/nh'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                parts = line.split(',')
                if len(parts) >= 1:
                    mac = parts[0].strip('"').replace('-', ':')
                    if mac and not mac.startswith('00:00:00'):
                        return mac
        except Exception:
            pass
        return None

    def get_agent_id_from_machine_id(self) -> str:
        """
        由机器 ID 生成 Agent ID，跨安装保持同一标识。
        """
        return self.get_machine_id()

    def reset_machine_id(self) -> bool:
        """
        重置机器 ID（测试或排障用）。
        警告：平台将把该 Agent 视为全新安装。
        """
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REGISTRY_PATH,
                0,
                winreg.KEY_WRITE
            )
            try:
                winreg.DeleteValue(key, self.MACHINE_ID_KEY)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            self._machine_id = None
            self.logger.warning("Machine ID has been reset")
            return True
        except WindowsError as e:
            self.logger.error(f"Failed to reset machine ID: {e}")
            return False


machine_identity = MachineIdentity()
