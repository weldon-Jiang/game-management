"""Playwright 回退登录（对齐 xblauth xal_redirect_url_web）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

import pyotp
from playwright.async_api import async_playwright, expect

from . import errors as E

logger = logging.getLogger("xblive_oauth_web")


class OAuthWebLogin:
    def __init__(
        self,
        username: str,
        password: str,
        verify: str,
        oauth_authorize_url: str,
        redirect_uri: str,
        headless: bool = True,
    ) -> None:
        self.username = username
        self.password = password
        self.verify = verify or ""
        self.oauth_authorize_url = oauth_authorize_url
        self.redirect_uri = redirect_uri
        self.headless = headless
        self.location: Optional[str] = None

    def _totp_code(self) -> str:
        if not self.verify:
            return ""
        try:
            valid = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567="
            token = "".join(c for c in self.verify if c in valid)
            return pyotp.TOTP(token).now()
        except Exception as exc:
            logger.error("TOTP 生成失败: %s", exc)
            return ""

    async def _on_response(self, response) -> None:
        try:
            if (
                response.url.find("login.live.com") >= 0
                and response.status == 302
                and "location" in response.headers
            ):
                self.location = response.headers["location"]
        except Exception:
            pass

    async def run(self) -> Tuple[Optional[str], int]:
        keyword_failed_username = "找不到"
        keyword_use_password = "使用密码"
        keyword_other_login = "其他登录"
        keyword_failed_password = "密码不是"
        keyword_proof = "验证码"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    channel="msedge",
                    headless=self.headless,
                )
                context = await browser.new_context(locale="zh-CN")
                page = await context.new_page()
                page.on("response", self._on_response)
                await page.goto(
                    self.oauth_authorize_url,
                    timeout=120000,
                    wait_until="domcontentloaded",
                )
                await page.locator("[type=email]").fill(self.username, timeout=3000)
                await page.locator("[type=submit]").click(timeout=60000)
                await page.wait_for_load_state("domcontentloaded", timeout=60000)
                try:
                    if not self.headless:
                        await asyncio.sleep(3.0)
                        await expect(page.get_by_text(keyword_failed_username)).not_to_be_visible(
                            timeout=2000
                        )
                    for label in (keyword_other_login, keyword_use_password):
                        try:
                            await page.locator("[role=button]", has_text=label).click(timeout=2000)
                            await page.wait_for_load_state("domcontentloaded", timeout=60000)
                        except Exception:
                            pass
                    if not self.headless:
                        await expect(page.locator("[type=password]")).to_be_visible(timeout=3000)
                    await page.locator("[type=password]").fill(self.password, timeout=3000)
                    await page.locator("[type=submit]").click(timeout=60000)
                    await page.wait_for_load_state("domcontentloaded", timeout=60000)
                    if not self.headless:
                        await asyncio.sleep(3.0)
                        await expect(page.get_by_text(keyword_failed_password)).not_to_be_visible(
                            timeout=3000
                        )
                    if self.verify and not self.location:
                        for action in (
                            lambda: page.locator("[id=\"iSelectProofAlternate\"]").click(timeout=2000),
                            lambda: page.locator("[role=button]", has_text=keyword_proof).click(
                                timeout=2000
                            ),
                        ):
                            try:
                                await action()
                                await page.wait_for_load_state("domcontentloaded", timeout=3000)
                            except Exception:
                                pass
                        code = self._totp_code()
                        if code:
                            for fill_fn in (
                                lambda: page.locator("[type=tel]").fill(code, timeout=2000),
                                lambda: page.locator("[type=text]").fill(code, timeout=2000),
                            ):
                                try:
                                    await fill_fn()
                                    await page.locator("[type=submit]").click(timeout=120000)
                                    break
                                except Exception:
                                    pass
                            await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    if self.location and self.redirect_uri in self.location:
                        await browser.close()
                        return self.location, E.ERRXS_OK
                    await browser.close()
                    return None, E.ERRXS_XAL_PPSECURE_WEB
                except Exception:
                    await browser.close()
                    return None, E.ERRXS_XAL_MAILBOX
        except Exception as exc:
            logger.error("OAuthWebLogin 异常: %s", exc)
            return None, E.ERRXS_XAL_WEB
