"""
Bend Agent 系统托盘模块。
提供 Windows 系统托盘图标与菜单。
"""
import os
import sys
import asyncio
import threading
from typing import Any, Optional

from ..core.logger import get_logger


class SystemTray:
    """
    Bend Agent 系统托盘管理器。
    提供托盘图标、菜单与通知。
    """

    def __init__(self):
        self.logger = get_logger('tray')
        self._tray_icon: Optional[Any] = None
        self._menu: Optional[Any] = None
        self._running = False
        self._window: Optional[Any] = None

    def initialize(self, window=None):
        """
        初始化系统托盘。

        参数:
            window: 父窗口引用
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
        """创建简单图标图像"""
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
        """在独立线程运行系统托盘"""
        if not self._tray_icon:
            return

        def run_tray():
            self._tray_icon.run()

        thread = threading.Thread(target=run_tray, daemon=True)
        thread.start()
        self.logger.info("System tray started")

    def stop(self):
        """停止系统托盘"""
        self._running = False
        if self._tray_icon:
            self._tray_icon.stop()
            self.logger.info("System tray stopped")

    def _on_show_console(self, icon=None, item=None):
        """显示控制台窗口"""
        try:
            if self._window:
                self._window.show()
                self._window.focus()
        except Exception as e:
            self.logger.error(f"Failed to show console: {e}")

    def _on_show_settings(self, icon=None, item=None):
        """显示设置窗口"""
        self.logger.info("Show settings")

    def _on_check_update(self, icon=None, item=None):
        """检查更新"""
        self.logger.info("Checking for updates")

    def _on_show_about(self, icon=None, item=None):
        """显示关于对话框"""
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
        """退出应用"""
        self.logger.info("Exit requested from system tray")
        self._running = False
        if self._tray_icon:
            self._tray_icon.stop()

    def update_status(self, status: str):
        """更新托盘提示文字"""
        if self._tray_icon:
            self._tray_icon.title = f"Bend Agent - {status}"

    def show_notification(self, title: str, message: str):
        """
        显示系统通知。

        参数:
            title: 通知标题
            message: 通知内容
        """
        if not self._tray_icon:
            return

        try:
            self._tray_icon.notify(message, title)
        except Exception as e:
            self.logger.error(f"Failed to show notification: {e}")


system_tray = SystemTray()
