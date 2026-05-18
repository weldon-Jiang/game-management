"""
浏览器自动化模块 - Microsoft 设备码认证
=========================================

功能说明：
- 使用 Playwright 实现浏览器自动化登录
- 支持设备码认证流程
- 支持账号密码自动填充
- 支持无头模式（隐藏浏览器窗口）
- 自动关闭浏览器

依赖：
- playwright>=1.40.0
- 安装命令: playwright install chromium

作者：技术团队
版本：2.0

登录流程：
1. 访问 https://www.microsoft.com/link
2. 输入设备码 -> 点击"允许访问"
3. 输入邮箱 -> 点击"下一步"
4. 输入密码 -> 点击"登录"
5. 保持登录状态页面 -> 点击"是"
6. 检测成功页面 -> 关闭浏览器
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('browser_automation')


class BrowserState(Enum):
    """浏览器状态"""
    IDLE = "idle"           # 空闲
    LAUNCHING = "launching" # 启动中
    READY = "ready"         # 就绪
    AUTHENTICATING = "authenticating"  # 认证中
    SUCCESS = "success"     # 认证成功
    FAILED = "failed"       # 认证失败
    CLOSED = "closed"       # 已关闭


@dataclass
class AuthConfig:
    """认证配置"""
    verification_url: str    # 验证URL
    user_code: str          # 设备码
    email: str              # 微软账号邮箱
    password: str           # 微软账号密码
    timeout: int = 300      # 超时时间（秒）


class DeviceCodeAuthenticator:
    """
    设备码认证自动化类

    功能：
    1. 自动打开浏览器并导航到验证URL
    2. 自动输入设备代码，点击"允许访问"
    3. 自动输入账号密码，点击"下一步"和"登录"
    4. 处理保持登录状态页面，点击"是"
    5. 检测成功页面，自动关闭浏览器

    使用方式：
        authenticator = DeviceCodeAuthenticator()
        success = await authenticator.authenticate(
            verification_url="https://www.microsoft.com/link",
            user_code="HUXJQ43Z",
            email="user@outlook.com",
            password="password123"
        )
    """

    def __init__(self, headless: bool = True):
        """
        初始化浏览器自动化器

        参数：
        - headless: 是否使用无头模式（隐藏浏览器窗口）
        """
        self.headless = headless
        self._state = BrowserState.IDLE
        self._browser = None
        self._context = None
        self._page = None
        self._logger = logger

    @property
    def state(self) -> BrowserState:
        """获取当前状态"""
        return self._state

    async def authenticate(
        self,
        verification_url: str,
        user_code: str,
        email: str,
        password: str,
        timeout: int = 300
    ) -> bool:
        """
        执行完整的设备码认证流程

        参数：
        - verification_url: 验证URL
        - user_code: 设备码
        - email: 微软账号邮箱
        - password: 微软账号密码
        - timeout: 超时时间（秒）

        返回：
        - True: 认证成功
        - False: 认证失败
        """
        config = AuthConfig(
            verification_url=verification_url,
            user_code=user_code,
            email=email,
            password=password,
            timeout=timeout
        )

        try:
            # 启动浏览器
            self._state = BrowserState.LAUNCHING
            if not await self._launch_browser():
                self._logger.error("启动浏览器失败")
                return False

            # 执行完整认证流程
            self._state = BrowserState.AUTHENTICATING
            success = await self._execute_auth_flow(config)

            # 认证成功
            if success:
                self._state = BrowserState.SUCCESS
                self._logger.info("设备码认证成功")
            else:
                self._state = BrowserState.FAILED
                self._logger.error("认证流程失败")

            # 关闭浏览器
            await self._close_browser()
            return success

        except Exception as e:
            self._logger.error(f"认证异常: {e}", exc_info=True)
            self._state = BrowserState.FAILED
            await self._close_browser()
            return False

    async def _launch_browser(self) -> bool:
        """
        启动浏览器

        返回：
        - True: 启动成功
        - False: 启动失败
        """
        try:
            from playwright.async_api import async_playwright

            self._logger.info(f"启动浏览器（headless={self.headless}）...")

            # 创建 Playwright 实例
            self._playwright = await async_playwright().start()

            # 启动 Chromium 浏览器
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--start-maximized'
                ]
            )

            # 创建浏览器上下文（隔离环境）
            self._context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            # 创建新页面
            self._page = await self._context.new_page()

            self._state = BrowserState.READY
            self._logger.info("浏览器启动成功")
            return True

        except Exception as e:
            self._logger.error(f"启动浏览器失败: {e}", exc_info=True)
            return False

    async def _execute_auth_flow(self, config: AuthConfig) -> bool:
        """
        执行完整的认证流程

        参数：
        - config: 认证配置

        返回：
        - True: 认证成功
        - False: 认证失败
        """
        try:
            self._logger.info(f"导航到验证URL: {config.verification_url}")

            # Step 1: 导航到验证URL
            await self._page.goto(config.verification_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

            # Step 2: 输入设备码并点击"允许访问"
            if not await self._handle_device_code_step(config.user_code):
                self._logger.error("设备码步骤失败")
                await self._save_screenshot("device_code_step_failed")
                return False

            # Step 3: 输入邮箱并点击"下一步"
            if not await self._handle_email_step(config.email):
                self._logger.error("邮箱输入步骤失败")
                await self._save_screenshot("email_step_failed")
                return False

            # Step 4: 输入密码并点击"登录"
            if not await self._handle_password_step(config.password):
                self._logger.error("密码输入步骤失败")
                await self._save_screenshot("password_step_failed")
                return False

            # Step 5: 处理保持登录状态页面
            await self._handle_keep_signed_in_step()

            # Step 6: 等待成功页面
            if await self._wait_for_success_page(config.timeout):
                self._logger.info("登录成功！")
                return True
            else:
                self._logger.error("未检测到成功页面")
                await self._save_screenshot("success_page_timeout")
                return False

        except Exception as e:
            self._logger.error(f"认证流程异常: {e}", exc_info=True)
            await self._save_screenshot("auth_flow_error")
            return False

    async def _handle_device_code_step(self, user_code: str) -> bool:
        """
        处理设备码输入步骤

        参数：
        - user_code: 设备码

        返回：
        - True: 成功
        - False: 失败
        """
        try:
            self._logger.info("等待设备码输入框...")

            # 等待设备码输入框出现
            selectors = [
                'input[name="otc"]',
                'input[id="otc"]',
                'input[placeholder*="输入代码"]',
                'input[placeholder*="Enter code"]'
            ]

            input_found = False
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=15000, state='visible')
                    await element.fill(user_code)
                    self._logger.info(f"设备码已输入: {user_code}")
                    input_found = True
                    break
                except:
                    continue

            if not input_found:
                self._logger.error("未找到设备码输入框")
                return False

            # 点击"允许访问"按钮
            await asyncio.sleep(1)
            await self._click_allow_access_button()

            return True

        except Exception as e:
            self._logger.error(f"设备码步骤异常: {e}")
            return False

    async def _click_allow_access_button(self):
        """点击"允许访问"按钮"""
        selectors = [
            'input[type="submit"][value="允许访问"]',
            'input[type="submit"]#idSIButton9',
            'input[type="submit"]',
            'button[type="submit"]'
        ]

        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.count() > 0:
                    await element.click()
                    self._logger.info("已点击'允许访问'按钮")
                    await asyncio.sleep(2)
                    return
            except:
                continue

        self._logger.warning("未找到'允许访问'按钮")

    async def _handle_email_step(self, email: str) -> bool:
        """
        处理邮箱输入步骤

        参数：
        - email: 邮箱地址

        返回：
        - True: 成功
        - False: 失败
        """
        try:
            self._logger.info("等待邮箱输入框...")

            # 等待邮箱输入框出现
            selectors = [
                'input[name="loginfmt"]',
                'input[id="i0116"]',
                'input[type="email"]',
                'input[placeholder*="电子邮件"]',
                'input[placeholder*="电话"]',
                'input[placeholder*="Skype"]'
            ]

            input_found = False
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=15000, state='visible')
                    await element.fill(email)
                    self._logger.info(f"邮箱已输入: {email}")
                    input_found = True
                    break
                except:
                    continue

            if not input_found:
                self._logger.error("未找到邮箱输入框")
                return False

            # 点击"下一步"按钮
            await asyncio.sleep(1)
            await self._click_next_button()

            return True

        except Exception as e:
            self._logger.error(f"邮箱步骤异常: {e}")
            return False

    async def _click_next_button(self):
        """点击"下一步"按钮"""
        selectors = [
            'button[type="submit"]:has-text("下一步")',
            'button[type="submit"]',
            'input[type="submit"]',
            'button#idSIButton9'
        ]

        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.count() > 0:
                    await element.click()
                    self._logger.info("已点击'下一步'按钮")
                    await asyncio.sleep(2)
                    return
            except:
                continue

        self._logger.warning("未找到'下一步'按钮")

    async def _handle_password_step(self, password: str) -> bool:
        """
        处理密码输入步骤

        参数：
        - password: 密码

        返回：
        - True: 成功
        - False: 失败
        """
        try:
            self._logger.info("等待密码输入框...")

            # 等待密码输入框出现
            selectors = [
                'input[name="passwd"]',
                'input[id="i0118"]',
                'input[type="password"]',
                'input[placeholder*="密码"]'
            ]

            input_found = False
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=15000, state='visible')
                    await element.fill(password)
                    self._logger.info("密码已输入")
                    input_found = True
                    break
                except:
                    continue

            if not input_found:
                self._logger.error("未找到密码输入框")
                return False

            # 点击"登录"按钮
            await asyncio.sleep(1)
            await self._click_login_button()

            return True

        except Exception as e:
            self._logger.error(f"密码步骤异常: {e}")
            return False

    async def _click_login_button(self):
        """点击"登录"按钮"""
        selectors = [
            'button[type="submit"]:has-text("登录")',
            'button[type="submit"]',
            'input[type="submit"]',
            'button#idSIButton9'
        ]

        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.count() > 0:
                    await element.click()
                    self._logger.info("已点击'登录'按钮")
                    await asyncio.sleep(2)
                    return
            except:
                continue

        self._logger.warning("未找到'登录'按钮")

    async def _handle_keep_signed_in_step(self):
        """处理保持登录状态页面"""
        try:
            self._logger.info("检查保持登录状态页面...")

            # 等待"是"按钮出现（不勾选复选框）
            selectors = [
                'button#acceptButton',
                'button:has-text("是")',
                'button[aria-label="是"]'
            ]

            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=5000, state='visible')
                    await element.click()
                    self._logger.info("已点击'是'按钮（保持登录状态）")
                    await asyncio.sleep(2)
                    return
                except:
                    continue

            self._logger.info("未出现保持登录状态页面，继续...")

        except Exception as e:
            self._logger.warning(f"保持登录状态步骤异常（可能不需要）: {e}")

    async def _wait_for_success_page(self, timeout: int = 300) -> bool:
        """
        等待成功页面

        参数：
        - timeout: 超时时间（秒）

        返回：
        - True: 检测到成功页面
        - False: 超时
        """
        try:
            self._logger.info("等待成功页面...")

            # 成功页面指示器
            success_indicators = [
                'text=大功告成',
                'text=Done',
                'text=Success',
                'text=已成功',
                'text=成功',
                'text=完成',
                'text=You have signed in'
            ]

            # 失败页面指示器
            failure_indicators = [
                'text=失败',
                'text=Failed',
                'text=错误',
                'text=Error',
                'text=密码不正确',
                'text=incorrect',
                'text=Try again'
            ]

            start_time = asyncio.get_event_loop().time()
            check_interval = 2

            while (asyncio.get_event_loop().time() - start_time) < timeout:
                # 检查成功指标
                for indicator in success_indicators:
                    try:
                        if await self._page.locator(indicator).count() > 0:
                            self._logger.info(f"检测到成功标志: {indicator}")
                            await asyncio.sleep(2)  # 额外等待确保页面完全加载
                            return True
                    except:
                        pass

                # 检查失败指标
                for indicator in failure_indicators:
                    try:
                        if await self._page.locator(indicator).count() > 0:
                            self._logger.error(f"检测到失败标志: {indicator}")
                            await self._save_screenshot("login_failed")
                            return False
                    except:
                        pass

                await asyncio.sleep(check_interval)

            self._logger.warning("等待成功页面超时")
            await self._save_screenshot("success_timeout")
            return False

        except Exception as e:
            self._logger.error(f"等待成功页面异常: {e}")
            await self._save_screenshot("success_page_error")
            return False

    async def _save_screenshot(self, name: str):
        """
        保存页面截图

        参数：
        - name: 截图名称
        """
        try:
            import os
            import sys

            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

            logs_dir = os.path.join(base_dir, 'logs')
            screenshot_dir = os.path.join(logs_dir, 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            screenshot_path = os.path.join(screenshot_dir, f'{name}.png')
            await self._page.screenshot(path=screenshot_path)
            self._logger.info(f"截图已保存: {screenshot_path}")

        except Exception as e:
            self._logger.error(f"保存截图失败: {e}")

    async def _close_browser(self):
        """关闭浏览器"""
        try:
            self._state = BrowserState.CLOSED

            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if hasattr(self, '_playwright'):
                await self._playwright.stop()
                self._playwright = None

            self._logger.info("浏览器已关闭")

        except Exception as e:
            self._logger.error(f"关闭浏览器失败: {e}")

    async def close(self):
        """公共关闭方法"""
        await self._close_browser()