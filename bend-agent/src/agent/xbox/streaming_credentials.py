"""
Step1 串流授权 → Step2 发现/握手 凭证封装。

对齐 streaming/xsrp.py + libxsrp 在 XblAuth 之后使用的 GSSV 字段：
旧路径用 XblAuth host/port/SessionKey 换 XhomeToken；xblive Step1 直接产出 gs_token
与 gssv_base_uri、server_id、play_path，Step2 经本模块统一读取，不再依赖授权代理三件套。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, TYPE_CHECKING

from ..gssv.base_uri import normalize_gssv_base_uri

if TYPE_CHECKING:
    from ..task.task_context import AgentTaskContext
    from .xbox_host_matcher import XboxInfo

DEFAULT_PLAY_PATH = "v5/sessions/home/play"


class StreamingAuthError(Exception):
    """Step2 启动前凭证校验失败。"""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass
class StreamingAuthCredentials:
    """
    串流授权凭证（Step1 产出 → Step2 消费）。

    字段对照 libxsrp / streaming 账号 CSV：
    - username：xsrp OpenStreaming 唯一键（邮箱）
    - gs_token：XhomeToken / GSSV Bearer（替代 XblAuth 换票结果）
    - gssv_base_uri：region baseUri（ProvisionClient QueryServerList 根地址）
    - server_id / play_path：Step1 预查主机（替代再次 list 后单选）
    - user_hash / xsts_token：LAN SmartGlass 路线额外需要
    """

    username: str
    gs_token: str
    gssv_base_uri: str
    server_id: str = ""
    play_path: str = DEFAULT_PLAY_PATH
    gamer_tag: str = ""
    user_hash: str = ""
    xsts_token: str = ""
    auth_provider: str = "unknown"
    step1_console_preloaded: bool = field(default=False)

    def validate_for_cloud(self) -> Optional[str]:
        """云端 Route B 最低要求；返回错误文案或 None。"""
        if not self.gs_token:
            return "无可用的 gsToken，请重新执行步骤一"
        if not self.gssv_base_uri:
            return "缺少 gssv_base_uri，请重新执行步骤一"
        return None

    def validate_for_lan(self) -> Optional[str]:
        """LAN Route A 在 cloud 校验基础上还需 XSTS。"""
        cloud_err = self.validate_for_cloud()
        if cloud_err:
            return cloud_err
        if not self.xsts_token or not self.user_hash:
            return "缺少 XSTS/userhash，无法 SmartGlass UDP 授权"
        return None

    def gssv_bearer_headers(self) -> dict:
        """GSSV HTTP 请求 Authorization 头。"""
        return {
            "Authorization": f"Bearer {self.gs_token}",
            "Accept": "application/json",
        }


def normalize_server_id(server_id: str) -> str:
    """平台/匹配用 ID（带 XBOX- 前缀）。"""
    normalized = (server_id or "").strip().upper()
    if not normalized:
        return ""
    if not normalized.startswith("XBOX-"):
        normalized = f"XBOX-{normalized}"
    return normalized


def gssv_server_id_for_api(server_id: str) -> str:
    """
    GSSV play/list API 用的 serverId（libxsrp 直接取 JSON serverId，无 XBOX- 前缀）。
    """
    normalized = (server_id or "").strip().upper()
    if normalized.startswith("XBOX-"):
        normalized = normalized[5:]
    return normalized


def resolve_streaming_credentials(context: AgentTaskContext) -> StreamingAuthCredentials:
    """
    从 AgentTaskContext 解析 Step1 串流授权结果。

    优先 xblive_auth（完整预查主机），再合并 xbox_tokens（MSAL / 兼容层）。
    失败时抛出 StreamingAuthError。
    """
    username = (context.streaming_account_email or "").strip()

    xblive = getattr(context, "xblive_auth", None)
    tokens = getattr(context, "xbox_tokens", None)

    gs_token = ""
    gssv_base_uri = ""
    server_id = ""
    play_path = DEFAULT_PLAY_PATH
    gamer_tag = ""
    user_hash = ""
    xsts_token = ""
    provider = "unknown"
    step1_preloaded = False

    if xblive is not None:
        gs_token = getattr(xblive, "gs_token", "") or ""
        gssv_base_uri = getattr(xblive, "gssv_base_uri", "") or ""
        server_id = getattr(xblive, "server_id", "") or ""
        play_path = getattr(xblive, "play_path", "") or DEFAULT_PLAY_PATH
        gamer_tag = getattr(xblive, "gamer_tag", "") or ""
        provider = "xblive"
        step1_preloaded = bool(server_id and play_path)

    if tokens is not None:
        gs_token = gs_token or getattr(tokens, "gs_token", "") or ""
        gssv_base_uri = gssv_base_uri or getattr(tokens, "gssv_base_uri", "") or ""
        server_id = server_id or getattr(tokens, "server_id", "") or ""
        play_path = play_path or getattr(tokens, "play_path", "") or DEFAULT_PLAY_PATH
        gamer_tag = gamer_tag or getattr(tokens, "gamer_tag", "") or ""
        user_hash = user_hash or getattr(tokens, "user_hash", "") or ""
        xsts_token = xsts_token or getattr(tokens, "xsts_token", "") or ""
        if provider == "unknown":
            provider = "msal"
        if not step1_preloaded and server_id and play_path:
            step1_preloaded = True

    creds = StreamingAuthCredentials(
        username=username,
        gs_token=gs_token.strip(),
        gssv_base_uri=normalize_gssv_base_uri(gssv_base_uri),
        server_id=normalize_server_id(server_id),
        play_path=(play_path or DEFAULT_PLAY_PATH).strip(),
        gamer_tag=gamer_tag,
        user_hash=user_hash,
        xsts_token=xsts_token,
        auth_provider=provider,
        step1_console_preloaded=step1_preloaded,
    )

    if not creds.gs_token:
        raise StreamingAuthError(
            "NO_GS_TOKEN",
            "无可用的 gsToken，请重新执行步骤一",
        )

    return creds


def attach_streaming_credentials(context: AgentTaskContext) -> StreamingAuthCredentials:
    """解析并写入 context._streaming_credentials，供 Step2/3 复用。"""
    creds = resolve_streaming_credentials(context)
    context._streaming_credentials = creds
    return creds


def get_streaming_credentials(context: AgentTaskContext) -> StreamingAuthCredentials:
    """读取已附着凭证，否则即时解析。"""
    existing = getattr(context, "_streaming_credentials", None)
    if isinstance(existing, StreamingAuthCredentials):
        return existing
    return attach_streaming_credentials(context)


def prioritize_candidates_by_step1(
    candidates: List[XboxInfo],
    creds: StreamingAuthCredentials,
) -> List[XboxInfo]:
    """
    Step1 已锁定 server_id 时，将匹配主机排到候选列表首位。
    不改变集合成员，仅调整尝试顺序。
    """
    if not creds.step1_console_preloaded or not creds.server_id or not candidates:
        return candidates

    target = normalize_server_id(creds.server_id)
    matched: List[XboxInfo] = []
    rest: List[XboxInfo] = []
    for item in candidates:
        cid = normalize_server_id(getattr(item, "device_id", "") or getattr(item, "id", "") or "")
        if cid == target:
            matched.append(item)
        else:
            rest.append(item)
    if not matched:
        return candidates
    return matched + rest


def apply_play_path_to_candidates(
    candidates: List[XboxInfo],
    creds: StreamingAuthCredentials,
) -> None:
    """将 Step1 play_path 回填到候选（GSSV list 条目可能缺省）。"""
    if not creds.play_path:
        return
    for item in candidates:
        if not getattr(item, "play_path", ""):
            item.play_path = creds.play_path
