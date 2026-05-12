"""
Agent更新管理器
处理版本检查、下载和安装
"""
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

from ..core.config import config
from ..core.logger import get_logger
from ..core.paths import get_base_dir


class UpdateStatus(Enum):
    """Update status"""
    CHECKING = "checking"
    COMPATIBLE = "compatible"
    UPDATE_AVAILABLE = "update_available"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    REBOOTING = "rebooting"
    FAILED = "failed"


@dataclass
class UpdateInfo:
    """Update information"""
    current_version: str
    latest_version: str
    download_url: str
    md5_checksum: str
    changelog: str
    mandatory: bool
    force_restart: bool


class UpdateManager:
    """
    Agent更新管理器
    负责检查更新、下载和安装
    """

    def __init__(self, api_client, version: str):
        self.api = api_client
        self.current_version = version
        self.logger = get_logger('update')
        self._update_info: Optional[UpdateInfo] = None
        self._status = UpdateStatus.CHECKING
        self._progress = 0
        self._download_path = None
        self._on_status_change: Optional[Callable] = None

    def set_status_callback(self, callback: Callable):
        """Set callback for status changes"""
        self._on_status_change = callback

    def _notify_status(self, status: UpdateStatus, progress: int = 0):
        """Notify status change"""
        self._status = status
        self._progress = progress
        if self._on_status_change:
            self._on_status_change(status, progress)

    async def check_update(self) -> Optional[UpdateInfo]:
        """Check if there's an update available"""
        self._notify_status(UpdateStatus.CHECKING)

        try:
            result = await self.api.check_update(self.current_version)
            if result.get('code') == 0 or result.get('code') == 200:
                data = result.get('data', {})
                if data.get('hasUpdate'):
                    self._update_info = UpdateInfo(
                        current_version=self.current_version,
                        latest_version=data.get('latestVersion'),
                        download_url=data.get('downloadUrl'),
                        md5_checksum=data.get('md5Checksum', ''),
                        changelog=data.get('changelog', ''),
                        mandatory=data.get('mandatory', False),
                        force_restart=data.get('forceRestart', False)
                    )
                    self._notify_status(UpdateStatus.UPDATE_AVAILABLE)
                    self.logger.info(f"Update available: {self._update_info.latest_version}")
                    return self._update_info
                else:
                    self._notify_status(UpdateStatus.COMPATIBLE)
                    self.logger.info("Current version is up to date")
                    return None
            else:
                self.logger.error(f"Check update failed: {result.get('message')}")
                return None
        except Exception as e:
            self.logger.error(f"Check update error: {e}")
            return None

    async def download_update(self, info: UpdateInfo = None) -> bool:
        """Download the update package"""
        update_info = info or self._update_info
        if not update_info:
            self.logger.error("No update info available")
            return False

        self._notify_status(UpdateStatus.DOWNLOADING, 0)

        temp_dir = config.get('agent.update_temp_dir', os.path.join(get_base_dir(), 'temp'))
        os.makedirs(temp_dir, exist_ok=True)

        self._download_path = os.path.join(temp_dir, f"agent_{update_info.latest_version}.zip")

        def progress_callback(progress):
            self._notify_status(UpdateStatus.DOWNLOADING, progress)

        try:
            success = await self.api.download_file(
                update_info.download_url,
                self._download_path,
                update_info.md5_checksum,
                progress_callback
            )

            if success:
                self._notify_status(UpdateStatus.VERIFYING)
                self.logger.info(f"Update downloaded: {self._download_path}")
                return True
            else:
                self._notify_status(UpdateStatus.FAILED)
                self.logger.error("Download failed")
                return False

        except Exception as e:
            self.logger.error(f"Download error: {e}")
            self._notify_status(UpdateStatus.FAILED)
            return False

    async def install_update(self, force: bool = False) -> bool:
        """Install the downloaded update"""
        if not self._download_path or not os.path.exists(self._download_path):
            self.logger.error("No update package found")
            return False

        if not force and self._update_info and self._update_info.mandatory:
            self.logger.error("Mandatory update cannot be skipped")
            return False

        self._notify_status(UpdateStatus.INSTALLING)

        try:
            backup_path = self._create_backup()
            if not backup_path:
                self.logger.warning("Failed to create backup, continuing anyway")

            if self._update_info and self._update_info.force_restart:
                success = self._perform_hot_update()
            else:
                success = self._schedule_update()

            if success:
                self._notify_status(UpdateStatus.REBOOTING)
                self.logger.info("Update installed, rebooting...")
            else:
                self._notify_status(UpdateStatus.FAILED)
                self.logger.error("Installation failed")

            return success

        except Exception as e:
            self.logger.error(f"Install error: {e}")
            self._notify_status(UpdateStatus.FAILED)
            return False

    def _create_backup(self) -> Optional[str]:
        """Create backup of current installation"""
        try:
            import shutil
            current_exe = sys.executable
            backup_dir = config.get('agent.backup_dir', os.path.join(get_base_dir(), 'backup'))
            os.makedirs(backup_dir, exist_ok=True)

            backup_path = os.path.join(backup_dir, f"agent_backup_{self.current_version}.exe")
            shutil.copy2(current_exe, backup_path)
            self.logger.info(f"Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            return None

    def _perform_hot_update(self) -> bool:
        """Perform hot update without restart"""
        try:
            update_script = config.get('agent.update_script',
                os.path.join(get_base_dir(), 'scripts', 'hot_update.py'))
            if os.path.exists(update_script):
                result = subprocess.run(
                    [sys.executable, update_script, self._download_path],
                    capture_output=True
                )
                return result.returncode == 0
            return False
        except Exception as e:
            self.logger.error(f"Hot update failed: {e}")
            return False

    def _schedule_update(self) -> bool:
        """Schedule update to run on next restart"""
        try:
            update_batch = config.get('agent.update_batch',
                os.path.join(get_base_dir(), 'scripts', 'update.bat'))

            batch_content = f"""@echo off
timeout /t 2 /nobreak > nul
xcopy /Y "{self._download_path}" "{os.path.dirname(sys.executable)}\\"
del "{self._download_path}"
start "" "{sys.executable}"
del "%~f0"
"""

            with open(update_batch, 'w') as f:
                f.write(batch_content)

            subprocess.Popen(update_batch, shell=True)
            self.logger.info("Update scheduled for next restart")
            return True

        except Exception as e:
            self.logger.error(f"Schedule update failed: {e}")
            return False

    async def auto_update(self) -> bool:
        """Check and perform update automatically"""
        info = await self.check_update()
        if not info:
            return True

        if info.mandatory:
            downloaded = await self.download_update(info)
            if downloaded:
                return await self.install_update(force=False)
            return False
        else:
            self.logger.info("Optional update available, skipping auto-update")
            return True

    def handle_version_update(self, data: dict):
        """
        Handle version update notification from platform via WebSocket

        Args:
            data: Version update data from platform
                - version: New version string
                - downloadUrl: Download URL
                - md5Checksum: MD5 checksum for verification
                - changelog: Update changelog
                - mandatory: Whether update is mandatory
                - forceRestart: Whether restart is required
        """
        try:
            version = data.get('version')
            download_url = data.get('downloadUrl', '')
            md5_checksum = data.get('md5Checksum', '')
            changelog = data.get('changelog', '')
            mandatory = data.get('mandatory', False)
            force_restart = data.get('forceRestart', False)

            self.logger.info(f"Received version update notification: {version}, mandatory: {mandatory}")

            self._update_info = UpdateInfo(
                current_version=self.current_version,
                latest_version=version,
                download_url=download_url,
                md5_checksum=md5_checksum,
                changelog=changelog,
                mandatory=mandatory,
                force_restart=force_restart
            )

            if mandatory:
                self.logger.info(f"Mandatory update to {version}, starting download...")
                asyncio.create_task(self._auto_download_and_install())
            else:
                self.logger.info(f"Optional update to {version}, waiting for user confirmation")
                self._notify_status(UpdateStatus.UPDATE_AVAILABLE)

        except Exception as e:
            self.logger.error(f"Failed to handle version update: {e}")

    async def _auto_download_and_install(self):
        """Auto download and install the update"""
        try:
            downloaded = await self.download_update()
            if downloaded:
                await self.install_update(force=True)
            else:
                self.logger.error("Auto update failed: download failed")
                self._notify_status(UpdateStatus.FAILED)
        except Exception as e:
            self.logger.error(f"Auto update error: {e}")
            self._notify_status(UpdateStatus.FAILED)

    @property
    def update_info(self) -> Optional[UpdateInfo]:
        return self._update_info

    @property
    def status(self) -> UpdateStatus:
        return self._status

    @property
    def progress(self) -> int:
        return self._progress
