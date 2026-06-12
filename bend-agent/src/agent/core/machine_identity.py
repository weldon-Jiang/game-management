"""
Bend Agent 机器标识模块。
基于硬件特征生成并持久化唯一机器 ID。
"""
import hashlib
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .logger import get_logger
from .paths import get_logs_dir_fallback

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore[assignment]


class MachineIdentity:
    """
    机器标识管理器。
    基于硬件特征生成并持久化唯一机器 ID。
    """

    REGISTRY_PATH = r"SOFTWARE\BendPlatform\Agent"
    MACHINE_ID_KEY = "MachineId"
    INSTALL_PATH_KEY = "InstallPath"
    INSTALLED_AT_KEY = "InstalledAt"
    FILE_NAME = "machine_id"
    INSTALL_PATH_FILE = "install_path"

    def __init__(self):
        self.logger = get_logger('machine_identity')
        self._machine_id: Optional[str] = None

    def _identity_file_path(self) -> Path:
        """非 Windows 平台将机器 ID 持久化到 logs 目录旁的文件。"""
        return Path(get_logs_dir_fallback()).parent / self.FILE_NAME

    def _install_path_file(self) -> Path:
        """非 Windows 平台安装路径标记文件。"""
        return Path(get_logs_dir_fallback()).parent / self.INSTALL_PATH_FILE

    def get_machine_id(self) -> str:
        """
        获取或生成唯一机器 ID。
        Windows 使用注册表；其他平台使用本地文件持久化。
        """
        if self._machine_id:
            return self._machine_id

        stored_id = self._load_persisted_id()
        if stored_id:
            self._machine_id = stored_id
            self.logger.info(f"Loaded machine ID from storage: {stored_id[:8]}...")
            return stored_id

        new_id = self._generate_machine_id()
        self._save_persisted_id(new_id)
        self._machine_id = new_id
        self.logger.info(f"Generated new machine ID: {new_id[:8]}...")
        return new_id

    def _load_persisted_id(self) -> Optional[str]:
        if sys.platform == "win32":
            return self._load_from_registry()
        return self._load_from_file()

    def _save_persisted_id(self, machine_id: str) -> bool:
        if sys.platform == "win32":
            return self._save_to_registry(machine_id)
        return self._save_to_file(machine_id)

    def _load_from_file(self) -> Optional[str]:
        path = self._identity_file_path()
        try:
            if not path.is_file():
                return None
            value = path.read_text(encoding="utf-8").strip()
            return value or None
        except OSError as exc:
            self.logger.warning(f"Failed to load machine ID from file: {exc}")
            return None

    def _save_to_file(self, machine_id: str) -> bool:
        path = self._identity_file_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(machine_id, encoding="utf-8")
            self.logger.info(f"Saved machine ID to file: {machine_id[:8]}...")
            return True
        except OSError as exc:
            self.logger.error(f"Failed to save machine ID to file: {exc}")
            return False

    def _load_from_registry(self) -> Optional[str]:
        """从 Windows 注册表加载机器 ID（当前用户，无需管理员）"""
        if winreg is None:
            return None
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
        if winreg is None:
            return False
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
        if sys.platform != "win32":
            node = uuid.getnode()
            if (node >> 40) % 2:
                return None
            mac = ":".join(f"{(node >> shift) & 0xFF:02x}" for shift in range(40, -1, -8))
            if mac and not mac.startswith("00:00:00"):
                return mac
            return None

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

    def get_install_path(self) -> Optional[str]:
        """读取本机 Agent 安装目录标记；未安装时返回 None。"""
        if sys.platform == "win32":
            return self._read_registry_string(self.INSTALL_PATH_KEY)
        return self._load_install_path_from_file()

    def mark_installed(self, install_path: str) -> bool:
        """
        写入安装目录与安装时间；首次激活或迁移旧版本时调用。
        """
        normalized = str(Path(install_path).resolve())
        installed_at = datetime.now(timezone.utc).isoformat()

        if sys.platform == "win32":
            if winreg is None:
                return False
            try:
                key = winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER,
                    self.REGISTRY_PATH,
                )
                winreg.SetValueEx(
                    key, self.INSTALL_PATH_KEY, 0, winreg.REG_SZ, normalized,
                )
                winreg.SetValueEx(
                    key, self.INSTALLED_AT_KEY, 0, winreg.REG_SZ, installed_at,
                )
                winreg.CloseKey(key)
            except WindowsError as exc:
                self.logger.error("Failed to save install path to registry: %s", exc)
                return False
        elif not self._save_install_path_to_file(normalized):
            return False

        self.logger.info("Marked Agent install path: %s", normalized)
        return True

    def clear_install_registry(self) -> bool:
        """
        清除本机 Agent 安装标记（MachineId、InstallPath、InstalledAt）。
        卸载后调用，允许在同一台电脑重新安装。
        """
        if sys.platform == "win32":
            if winreg is None:
                return False
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.REGISTRY_PATH)
            except FileNotFoundError:
                pass
            except WindowsError as exc:
                self.logger.error("Failed to clear install registry: %s", exc)
                return False
        else:
            for path in (self._identity_file_path(), self._install_path_file()):
                try:
                    if path.is_file():
                        path.unlink()
                except OSError as exc:
                    self.logger.error("Failed to clear install marker file %s: %s", path, exc)
                    return False

        self._machine_id = None
        self.logger.warning("Agent install registry cleared")
        return True

    def reset_machine_id(self) -> bool:
        """
        重置机器 ID（测试或排障用）。
        警告：平台将把该 Agent 视为全新安装。
        """
        return self.clear_install_registry()

    def _read_registry_string(self, value_name: str) -> Optional[str]:
        if winreg is None:
            return None
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REGISTRY_PATH,
                0,
                winreg.KEY_READ,
            )
            try:
                value, _ = winreg.QueryValueEx(key, value_name)
                winreg.CloseKey(key)
                return value if value else None
            except FileNotFoundError:
                winreg.CloseKey(key)
                return None
        except WindowsError:
            return None

    def _load_install_path_from_file(self) -> Optional[str]:
        path = self._install_path_file()
        try:
            if not path.is_file():
                return None
            value = path.read_text(encoding="utf-8").strip()
            return value or None
        except OSError as exc:
            self.logger.warning("Failed to load install path file: %s", exc)
            return None

    def _save_install_path_to_file(self, install_path: str) -> bool:
        path = self._install_path_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(install_path, encoding="utf-8")
            return True
        except OSError as exc:
            self.logger.error("Failed to save install path file: %s", exc)
            return False


machine_identity = MachineIdentity()
