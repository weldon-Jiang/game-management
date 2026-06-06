"""
浏览器自动化模块 - Microsoft 设备码认证
=========================================

功能：
- Playwright 浏览器自动化登录
- 设备码认证流程
- MFA 多因素认证支持 (SMS/Email/App/Phone)
- TOTP 自动验证码生成

依赖：playwright>=1.40.0
安装：playwright install chromium

作者：技术团队
版本：4.0

认证流程：
1. 访问验证URL -> 输入设备码 -> 点击"允许访问"
2. 输入邮箱 -> 点击"下一步"
3. 输入密码 -> 点击"登录"
4. [可选] 处理 MFA 多因素认证
5. [可选] 保持登录状态 -> 点击"是"
6. 检测成功页面 -> 关闭浏览器
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    import pyotp
    TOTP_AVAILABLE = True
except ImportError:
    TOTP_AVAILABLE = False
    logger.warning("pyotp未安装，MFA自动验证码生成将不可用")

logger = logging.getLogger('browser_automation')


class PerformanceTimer:
    """性能计时器"""
    
    def __init__(self):
        self._start_times = {}
        self._durations = {}
    
    def start(self, step_name: str):
        """开始计时"""
        self._start_times[step_name] = time.perf_counter()
        logger.debug(f"⏱️ [{step_name}] 开始计时")
    
    def end(self, step_name: str) -> float:
        """结束计时并返回耗时（秒）"""
        if step_name in self._start_times:
            duration = time.perf_counter() - self._start_times[step_name]
            self._durations[step_name] = duration
            logger.info(f"⏱️ [{step_name}] 完成，耗时: {duration:.2f}秒")
            return duration
        return 0.0
    
    def get_duration(self, step_name: str) -> float:
        """获取步骤耗时"""
        return self._durations.get(step_name, 0.0)
    
    def get_summary(self) -> Dict[str, float]:
        """获取所有步骤的耗时汇总"""
        return dict(self._durations)


class BrowserState(Enum):
    """浏览器状态"""
    IDLE = "idle"           # 空闲
    LAUNCHING = "launching" # 启动中
    READY = "ready"         # 就绪
    AUTHENTICATING = "authenticating"  # 认证中
    MFA_REQUIRED = "mfa_required"      # 需要MFA验证
    SUCCESS = "success"     # 认证成功
    FAILED = "failed"       # 认证失败
    CLOSED = "closed"       # 已关闭


class MFAType(Enum):
    """MFA 验证类型"""
    SMS = "sms"                   # 短信验证码
    EMAIL = "email"              # 邮件验证码
    APP = "app"                  # Authenticator App
    PHONE = "phone"              # 电话验证
    UNKNOWN = "unknown"           # 未知类型


class MFAConfig:
    """
    MFA 配置类
    
    用于配置 MFA 验证的处理方式
    """
    def __init__(
        self,
        timeout: int = 300,
        max_retries: int = 3,
        check_interval: float = 2.0
    ):
        self.timeout = timeout          # MFA 验证超时时间（秒）
        self.max_retries = max_retries  # 最大重试次数
        self.check_interval = check_interval  # 检测间隔（秒）


@dataclass
class AuthConfig:
    """认证配置"""
    verification_url: str    # 验证URL
    user_code: str          # 设备码
    email: str              # 微软账号邮箱
    password: str           # 微软账号密码
    timeout: int = 300      # 超时时间（秒）
    mfa_config: MFAConfig = None  # MFA 配置


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
    
    性能优化：
    - 使用智能等待替代固定sleep
    - 优化页面加载策略
    - 添加性能计时器记录每个步骤耗时
    """

    # 元素等待超时时间（秒）- 优化：从15秒缩短到8秒
    ELEMENT_TIMEOUT = 8000
    # 短等待时间（毫秒）- 用于点击后的最小等待
    SHORT_DELAY = 500
    # 页面加载超时时间（秒）
    PAGE_LOAD_TIMEOUT = 30000

    def __init__(self, headless: bool = True, auto_code: str = None):
        """
        初始化浏览器自动化器

        参数：
        - headless: 是否使用无头模式（隐藏浏览器窗口）
        - auto_code: TOTP Secret Key，用于MFA自动验证码生成
        """
        self.headless = headless
        self._state = BrowserState.IDLE
        self._browser = None
        self._context = None
        self._page = None
        self._logger = logger
        self._timer = PerformanceTimer()  # 性能计时器
        self._mfa_error_code = None  # MFA 错误码
        self._auto_code = auto_code  # TOTP Secret Key

    @property
    def state(self) -> BrowserState:
        """获取当前状态"""
        return self._state
    
    @property
    def mfa_error_code(self) -> Optional[str]:
        """获取 MFA 错误码"""
        return self._mfa_error_code

    def _generate_totp_code(self) -> Optional[str]:
        """
        使用TOTP算法生成验证码
        
        使用存储的auto_code (TOTP Secret Key) 生成6位动态验证码
        
        Returns:
            Optional[str]: 生成的验证码，失败返回None
        """
        if not self._auto_code:
            self._logger.debug("未配置TOTP Secret Key")
            return None
        
        if not TOTP_AVAILABLE:
            self._logger.warning("pyotp库未安装，无法生成TOTP验证码")
            return None
        
        try:
            # 清理Secret Key（移除空格，转换为大写）
            secret = self._auto_code.strip().upper()
            
            # 验证Base32格式
            valid_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
            secret = "".join([c for c in secret if c in valid_chars])
            
            if not secret:
                self._logger.error("TOTP Secret Key格式无效")
                return None
            
            # 生成TOTP验证码
            totp = pyotp.TOTP(secret)
            code = totp.now()
            
            self._logger.info(f"TOTP验证码生成成功: {code}")
            return code
            
        except Exception as e:
            self._logger.error(f"TOTP验证码生成失败: {e}")
            return None

    async def _submit_mfa_code(self) -> bool:
        """
        提交MFA验证码
        
        查找并点击验证码验证按钮
        
        Returns:
            bool: 提交是否成功
        """
        try:
            # 查找验证按钮
            submit_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                'button:has-text("验证")',
                'button:has-text("Verify")',
                'span:has-text("验证")',
                'input[value="验证"]',
                'button:has-text("下一步")',
                'input[value="下一步"]'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=3000, state='visible')
                    submit_button = element
                    self._logger.info(f"找到验证按钮: {selector}")
                    break
                except:
                    continue
            
            if submit_button:
                await submit_button.click()
                self._logger.info("已点击验证按钮")
                
                # 等待一小段时间让服务器处理
                await asyncio.sleep(2)
                return True
            else:
                self._logger.warning("未找到验证按钮")
                return False
                
        except Exception as e:
            self._logger.error(f"提交MFA验证码失败: {e}")
            return False

    async def authenticate(
        self,
        verification_url: str,
        user_code: str,
        email: str,
        password: str,
        auto_code: str = None,
        timeout: int = 300
    ) -> bool:
        """
        执行完整的设备码认证流程

        参数：
        - verification_url: 验证URL
        - user_code: 设备码
        - email: 微软账号邮箱
        - password: 微软账号密码
        - auto_code: TOTP Secret Key，用于MFA自动验证码生成
        - timeout: 超时时间（秒）
        
        返回：
        - True: 认证成功
        - False: 认证失败
        """
        if auto_code:
            self._auto_code = auto_code

        config = AuthConfig(
            verification_url=verification_url,
            user_code=user_code,
            email=email,
            password=password,
            timeout=timeout
        )

        total_start_time = time.perf_counter()
        self._logger.info(f"========== 开始设备码认证流程 (账号: {email}) ==========")

        try:
            self._state = BrowserState.LAUNCHING
            self._timer.start("浏览器启动")
            if not await self._launch_browser():
                self._logger.error("启动浏览器失败")
                return False
            self._timer.end("浏览器启动")

            self._state = BrowserState.AUTHENTICATING
            self._timer.start("认证流程")
            success = await self._execute_auth_flow(config)
            self._timer.end("认证流程")

            if success:
                self._state = BrowserState.SUCCESS
                self._logger.info("设备码认证成功")
            else:
                self._state = BrowserState.FAILED
                self._logger.error("认证流程失败")

            self._timer.start("浏览器关闭")
            await self._close_browser()
            self._timer.end("浏览器关闭")

            total_duration = time.perf_counter() - total_start_time
            self._logger.info("========== 认证流程完成 ==========")
            self._logger.info(f"整体耗时: {total_duration:.2f}秒")
            for step, duration in self._timer.get_summary().items():
                self._logger.info(f"  - {step}: {duration:.2f}秒")

            return success

        except Exception as e:
            self._logger.error(f"认证异常: {e}", exc_info=True)
            self._state = BrowserState.FAILED
            total_duration = time.perf_counter() - total_start_time
            self._logger.error(f"认证失败，总耗时: {total_duration:.2f}秒")
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
            self._logger.info("_launch_browser() 方法开始执行")

            self._logger.info("正在导入 playwright...")
            from playwright.async_api import async_playwright
            self._logger.info("playwright 导入成功")

            self._logger.info(f"启动浏览器（headless={self.headless}）...")

            # 创建 Playwright 实例
            self._logger.info("正在创建 Playwright 实例...")
            self._playwright = await async_playwright().start()
            self._logger.info("Playwright 实例已创建")

            # 启动 Chromium 浏览器
            self._logger.info("正在启动 Chromium 浏览器（这可能需要一些时间）...")
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
            self._logger.info("Chromium 浏览器已启动")

            # 创建浏览器上下文（隔离环境）
            self._logger.info("正在创建浏览器上下文...")
            self._context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self._logger.info("浏览器上下文已创建")

            # 创建新页面
            self._logger.info("正在创建新页面...")
            self._page = await self._context.new_page()
            self._logger.info("新页面已创建")

            self._state = BrowserState.READY
            self._logger.info("浏览器启动成功")
            return True

        except Exception as e:
            self._logger.error(f"启动浏览器失败: {e}", exc_info=True)
            return False

    async def _detect_mfa_type(self) -> MFAType:
        """
        检测 MFA 类型
        
        返回：
        - MFAType: MFA 验证类型
        """
        try:
            # 检查页面标题或 URL
            page_title = await self._page.title()
            page_content = await self._page.content()
            
            self._logger.info("检测 MFA 验证类型...")
            
            # SMS 短信验证码
            sms_indicators = [
                "短信",
                "SMS",
                "phone",
                "verification code.*text",
                "代码.*发送.*手机"
            ]
            for indicator in sms_indicators:
                if indicator.lower() in page_content.lower():
                    self._logger.info("检测到 SMS 短信验证码 MFA")
                    return MFAType.SMS
            
            # Email 邮件验证码
            email_indicators = [
                "电子邮件",
                "email",
                "发送.*邮件",
                "代码.*发送.*邮件",
                "microsoft.com.*发送.*邮箱"
            ]
            for indicator in email_indicators:
                if indicator.lower() in page_content.lower():
                    self._logger.info("检测到 Email 邮件验证码 MFA")
                    return MFAType.EMAIL
            
            # App Authenticator
            app_indicators =[
                "Authenticator",
                "应用",
                "approvals",
                "microsoft authenticator",
                "输入.*六位数"
            ]
            for indicator in app_indicators:
                if indicator.lower() in page_content.lower():
                    self._logger.info("检测到 Authenticator App MFA")
                    return MFAType.APP
            
            # Phone 电话验证
            phone_indicators = [
                "电话",
                "call",
                "拨打.*电话号码"
            ]
            for indicator in phone_indicators:
                if indicator.lower() in page_content.lower():
                    self._logger.info("检测到 Phone 电话验证 MFA")
                    return MFAType.PHONE
            
            # 默认返回未知类型，但记录页面内容供调试
            self._logger.warning(f"无法识别 MFA 类型，页面标题: {page_title}")
            self._logger.debug(f"页面内容片段: {page_content[:500]}")
            return MFAType.UNKNOWN
            
        except Exception as e:
            self._logger.error(f"检测 MFA 类型异常: {e}")
            return MFAType.UNKNOWN

    async def _check_mfa_required(self) -> bool:
        """
        检查是否需要进行 MFA 验证
        
        返回：
        - True: 需要 MFA 验证
        - False: 不需要 MFA 验证
        """
        try:
            # MFA 页面指示器
            mfa_indicators = [
                'text=额外验证',
                'text=两步验证',
                'text=Two-factor',
                'text=2FA',
                'text=多因素',
                'text=验证器',
                'text=Authenticator',
                'text=验证码',
                'text=verification code',
                'input[name="otc"]',
                'input[id="otc"]',
                'input[maxlength="6"]',
                'input[type="tel"]'
            ]
            
            for indicator in mfa_indicators:
                try:
                    if indicator.startswith('text='):
                        # 文本指示器
                        text = indicator[5:]  # 移除 'text=' 前缀
                        if await self._page.locator(f'text={text}').count() > 0:
                            self._logger.info(f"检测到 MFA 指示器: {indicator}")
                            return True
                    else:
                        # 选择器指示器
                        if await self._page.locator(indicator).count() > 0:
                            self._logger.info(f"检测到 MFA 输入框: {indicator}")
                            return True
                except Exception as e:
                    self._logger.debug(f"MFA 指示器检测失败 {indicator}: {e}")
                    continue
            
            self._logger.info("未检测到 MFA 验证要求")
            return False
            
        except Exception as e:
            self._logger.error(f"检查 MFA 要求异常: {e}")
            return False

    async def _handle_mfa_verification(self, config: AuthConfig) -> bool:
        """
        处理 MFA 验证流程
        
        参数：
        - config: 认证配置
        
        返回：
        - True: MFA 验证成功
        - False: MFA 验证失败
        """
        try:
            self._logger.info("开始处理 MFA 多因素认证...")
            self._state = BrowserState.MFA_REQUIRED
            
            # 检测 MFA 类型
            mfa_type = await self._detect_mfa_type()
            self._logger.info(f"MFA 类型: {mfa_type.value}")
            
            # 根据类型处理
            if mfa_type == MFAType.SMS:
                success = await self._handle_sms_mfa()
            elif mfa_type == MFAType.EMAIL:
                success = await self._handle_email_mfa()
            elif mfa_type == MFAType.APP:
                success = await self._handle_app_mfa()
            elif mfa_type == MFAType.PHONE:
                success = await self._handle_phone_mfa()
            else:
                # 未知类型，尝试通用处理
                success = await self._handle_generic_mfa()
            
            if not success:
                self._mfa_error_code = "MFA_FAILED"
            
            return success
                
        except Exception as e:
            self._logger.error(f"MFA 验证处理异常: {e}", exc_info=True)
            self._mfa_error_code = "MFA_FAILED"
            return False

    async def _handle_sms_mfa(self) -> bool:
        """处理短信验证码 MFA"""
        try:
            self._logger.info("处理 SMS 短信验证码...")
            
            # 等待验证码输入框
            selectors = [
                'input[name="otc"]',
                'input[id="otc"]',
                'input[aria-label*="代码"]',
                'input[placeholder*="代码"]',
                'input[maxlength="6"]'
            ]
            
            code_input = None
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    code_input = element
                    break
                except:
                    continue
            
            if not code_input:
                self._logger.error("未找到短信验证码输入框")
                return False
            
            # 尝试使用TOTP自动生成验证码
            totp_code = self._generate_totp_code()
            
            if totp_code:
                self._logger.info(f"TOTP验证码生成成功: {totp_code}，自动填写...")
                print("\n" + "="*60)
                print("✅ 检测到TOTP Secret Key，自动生成验证码")
                print("="*60 + "\n")
                
                # 自动填写验证码
                await code_input.fill(totp_code)
                
                # 点击验证按钮
                success = await self._submit_mfa_code()
                
                if success:
                    self._logger.info("TOTP验证码验证成功")
                    return True
                else:
                    self._logger.warning("TOTP验证码验证失败，尝试用户手动输入")
                    print("⚠️  自动验证码验证失败，将尝试用户手动输入\n")
            else:
                # 输出提示信息
                print("\n" + "="*60)
                print("⚠️  需要短信验证码验证")
                print("="*60)
                if self._auto_code:
                    print("注意: 已配置auto_code但验证码生成失败")
                    print("请手动输入验证码")
                else:
                    print("未配置TOTP Secret Key (auto_code)")
                    print("请查看手机收到的短信，输入6位验证码")
                print("提示：您有 3 次输入机会")
                print("="*60 + "\n")
            
            # 等待用户输入验证码
            success = await self._wait_for_mfa_input(code_input, max_retries=3)
            
            return success
            
        except Exception as e:
            self._logger.error(f"SMS MFA 处理异常: {e}")
            return False

    async def _handle_email_mfa(self) -> bool:
        """处理邮件验证码 MFA"""
        try:
            self._logger.info("处理 Email 邮件验证码...")
            
            # 等待验证码输入框
            selectors = [
                'input[name="otc"]',
                'input[id="otc"]',
                'input[aria-label*="代码"]',
                'input[placeholder*="代码"]',
                'input[maxlength="6"]'
            ]
            
            code_input = None
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    code_input = element
                    break
                except:
                    continue
            
            if not code_input:
                self._logger.error("未找到邮件验证码输入框")
                return False
            
            # 尝试使用TOTP自动生成验证码
            totp_code = self._generate_totp_code()
            
            if totp_code:
                self._logger.info(f"TOTP验证码生成成功: {totp_code}，自动填写...")
                print("\n" + "="*60)
                print("✅ 检测到TOTP Secret Key，自动生成验证码")
                print("="*60 + "\n")
                
                # 自动填写验证码
                await code_input.fill(totp_code)
                
                # 点击验证按钮
                success = await self._submit_mfa_code()
                
                if success:
                    self._logger.info("TOTP验证码验证成功")
                    return True
                else:
                    self._logger.warning("TOTP验证码验证失败，尝试用户手动输入")
                    print("⚠️  自动验证码验证失败，将尝试用户手动输入\n")
            else:
                # 输出提示信息
                print("\n" + "="*60)
                print("⚠️  需要邮件验证码验证")
                print("="*60)
                if self._auto_code:
                    print("注意: 已配置auto_code但验证码生成失败")
                    print("请手动输入验证码")
                else:
                    print("未配置TOTP Secret Key (auto_code)")
                    print("请查看您的邮箱（包括垃圾邮件），输入6位验证码")
                print("提示：验证码通常在几分钟内送达")
                print("="*60 + "\n")
            
            # 等待用户输入验证码
            success = await self._wait_for_mfa_input(code_input, max_retries=3)
            
            return success
            
        except Exception as e:
            self._logger.error(f"Email MFA 处理异常: {e}")
            return False

    async def _handle_app_mfa(self) -> bool:
        """处理 Authenticator App MFA"""
        try:
            self._logger.info("处理 Authenticator App MFA...")
            
            # 等待验证码输入框
            selectors = [
                'input[name="otc"]',
                'input[id="otc"]',
                'input[aria-label*="代码"]',
                'input[placeholder*="代码"]',
                'input[maxlength="6"]'
            ]
            
            code_input = None
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    code_input = element
                    break
                except:
                    continue
            
            if not code_input:
                self._logger.error("未找到 App 验证码输入框")
                return False
            
            # 尝试使用TOTP自动生成验证码
            totp_code = self._generate_totp_code()
            
            if totp_code:
                self._logger.info(f"TOTP验证码生成成功: {totp_code}，自动填写...")
                print("\n" + "="*60)
                print("✅ 检测到TOTP Secret Key，自动生成验证码")
                print("="*60 + "\n")
                
                # 自动填写验证码
                await code_input.fill(totp_code)
                
                # 点击验证按钮
                success = await self._submit_mfa_code()
                
                if success:
                    self._logger.info("TOTP验证码验证成功")
                    return True
                else:
                    self._logger.warning("TOTP验证码验证失败，尝试用户手动输入")
                    print("⚠️  自动验证码验证失败，将尝试用户手动输入\n")
            else:
                # 输出提示信息
                print("\n" + "="*60)
                print("⚠️  需要 Authenticator App 验证码")
                print("="*60)
                if self._auto_code:
                    print("注意: 已配置auto_code但验证码生成失败")
                    print("请手动输入验证码")
                else:
                    print("未配置TOTP Secret Key (auto_code)")
                    print("请打开 Microsoft Authenticator App")
                    print("输入显示的6位验证码")
                print("提示：验证码每30秒刷新一次")
                print("="*60 + "\n")
            
            # 等待用户输入验证码
            success = await self._wait_for_mfa_input(code_input, max_retries=3)
            
            return success
            
        except Exception as e:
            self._logger.error(f"App MFA 处理异常: {e}")
            return False

    async def _handle_phone_mfa(self) -> bool:
        """处理电话验证 MFA"""
        try:
            self._logger.info("处理 Phone 电话验证 MFA...")
            
            # 电话验证无法自动处理，需要用户手动完成
            print("\n" + "="*60)
            print("⚠️  需要电话验证")
            print("="*60)
            print("请接听来自 Microsoft 的电话")
            print("根据提示按相应数字键完成验证")
            print("提示：最多等待2分钟")
            print("="*60 + "\n")
            
            # 等待验证完成（通过检测成功页面）
            success = await self._wait_for_success_page(timeout=120)
            
            return success
            
        except Exception as e:
            self._logger.error(f"Phone MFA 处理异常: {e}")
            return False

    async def _handle_generic_mfa(self) -> bool:
        """处理通用 MFA（无法识别类型时）"""
        try:
            self._logger.info("处理通用 MFA...")
            
            # 尝试查找验证码输入框
            selectors = [
                'input[name="otc"]',
                'input[id="otc"]',
                'input[aria-label*="代码"]',
                'input[placeholder*="代码"]',
                'input[maxlength="6"]',
                'input[type="tel"]'
            ]
            
            code_input = None
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    code_input = element
                    break
                except:
                    continue
            
            if not code_input:
                self._logger.error("未找到 MFA 验证码输入框")
                return False
            
            # 尝试使用TOTP自动生成验证码
            totp_code = self._generate_totp_code()
            
            if totp_code:
                self._logger.info(f"TOTP验证码生成成功: {totp_code}，自动填写...")
                print("\n" + "="*60)
                print("✅ 检测到TOTP Secret Key，自动生成验证码")
                print("="*60 + "\n")
                
                # 自动填写验证码
                await code_input.fill(totp_code)
                
                # 点击验证按钮
                success = await self._submit_mfa_code()
                
                if success:
                    self._logger.info("TOTP验证码验证成功")
                    return True
                else:
                    self._logger.warning("TOTP验证码验证失败，尝试用户手动输入")
                    print("⚠️  自动验证码验证失败，将尝试用户手动输入\n")
            else:
                # 输出提示信息
                print("\n" + "="*60)
                print("⚠️  需要多因素验证")
                print("="*60)
                if self._auto_code:
                    print("注意: 已配置auto_code但验证码生成失败")
                    print("请手动输入验证码")
                else:
                    print("未配置TOTP Secret Key (auto_code)")
                    print("请根据页面提示完成验证")
                    print("可能是短信、邮件或 Authenticator App 验证码")
                print("="*60 + "\n")
            
            # 等待用户输入验证码
            success = await self._wait_for_mfa_input(code_input, max_retries=3)
            
            return success
            
        except Exception as e:
            self._logger.error(f"通用 MFA 处理异常: {e}")
            return False

    async def _wait_for_mfa_input(
        self,
        code_input,
        max_retries: int = 3
    ) -> bool:
        """
        等待并处理 MFA 验证码输入
        
        参数：
        - code_input: 验证码输入框元素
        - max_retries: 最大输入次数
        
        返回：
        - True: 验证成功
        - False: 验证失败
        """
        for attempt in range(1, max_retries + 1):
            try:
                self._logger.info(f"MFA 验证码输入尝试 {attempt}/{max_retries}")
                
                # 等待用户输入（检查输入框是否有内容）
                await asyncio.sleep(2)  # 给予用户输入时间
                
                # 获取用户输入的验证码
                code = await code_input.input_value()
                
                if not code:
                    self._logger.warning(f"尝试 {attempt}: 验证码为空，等待输入...")
                    continue
                
                if len(code) < 6:
                    self._logger.warning(f"尝试 {attempt}: 验证码长度不足: {len(code)}")
                    await code_input.clear()
                    continue
                
                self._logger.info(f"尝试 {attempt}: 验证码已输入: {code[:3]}***")
                
                # 点击验证按钮
                await self._click_mfa_submit_button()
                
                # 等待验证结果
                await asyncio.sleep(2)
                
                # 检查是否验证成功（检测成功页面）
                if await self._check_mfa_success():
                    self._logger.info("MFA 验证成功")
                    return True
                
                # 检查是否需要重新输入
                if await self._check_mfa_failure():
                    self._logger.warning(f"尝试 {attempt}: 验证码错误")
                    await code_input.clear()
                    print(f"\n⚠️  验证码错误，请重新输入 ({attempt}/{max_retries})\n")
                    continue
                
            except Exception as e:
                self._logger.error(f"尝试 {attempt} 异常: {e}")
                continue
        
        # MFA 验证失败
        self._logger.error(f"MFA 验证失败，已尝试 {max_retries} 次")
        self._mfa_error_code = "MFA_INVALID_CODE"
        return False

    async def _click_mfa_submit_button(self):
        """点击 MFA 验证提交按钮"""
        selectors = [
            'input[type="submit"]',
            'button[type="submit"]',
            'input[id="idSubmit_SAOTCS"]',
            'input[value*="验证"]',
            'button:has-text("验证")'
        ]
        
        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                await element.click(timeout=3000)
                self._logger.info("已点击 MFA 验证提交按钮")
                return
            except:
                continue
        
        self._logger.warning("未找到 MFA 验证提交按钮")

    async def _check_mfa_success(self) -> bool:
        """检查 MFA 是否验证成功"""
        try:
            # 检查成功页面指示器
            success_indicators = [
                'text=大功告成',
                'text=Done',
                'text=Success',
                'text=已成功',
                'text=成功',
                'text=You have signed in'
            ]
            
            for indicator in success_indicators:
                if await self._page.locator(indicator).count() > 0:
                    return True
            
            return False
        except:
            return False

    async def _check_mfa_failure(self) -> bool:
        """检查 MFA 是否验证失败"""
        try:
            # 检查失败页面指示器
            failure_indicators = [
                'text=代码不正确',
                'text=incorrect',
                'text=错误',
                'text=失败',
                'text=验证失败',
                'text=incorrect.*code'
            ]
            
            for indicator in failure_indicators:
                if await self._page.locator(indicator).count() > 0:
                    return True
            
            return False
        except:
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
            self._timer.start("页面导航")
            self._logger.info("[步骤1/6] 导航到验证页面...")
            await self._page.goto(config.verification_url, wait_until='domcontentloaded', timeout=self.PAGE_LOAD_TIMEOUT)
            # 优化：使用智能等待替代固定sleep(2)
            await self._page.wait_for_load_state('domcontentloaded')
            self._timer.end("页面导航")
            self._logger.info("[步骤1/6] 页面导航完成")

            # Step 2: 输入设备码并点击"允许访问"
            self._timer.start("设备码输入")
            self._logger.info("[步骤2/6] 输入设备码...")
            if not await self._handle_device_code_step(config.user_code):
                self._logger.error("[步骤2/6] 设备码步骤失败")
                await self._save_screenshot("device_code_step_failed")
                return False
            self._timer.end("设备码输入")
            self._logger.info("[步骤2/6] 设备码步骤完成")

            # Step 3: 输入邮箱并点击"下一步"
            self._timer.start("邮箱输入")
            self._logger.info("[步骤3/6] 输入邮箱...")
            if not await self._handle_email_step(config.email):
                self._logger.error("[步骤3/6] 邮箱输入步骤失败")
                await self._save_screenshot("email_step_failed")
                return False
            self._timer.end("邮箱输入")
            self._logger.info("[步骤3/6] 邮箱步骤完成")

            # Step 4: 输入密码并点击"登录"
            self._timer.start("密码输入")
            self._logger.info("[步骤4/6] 输入密码...")
            if not await self._handle_password_step(config.password):
                self._logger.error("[步骤4/6] 密码输入步骤失败")
                await self._save_screenshot("password_step_failed")
                return False
            self._timer.end("密码输入")
            self._logger.info("[步骤4/6] 密码步骤完成")

            # Step 4.5: 检测并处理 MFA（多因素认证）
            self._timer.start("MFA验证")
            self._logger.info("[步骤4.5/6] 检测 MFA 多因素认证...")
            
            # 等待页面稳定
            await asyncio.sleep(2)
            
            # 检查是否需要 MFA
            mfa_required = await self._check_mfa_required()
            if mfa_required:
                self._logger.info("[步骤4.5/6] 检测到 MFA 验证...")
                mfa_success = await self._handle_mfa_verification(config)
                if not mfa_success:
                    self._logger.error("[步骤4.5/6] MFA 验证失败")
                    await self._save_screenshot("mfa_verification_failed")
                    self._timer.end("MFA验证")
                    return False
                self._logger.info("[步骤4.5/6] MFA 验证成功")
            else:
                self._logger.info("[步骤4.5/6] 无需 MFA，继续...")
            
            self._timer.end("MFA验证")

            # Step 5: 处理保持登录状态页面
            self._timer.start("保持登录状态")
            self._logger.info("[步骤5/6] 处理保持登录状态页面...")
            await self._handle_keep_signed_in_step()
            self._timer.end("保持登录状态")
            self._logger.info("[步骤5/6] 保持登录状态步骤完成")

            # Step 6: 等待成功页面
            self._timer.start("等待成功页面")
            self._logger.info("[步骤6/6] 等待成功页面...")
            if await self._wait_for_success_page(config.timeout):
                self._timer.end("等待成功页面")
                self._logger.info("[步骤6/6] ✅ 登录成功！")
                return True
            else:
                self._timer.end("等待成功页面")
                self._logger.error("[步骤6/6] ❌ 未检测到成功页面")
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
        
        优化：使用类常量ELEMENT_TIMEOUT替代硬编码的15000
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
                self._logger.debug(f"尝试选择器: {selector}")
                try:
                    element = self._page.locator(selector).first
                    self._logger.debug(f"等待元素可见: {selector}")
                    # 优化：使用类常量替代硬编码的15000
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    self._logger.info(f"填写设备码")
                    await element.fill(user_code)
                    self._logger.info(f"设备码已输入")
                    input_found = True
                    break
                except Exception as e:
                    self._logger.debug(f"选择器 {selector} 失败: {e}")
                    continue

            if not input_found:
                self._logger.error("未找到设备码输入框")
                return False

            # 点击"允许访问"按钮
            self._logger.info("点击'允许访问'按钮...")
            # 优化：移除固定sleep(1)，依赖元素等待
            await self._click_allow_access_button()
            self._logger.info("'_click_allow_access_button()' 执行完成")

            return True

        except Exception as e:
            self._logger.error(f"设备码步骤异常: {e}")
            return False

    async def _click_allow_access_button(self):
        """点击"允许访问"按钮"""
        self._logger.info("开始查找'允许访问'按钮...")
        selectors = [
            'input[type="submit"][value="允许访问"]',
            'input[type="submit"]#idSIButton9',
            'input[type="submit"]',
            'button[type="submit"]'
        ]

        for selector in selectors:
            self._logger.debug(f"尝试按钮选择器: {selector}")
            try:
                element = self._page.locator(selector).first
                count = await element.count()
                self._logger.debug(f"选择器 {selector} 找到 {count} 个元素")
                if count > 0:
                    await element.click()
                    self._logger.info("已点击'允许访问'按钮")
                    # 优化：使用异步等待替代固定sleep(2)
                    await asyncio.sleep(self.SHORT_DELAY / 1000)
                    return
            except Exception as e:
                self._logger.debug(f"按钮选择器 {selector} 失败: {e}")
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
        
        优化：使用类常量ELEMENT_TIMEOUT替代硬编码的15000
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
                    # 优化：使用类常量替代硬编码的15000
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    await element.fill(email)
                    self._logger.info(f"邮箱已输入: {email}")
                    input_found = True
                    break
                except Exception as e:
                    self._logger.debug(f"邮箱选择器 {selector} 失败: {e}")
                    continue

            if not input_found:
                self._logger.error("未找到邮箱输入框")
                return False

            # 点击"下一步"按钮
            # 优化：移除固定sleep(1)，依赖元素等待
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
                    # 优化：使用异步等待替代固定sleep(2)
                    await asyncio.sleep(self.SHORT_DELAY / 1000)
                    return
            except Exception as e:
                self._logger.debug(f"下一步按钮选择器 {selector} 失败: {e}")
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
        
        优化：使用类常量ELEMENT_TIMEOUT替代硬编码的15000
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
                    # 优化：使用类常量替代硬编码的15000
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT, state='visible')
                    await element.fill(password)
                    self._logger.info("密码已输入")
                    input_found = True
                    break
                except Exception as e:
                    self._logger.debug(f"密码选择器 {selector} 失败: {e}")
                    continue

            if not input_found:
                self._logger.error("未找到密码输入框")
                return False

            # 点击"登录"按钮
            # 优化：移除固定sleep(1)，依赖元素等待
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
                    # 优化：使用异步等待替代固定sleep(2)
                    await asyncio.sleep(self.SHORT_DELAY / 1000)
                    return
            except Exception as e:
                self._logger.debug(f"登录按钮选择器 {selector} 失败: {e}")
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
                    # 优化：使用类常量替代硬编码的5000
                    await element.wait_for(timeout=self.ELEMENT_TIMEOUT // 2, state='visible')
                    await element.click()
                    self._logger.info("已点击'是'按钮（保持登录状态）")
                    # 优化：使用异步等待替代固定sleep(2)
                    await asyncio.sleep(self.SHORT_DELAY / 1000)
                    return
                except Exception as e:
                    self._logger.debug(f"保持登录选择器 {selector} 失败: {e}")
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
        
        优化：增加检测频率，减少等待时间
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
            # 优化：减少检测间隔，从2秒缩短到1秒
            check_interval = 1

            while (asyncio.get_event_loop().time() - start_time) < timeout:
                # 检查成功指标
                for indicator in success_indicators:
                    try:
                        if await self._page.locator(indicator).count() > 0:
                            self._logger.info(f"检测到成功标志: {indicator}")
                            # 优化：减少等待时间，从2秒缩短到0.5秒
                            await asyncio.sleep(0.5)
                            return True
                    except Exception as e:
                        self._logger.debug(f"成功指标检测失败 {indicator}: {e}")
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

            if getattr(self, '_playwright', None):
                await self._playwright.stop()
                self._playwright = None

            self._logger.info("浏览器已关闭")

        except Exception as e:
            self._logger.error(f"关闭浏览器失败: {e}")

    async def close(self):
        """公共关闭方法"""
        await self._close_browser()