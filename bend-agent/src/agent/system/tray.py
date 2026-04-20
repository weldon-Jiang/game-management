"""
System tray module for Bend Agent
Provides system tray icon and menu for Windows
"""
import os
import sys
import asyncio
import threading
from typing import Optional

from ..core.logger import get_logger


class SystemTray:
    """
    System tray manager for Bend Agent
    Provides system tray icon, menu, and notifications
    """

    def __init__(self):
        self.logger = get_logger('tray')
        self._tray_icon: Optional[Any] = None
        self._menu: Optional[Any] = None
        self._running = False
        self._window: Optional[Any] = None

    def initialize(self, window=None):
        """
        Initialize system tray

        Args:
            window: Parent window reference
        """
        try:
            import pystray
            from PIL import Image, ImageDraw

            self._window = window

            image = self._create_default_icon()
            menu = pystray.Menu(
                pystray.MenuItem("Bend Agent", lambda: None, enabled=False),
                pystray.MenuItem("状态: 运行中", lambda: None, enabled=False),
                pystray.MenuItem("---"),
                pystray.MenuItem("打开控制台", self._on_show_console),
                pystray.MenuItem("设置", self._on_show_settings),
                pystray.MenuItem("---"),
                pystray.MenuItem("检查更新", self._on_check_update),
                pystray.MenuItem("关于", self._on_show_about),
                pystray.MenuItem("---"),
                pystray.MenuItem("退出", self._on_exit)
            )

            self._tray_icon = pystray.Icon(
                "bend_agent",
                image,
                "Bend Agent",
                menu
            )

            self._running = True
            self.logger.info("System tray initialized")

        except ImportError as e:
            self.logger.warning(f"System tray not available: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize system tray: {e}")

    def _create_default_icon(self):
        """Create a simple icon image"""
        try:
            from PIL import Image, ImageDraw

            width = 64
            height = 64
            image = Image.new('RGB', (width, height), color=(42, 42, 58))
            draw = ImageDraw.Draw(image)

            draw.ellipse([8, 8, 56, 56], fill=(99, 102, 241))
            draw.ellipse([20, 20, 44, 44], fill=(42, 42, 58))

            return image
        except Exception as e:
            self.logger.error(f"Failed to create icon: {e}")
            return None

    def run(self):
        """Run system tray in a separate thread"""
        if not self._tray_icon:
            return

        def run_tray():
            self._tray_icon.run()

        thread = threading.Thread(target=run_tray, daemon=True)
        thread.start()
        self.logger.info("System tray started")

    def stop(self):
        """Stop system tray"""
        self._running = False
        if self._tray_icon:
            self._tray_icon.stop()
            self.logger.info("System tray stopped")

    def _on_show_console(self, icon=None, item=None):
        """Show console window"""
        try:
            if self._window:
                self._window.show()
                self._window.focus()
        except Exception as e:
            self.logger.error(f"Failed to show console: {e}")

    def _on_show_settings(self, icon=None, item=None):
        """Show settings window"""
        self.logger.info("Show settings")

    def _on_check_update(self, icon=None, item=None):
        """Check for updates"""
        self.logger.info("Checking for updates")

    def _on_show_about(self, icon=None, item=None):
        """Show about dialog"""
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "关于 Bend Agent",
                "Bend Agent v1.0.0\n\n一款高效的Xbox自动化管理工具",
                parent=root
            )
        except Exception as e:
            self.logger.error(f"Failed to show about: {e}")

    def _on_exit(self, icon=None, item=None):
        """Exit application"""
        self.logger.info("Exit requested from system tray")
        self._running = False
        if self._tray_icon:
            self._tray_icon.stop()

    def update_status(self, status: str):
        """Update tray tooltip"""
        if self._tray_icon:
            self._tray_icon.title = f"Bend Agent - {status}"

    def show_notification(self, title: str, message: str):
        """
        Show system notification

        Args:
            title: Notification title
            message: Notification message
        """
        if not self._tray_icon:
            return

        try:
            self._tray_icon.notify(message, title)
        except Exception as e:
            self.logger.error(f"Failed to show notification: {e}")


system_tray = SystemTray()
