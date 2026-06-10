"""
xblive 认证主流程（移植 xblauth.Authenticator.do_authentication 全链路）。

Device Token → SISU authenticate → MSA OAuth (ppSecure) → oauth_token →
SISU authorize → XSTS (gssv) → xHome login → /v6/servers/home 查主机。
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import aiohttp
import pyotp

from . import constants as C
from . import errors as E
from .models import XbliveAuthResult
from .oauth_web import OAuthWebLogin
from .pkce_util import generate_pkce_pair
from .signature import create_signing_key, make_signature, proof_key_dict
from .token_storage import delete_token_doc, load_token_doc, save_token_doc

logger = logging.getLogger("xblive_authenticator")

_EPOCH = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _extract_user_hash(sisu_token: Optional[Dict[str, Any]]) -> str:
    if not sisu_token:
        return ""
    try:
        xui = (
            sisu_token.get("AuthorizationToken", {})
            .get("DisplayClaims", {})
            .get("xui", [])
        )
        if xui:
            return str(xui[0].get("uhs", "") or "")
    except Exception:
        pass
    return ""


def _extract_gamer_tag(sisu_token: Optional[Dict[str, Any]]) -> str:
    if not sisu_token:
        return ""
    try:
        xui = (
            sisu_token.get("AuthorizationToken", {})
            .get("DisplayClaims", {})
            .get("xui", [])
        )
        for item in xui:
            gtg = item.get("gtg")
            if gtg:
                return str(gtg)
    except Exception:
        pass
    return ""


class XbliveAuthenticator:
    """对齐 xblive xblauth.Authenticator 的 Python 实现。"""

    def __init__(
        self,
        email: str,
        password: str,
        verify_code: str = "",
        token_doc: Optional[Dict[str, Any]] = None,
        web_headless: bool = True,
    ) -> None:
        self.username = email
        self.password = password
        self.verify = verify_code or ""
        self.web_headless = web_headless
        self.errno = E.ERRXS_OK
        self.auth_time = _now_ts()

        self.key = create_signing_key()
        self.state = __import__("base64").standard_b64encode(
            str(uuid.uuid4()).encode("ascii")
        ).decode("ascii")
        self.code_verifier, self.code_challenge = generate_pkce_pair()

        self.session: Optional[aiohttp.ClientSession] = None
        self.oauth_authorize_url = ""
        self.getCredentialType_url = ""
        self.ppSecure_url = ""
        self.token_ppft = ""
        self.uaid = ""
        self.cookies_login: Dict[str, Any] = {}
        self.location = ""
        self.session_id = ""
        self.default_type = ""
        self.entropy = ""
        self.credential: Dict[str, Any] = {}

        self.gamer_tag = ""
        self.server_id = ""
        self.play_path = ""
        self.gssv_base_uri = ""

        self.token_device: Optional[Dict[str, Any]] = None
        self.token_device_timepoint = _EPOCH.timestamp()
        self.token_user: Optional[Dict[str, Any]] = None
        self.token_user_timepoint = _EPOCH.timestamp()
        self.token_sisu: Optional[Dict[str, Any]] = None
        self.token_sisu_timepoint = _EPOCH.timestamp()
        self.token_xsts: Optional[Dict[str, Any]] = None
        self.token_xsts_timepoint = _EPOCH.timestamp()
        self.token_xhome: Optional[Dict[str, Any]] = None
        self.token_xhome_timepoint = _EPOCH.timestamp()

        if token_doc:
            self._hydrate_from_doc(token_doc)

    def _hydrate_from_doc(self, doc: Dict[str, Any]) -> None:
        self.gamer_tag = doc.get(C.KEY_GAMER_TAG, "") or self.gamer_tag
        self.server_id = doc.get(C.KEY_SERVER_ID, "") or self.server_id
        self.play_path = doc.get(C.KEY_PLAY_PATH, "") or self.play_path
        self.gssv_base_uri = doc.get(C.KEY_GSSV_BASE_URI, "") or self.gssv_base_uri

        for key, attr, tp_attr in (
            (C.KEY_DEVICE_TOKEN, "token_device", "token_device_timepoint"),
            (C.KEY_USER_TOKEN, "token_user", "token_user_timepoint"),
            (C.KEY_SISU_TOKEN, "token_sisu", "token_sisu_timepoint"),
            (C.KEY_XSTS_TOKEN, "token_xsts", "token_xsts_timepoint"),
            (C.KEY_XHOME_TOKEN, "token_xhome", "token_xhome_timepoint"),
        ):
            if key in doc and doc[key]:
                setattr(self, attr, doc[key])
            time_key = key.replace("_token", "_time").replace("user_token", "user_time")
            if time_key in doc:
                setattr(self, tp_attr, doc[time_key])

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=20, limit_per_host=1, use_dns_cache=False),
            cookie_jar=aiohttp.CookieJar(),
        )
        return self

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        await self.close()

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    def to_token_doc(self) -> Dict[str, Any]:
        return {
            C.KEY_GAMER_TAG: self.gamer_tag,
            C.KEY_SERVER_ID: self.server_id,
            C.KEY_PLAY_PATH: self.play_path,
            C.KEY_GSSV_BASE_URI: self.gssv_base_uri,
            C.KEY_DEVICE_TOKEN: self.token_device,
            C.KEY_DEVICE_TIME: self.token_device_timepoint,
            C.KEY_USER_TOKEN: self.token_user,
            C.KEY_USER_TIME: self.token_user_timepoint,
            C.KEY_SISU_TOKEN: self.token_sisu,
            C.KEY_SISU_TIME: self.token_sisu_timepoint,
            C.KEY_XSTS_TOKEN: self.token_xsts,
            C.KEY_XSTS_TIME: self.token_xsts_timepoint,
            C.KEY_XHOME_TOKEN: self.token_xhome,
            C.KEY_XHOME_TIME: self.token_xhome_timepoint,
            "auth_time": self.auth_time,
            "errno": self.errno,
        }

    async def do_authentication(self) -> int:
        now_tp = _now_ts()
        if self.token_xhome and abs(now_tp - self.token_xhome_timepoint) < C.XHOME_TOKEN_LIFE_SEC:
            logger.info("account %s 复用有效 xhome token", self.username)
            return E.ERRXS_OK
        if self.token_xsts and abs(now_tp - self.token_xsts_timepoint) < C.XSTS_TOKEN_LIFE_SEC:
            logger.info("account %s 从 xsts 刷新 xhome", self.username)
            errno = await self.get_xhome_token()
        elif self.token_user and abs(now_tp - self.token_user_timepoint) < (90 * C.USER_TOKEN_LIFE_SEC):
            logger.info("account %s 从 refresh token 续期", self.username)
            errno = await self.refresh_user_token()
            if errno == E.ERRXS_OAUTH_TOKEN:
                delete_token_doc(self.username)
                errno = await self.get_device_token(True)
        else:
            logger.info("account %s 全量 SISU 认证", self.username)
            errno = await self.get_device_token(True)
        self.errno = errno
        return errno

    async def get_device_token(self, full_process: bool) -> int:
        errno = E.ERRXS_GET_DEVICE_TOKEN
        post_dict = {
            "Properties": {
                "AuthMethod": "ProofOfPossession",
                "DeviceType": "Android",
                "Version": "15.0",
                "Id": "{" + str(uuid.uuid4()) + "}",
                "SerialNumber": "{" + str(uuid.uuid4()) + "}",
                "ProofKey": proof_key_dict(self.key),
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
        }
        body = _json_bytes(post_dict)
        signature_str = make_signature(self.key, "POST", "/device/authenticate", "", body)
        url = "https://device.auth.xboxlive.com/device/authenticate"
        headers = {
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "signature": signature_str,
            "x-xbl-contract-version": "1",
        }
        try:
            async with self.session.post(url, data=body, headers=headers) as resp:
                if resp.status == 200:
                    self.token_device = json.loads(await resp.read())
                    self.token_device_timepoint = _now_ts()
                    errno = E.ERRXS_OK
                else:
                    logger.error("get_device_token HTTP %s", resp.status)
        except Exception as exc:
            logger.error("get_device_token 异常: %s", exc)
        if full_process and errno != E.ERRXS_GET_DEVICE_TOKEN:
            return await self.sisu_authenticate()
        return errno

    async def sisu_authenticate(self) -> int:
        post_dict = {
            "AppId": C.APP_ID,
            "DeviceToken": self.token_device["Token"],
            "Offers": [C.SCOPE],
            "Query": {
                "code_challenge": self.code_challenge,
                "code_challenge_method": "S256",
                "display": "android_phone",
                "state": self.state,
            },
            "RedirectUri": C.REDIRECT_URI,
            "Sandbox": "RETAIL",
            "TitleId": C.TITLE_ID,
            "TokenType": "code",
        }
        body = _json_bytes(post_dict)
        signature_str = make_signature(self.key, "POST", "/authenticate", "", body)
        url = "https://sisu.xboxlive.com/authenticate"
        headers = {
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "Signature": signature_str,
            "X-Xbl-Contract-Version": "1",
        }
        try:
            async with self.session.post(url, data=body, headers=headers) as resp:
                if resp.status == 200:
                    ret_dict = json.loads(await resp.read())
                    self.oauth_authorize_url = ret_dict["MsaOauthRedirect"]
                    self.session_id = resp.headers.get("X-SessionId", "")
                    return await self.xal_redirect_url()
                logger.error("sisu_authenticate HTTP %s", resp.status)
        except Exception as exc:
            logger.error("sisu_authenticate 异常: %s", exc)
        return E.ERRXS_SISU_AUTHENTICATE

    async def xal_redirect_url(self) -> int:
        try:
            errno = await self.oauth_authorize()
            if errno in (
                E.ERRXS_OAUTH_AUTHORIZE,
                E.ERRXS_GET_CREDENTIAL_TYPE,
                E.ERRXS_PPSECURE,
            ):
                return await self.xal_redirect_url_web()
            return errno
        except Exception as exc:
            logger.error("xal_redirect_url 异常: %s", exc)
            return E.ERRXS_OAUTH_AUTHORIZE

    async def oauth_authorize(self) -> int:
        url = self.oauth_authorize_url
        headers = {
            "Host": "login.live.com",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with self.session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status != 200:
                    return E.ERRXS_OAUTH_AUTHORIZE
                html_str = (await resp.read()).decode("utf-8", errors="replace")
                try:
                    pos = html_str.index("https://login.live.com/GetCredentialType.srf?")
                    pos_end = html_str.index(",", pos) - 1
                    self.getCredentialType_url = html_str[pos:pos_end]
                except ValueError:
                    return E.ERRXS_OAUTH_AUTHORIZE
                try:
                    pos = html_str.index("https://login.live.com/ppsecure/post.srf?")
                    pos_end = html_str.index(",", pos) - 1
                    self.ppSecure_url = html_str[pos:pos_end]
                except ValueError:
                    return E.ERRXS_OAUTH_AUTHORIZE
                try:
                    ppft_template = 'type=\\"hidden\\" name=\\"PPFT\\"'
                    pos = html_str.index(ppft_template) + len(ppft_template)
                    ppft_value = 'value=\\"'
                    pos = html_str.index(ppft_value, pos) + len(ppft_value)
                    pos_end = html_str.index('\\"/>', pos)
                    self.token_ppft = html_str[pos:pos_end]
                except ValueError:
                    return E.ERRXS_OAUTH_AUTHORIZE
                self.uaid = resp.cookies["uaid"].value
                for cookie in resp.cookies:
                    self.cookies_login[cookie] = resp.cookies[cookie]
                return await self.get_credential_type()
        except Exception as exc:
            logger.error("oauth_authorize 异常: %s", exc)
        return E.ERRXS_OAUTH_AUTHORIZE

    async def get_credential_type(self) -> int:
        post_dict = {
            "checkPhones": False,
            "country": "",
            "federationFlags": 11,
            "flowToken": self.token_ppft,
            "forceotclogin": False,
            "isCookieBannerShown": False,
            "isExternalFederationDisallowed": False,
            "isFidoSupported": False,
            "isOtherIdpSupported": False,
            "isFederationDisabled": False,
            "isRemoteConnectSupported": False,
            "isRemoteNGCSupported": True,
            "isSignup": False,
            "originalRequest": "",
            "otclogindisallowed": False,
            "uaid": self.uaid,
            "username": self.username,
        }
        headers = {
            "Host": "login.live.com",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": self.oauth_authorize_url,
            "Origin": "https://login.live.com",
            "client-request-id": self.uaid,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) greenlight/2.0.0-beta9 Chrome/106.0.5249.199 "
                "Electron/21.4.4 Safari/537.36"
            ),
        }
        try:
            async with self.session.post(
                self.getCredentialType_url,
                data=_json_bytes(post_dict),
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    self.credential = json.loads(await resp.read())
                    for cookie in resp.cookies:
                        self.cookies_login[cookie] = resp.cookies[cookie]
                    return await self.pp_secure()
                logger.error("get_credential_type HTTP %s", resp.status)
        except Exception as exc:
            logger.error("get_credential_type 异常: %s", exc)
        return E.ERRXS_GET_CREDENTIAL_TYPE

    async def pp_secure(self) -> int:
        headers = {
            "Host": "login.live.com",
            "Origin": "https://login.live.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) greenlight/2.0.0-beta9 Chrome/106.0.5249.199 "
                "Electron/21.4.4 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.oauth_authorize_url,
        }
        post_dict = {
            "ps": 2,
            "psRNGCDefaultType": self.default_type,
            "psRNGCEntropy": self.entropy,
            "psRNGCSLK": "",
            "canary": "",
            "ctx": "",
            "hpgrequestid": "",
            "PPFT": self.token_ppft,
            "PPSX": "Pas",
            "NewUser": 1,
            "FoundMSAs": "",
            "fspost": 0,
            "i21": 0,
            "CookieDisclosure": 0,
            "IsFidoSupported": 0,
            "isSignupPost": 0,
            "isRecoveryAttemptPost": 0,
            "i13": 1,
            "login": self.username,
            "loginfmt": self.username,
            "type": 11,
            "LoginOptions": 1,
            "lrt": "",
            "lrtPartition": "",
            "hisRegion": "",
            "hisScaleUnit": "",
            "passwd": self.password,
        }
        query_str = urllib.parse.urlencode(post_dict, doseq=True)
        init_cookies = {k: v.value for k, v in self.cookies_login.items()}
        try:
            async with aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(),
                cookies=init_cookies,
            ) as login_session:
                async with login_session.post(
                    self.ppSecure_url,
                    data=query_str,
                    headers=headers,
                    allow_redirects=False,
                ) as resp:
                    if resp.status == 302:
                        self.location = resp.headers.get("Location", "")
                        logger.info("ppSecure 获得 redirect: %s", self.username)
                        return await self.get_user_token(C.OAUTH_GRANT_AUTHORIZE)
                    logger.error("ppSecure HTTP %s", resp.status)
        except Exception as exc:
            logger.error("ppSecure 异常: %s", exc)
        return E.ERRXS_PPSECURE

    async def get_user_token(self, grant_type: str) -> int:
        try:
            uri_template = f"{C.REDIRECT_URI}/?"
            pos = self.location.index(uri_template) + len(uri_template)
            params = urllib.parse.parse_qs(
                urllib.parse.unquote_plus(self.location[pos:])
            )
            code_list = params.get("code", [])
            if not code_list:
                return E.ERRXS_OAUTH_TOKEN
            errno = await self.oauth_token(grant_type, code_list[0])
            if errno == E.ERRXS_OK:
                return await self.sisu_authorize()
        except Exception as exc:
            logger.error("get_user_token 异常: %s", exc)
        return E.ERRXS_OAUTH_TOKEN

    async def refresh_user_token(self) -> int:
        refresh = (self.token_user or {}).get(C.KEY_USER_REFRESH, "")
        if not refresh:
            return E.ERRXS_OAUTH_TOKEN
        errno = await self.oauth_token(C.OAUTH_GRANT_REFRESH, refresh)
        if errno != E.ERRXS_OK:
            return E.ERRXS_OAUTH_TOKEN
        errno = await self.get_device_token(False)
        if errno != E.ERRXS_OK:
            return errno
        return await self.sisu_authorize()

    async def oauth_token(self, grant_type: str, code: str) -> int:
        url = "https://login.live.com/oauth20_token.srf"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-store, must-revalidate, no-cache",
        }
        if grant_type == C.OAUTH_GRANT_AUTHORIZE:
            post_dict = {
                "grant_type": grant_type,
                "code": code,
                "code_verifier": self.code_verifier,
                "client_id": C.APP_ID,
                "redirect_uri": C.REDIRECT_URI,
                "scope": C.SCOPE,
            }
        elif grant_type == C.OAUTH_GRANT_REFRESH:
            post_dict = {
                "grant_type": grant_type,
                "client_id": C.APP_ID,
                "scope": C.SCOPE,
                "refresh_token": code,
            }
        else:
            return E.ERRXS_OAUTH_TOKEN
        try:
            async with self.session.post(
                url,
                data=urllib.parse.urlencode(post_dict),
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    self.token_user = json.loads(await resp.read())
                    self.token_user_timepoint = _now_ts()
                    return E.ERRXS_OK
                logger.error("oauth_token HTTP %s", resp.status)
        except Exception as exc:
            logger.error("oauth_token 异常: %s", exc)
        return E.ERRXS_OAUTH_TOKEN

    async def sisu_authorize(self) -> int:
        access = (self.token_user or {}).get(C.KEY_USER_ACCESS, "")
        post_dict = {
            "AccessToken": f"t={access}",
            "AppId": C.APP_ID,
            "DeviceToken": self.token_device["Token"],
            "ProofKey": proof_key_dict(self.key),
            "Sandbox": "RETAIL",
            "SiteName": "user.auth.xboxlive.com",
            "UseModernGamertag": True,
        }
        if self.session_id:
            post_dict["SessionId"] = self.session_id
        body = _json_bytes(post_dict)
        signature_str = make_signature(self.key, "POST", "/authorize", "", body)
        url = "https://sisu.xboxlive.com/authorize"
        headers = {
            "Signature": signature_str,
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-store, must-revalidate, no-cache",
        }
        try:
            async with self.session.post(url, data=body, headers=headers) as resp:
                if resp.status == 200:
                    self.token_sisu = json.loads(await resp.read())
                    self.token_sisu_timepoint = _now_ts()
                    self.gamer_tag = _extract_gamer_tag(self.token_sisu) or self.gamer_tag
                    return await self.xsts_authorize()
                logger.error("sisu_authorize HTTP %s", resp.status)
        except Exception as exc:
            logger.error("sisu_authorize 异常: %s", exc)
        return E.ERRXS_SISU_AUTHORIZE

    async def xsts_authorize(self) -> int:
        user_tok = (self.token_sisu or {}).get("UserToken", {}).get("Token", "")
        post_dict = {
            "RelyingParty": "http://gssv.xboxlive.com/",
            "TokenType": "JWT",
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [user_tok]},
        }
        body = _json_bytes(post_dict)
        signature_str = make_signature(self.key, "POST", "/xsts/authorize", "", body)
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        headers = {
            "Signature": signature_str,
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-store, must-revalidate, no-cache",
        }
        try:
            async with self.session.post(url, data=body, headers=headers) as resp:
                if resp.status == 200:
                    self.token_xsts = json.loads(await resp.read())
                    self.token_xsts_timepoint = _now_ts()
                    return await self.get_xhome_token()
                logger.error("xsts_authorize HTTP %s", resp.status)
        except Exception as exc:
            logger.error("xsts_authorize 异常: %s", exc)
        return E.ERRXS_XSTS_AUTHORIZE

    async def get_xhome_token(self) -> int:
        post_dict = {
            "offeringId": "xhome",
            "token": self.token_xsts["Token"],
        }
        body = _json_bytes(post_dict)
        url = "https://xhome.gssv-play-prod.xboxlive.com/v2/login/user"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "x-gssv-client": "XboxComBrowser",
        }
        try:
            async with self.session.post(url, data=body, headers=headers) as resp:
                if resp.status == 200:
                    self.token_xhome = json.loads(await resp.read())
                    self.token_xhome_timepoint = _now_ts()
                    return await self.get_xhome_console(self.token_xhome)
                logger.error("get_xhome_token HTTP %s", resp.status)
        except Exception as exc:
            logger.error("get_xhome_token 异常: %s", exc)
        return E.ERRXS_XHOME_GET_TOKEN

    async def get_xhome_console(self, xhome_portal: Dict[str, Any]) -> int:
        console_urls = []
        try:
            regions = (
                (xhome_portal.get("offeringSettings") or {}).get("regions") or []
            )
            for region in regions:
                if region.get("isDefault") and region.get("baseUri"):
                    console_urls.append(region["baseUri"])
                    self.gssv_base_uri = region["baseUri"]
            gs_token = (self.token_xhome or {}).get("gsToken", "")
            for console_url in console_urls:
                url = f"{console_url.rstrip('/')}/v6/servers/home"
                req_headers = {
                    "Accept": "*/*",
                    "Authorization": f"Bearer {gs_token}",
                    "Host": console_url.replace("https://", "").split("/")[0],
                }
                try:
                    async with self.session.get(url, headers=req_headers) as resp:
                        if resp.status != 200:
                            continue
                        ret_dict = json.loads(await resp.read())
                        total = ret_dict.get("totalItems", 0)
                        if total <= 0:
                            return E.ERRXS_QUERY_XHOME_SERVER_EMPTY
                        if total > 1:
                            return E.ERRXS_QUERY_XHOME_SERVER_TOO_MUCH
                        results = ret_dict.get("results") or []
                        if not results:
                            return E.ERRXS_QUERY_XHOME_SERVER_EMPTY
                        self.play_path = results[0].get("playPath", "")
                        self.server_id = results[0].get("serverId", "")
                        if self.server_id and self.play_path:
                            return E.ERRXS_OK
                        return E.ERRXS_QUERY_XHOME_SERVER_EMPTY
                except Exception as exc:
                    logger.error("xhome_query_console %s: %s", url, exc)
        except Exception as exc:
            logger.error("get_xhome_console 异常: %s", exc)
        return E.ERRXS_XHOME_QUERY_CONSOLE

    async def xal_redirect_url_web(self) -> int:
        web = OAuthWebLogin(
            username=self.username,
            password=self.password,
            verify=self.verify,
            oauth_authorize_url=self.oauth_authorize_url,
            redirect_uri=C.REDIRECT_URI,
            headless=self.web_headless,
        )
        location, errno = await web.run()
        if errno != E.ERRXS_OK or not location:
            return errno
        self.location = location
        return await self.get_user_token(C.OAUTH_GRANT_AUTHORIZE)

    def build_result(self) -> Optional[XbliveAuthResult]:
        if self.errno != E.ERRXS_OK or not self.token_xhome:
            return None
        gs_token = self.token_xhome.get("gsToken", "")
        if not gs_token:
            return None
        remaining = int(
            C.XHOME_TOKEN_LIFE_SEC
            - abs(math.floor(_now_ts() - self.token_xhome_timepoint))
        )
        user_hash = _extract_user_hash(self.token_sisu)
        xsts_raw = (self.token_xsts or {}).get("Token", "")
        return XbliveAuthResult(
            gs_token=gs_token,
            server_id=self.server_id,
            play_path=self.play_path,
            gamer_tag=self.gamer_tag,
            gssv_base_uri=self.gssv_base_uri,
            xhome_token=dict(self.token_xhome),
            token_life_sec=max(0, remaining),
            errno=self.errno,
            token_bundle=self.to_token_doc(),
        )


async def authenticate_account(
    email: str,
    password: str,
    verify_code: str = "",
    *,
    force_full: bool = False,
    web_headless: bool = True,
) -> Tuple[int, Optional[XbliveAuthResult]]:
    """
    执行 xblive 认证；成功时持久化 token 缓存。

    返回 (errno, XbliveAuthResult|None)。
    """
    token_doc = None if force_full else load_token_doc(email)
    async with XbliveAuthenticator(
        email,
        password,
        verify_code,
        token_doc=token_doc,
        web_headless=web_headless,
    ) as auth:
        errno = await auth.do_authentication()
        if errno == E.ERRXS_OK:
            save_token_doc(email, auth.to_token_doc())
            return errno, auth.build_result()
        save_token_doc(email, auth.to_token_doc())
        return errno, None
