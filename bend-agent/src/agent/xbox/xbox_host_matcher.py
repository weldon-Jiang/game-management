"""
Xbox 主机智能匹配器
==================

功能说明：
- 通过云端 API 获取流媒体账号授权的 Xbox 主机列表（对齐 streaming/xsplayer.py）
- 自动唤醒待机的 Xbox 主机（云端 Power API）
- 优先选择已开机的 Xbox

匹配策略（v4.0 streaming 风格）：
1. 仅通过 GET /v6/servers/home 获取云端授权列表（必须存在）
2. 指定主机：校验云端授权 → 占用检测 → 唤醒
3. 自动匹配：从云端列表按电源状态筛选，过滤占用后随机选择
4. 不依赖局域网 SSDP / SmartGlass

唤醒策略：
- 使用 Xbox Live 云端 Power API
- 等待 30 秒确认开机成功
- 最多重试 2 次

作者：技术团队
版本：4.0
"""

import asyncio
import random
from typing import Awaitable, Callable, List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

import aiohttp

from ..core.logger import get_logger
from ..gssv.base_uri import DEFAULT_GSSV_BASE_URI, normalize_gssv_base_uri
from ..gssv.device_info import build_x_ms_device_info
from .xbox_discovery import XboxDiscovery, XboxInfo as DiscoveredXboxInfo


class XboxMatchPriority(Enum):
    """Xbox 匹配优先级"""
    AUTHORIZED_ONLINE_POWERED = 1
    AUTHORIZED_ONLINE_STANDBY = 2
    AUTHORIZED_OFFLINE = 3
    UNAUTHORIZED = 99


@dataclass
class XboxInfo:
    """Xbox 主机信息（兼容 task_context.XboxInfo 扩展字段）"""
    id: str = ""
    name: str = ""
    ip_address: str = ""
    live_id: str = ""
    mac_address: str = ""
    device_id: str = ""
    port: int = 5050
    power_state: str = "Unknown"
    console_type: str = "Unknown"
    play_path: str = ""


@dataclass
class XboxMatchResult:
    """Xbox 主机匹配结果"""
    xbox_info: Optional[XboxInfo] = None
    priority: XboxMatchPriority = XboxMatchPriority.UNAUTHORIZED
    is_authorized: bool = False
    is_local_online: bool = False
    is_powered_on: bool = False
    match_reason: str = ""
    success: bool = False
    error_code: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class XboxWakeupResult:
    """Xbox 唤醒结果"""
    success: bool
    xbox_info: XboxInfo
    wakeup_method: str
    attempts: int
    wait_time_seconds: float
    error_message: Optional[str] = None


class XboxHostMatcher:
    """
    Xbox 主机智能匹配器（云端单路径，参考 streaming xsplayer.py）

    使用方式：
    matcher = XboxHostMatcher(gs_token)
    match_result = await matcher.find_best_match(wakeup=True)
    """

    WAKUP_MAX_RETRIES = 2
    WAKUP_WAIT_SECONDS = 30
    WAKUP_CHECK_INTERVAL = 3
    DEFAULT_PLAY_PATH = "v5/sessions/home/play"
    STANDBY_POWER_STATES = frozenset({"Standby", "ConnectedStandby", "Off"})

    def __init__(self, gs_token: str, gssv_base_uri: Optional[str] = None):
        self.logger = get_logger('xbox_matcher')
        self._gs_token = gs_token
        self._gssv_base_uri = normalize_gssv_base_uri(gssv_base_uri)
        self._authorized_xboxes: List[XboxInfo] = []
        self._local_xboxes: Dict[str, XboxInfo] = {}

    @staticmethod
    def _is_powered_on(power_state: str) -> bool:
        return (power_state or "").strip() == "On"

    @classmethod
    def _can_wakeup(cls, power_state: str) -> bool:
        return (power_state or "").strip() in cls.STANDBY_POWER_STATES

    async def discover_authorized_xboxes(self) -> List[XboxInfo]:
        """通过云端 API 获取账号授权的 Xbox 主机列表"""
        self.logger.info("正在获取云端授权的 Xbox 主机列表...")

        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'x-xbl-contract-version': '1',
                'X-MS-Device-Info': build_x_ms_device_info(),
            }

            url = f"{self._gssv_base_uri}/v6/servers/home"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get('results', [])

                        self._authorized_xboxes = []
                        for server in results:
                            server_id = server.get('serverId', '')
                            play_path = server.get('playPath', '') or self.DEFAULT_PLAY_PATH
                            xbox_info = XboxInfo(
                                id=server_id,
                                device_id=server_id,
                                name=server.get('deviceName', 'Xbox'),
                                ip_address="",
                                port=5050,
                                live_id=server.get('liveId', '') or server_id,
                                power_state=server.get('powerState', 'Unknown'),
                                console_type=server.get('consoleType', 'Unknown'),
                                play_path=play_path,
                            )
                            self._authorized_xboxes.append(xbox_info)

                        self.logger.info(f"✓ 获取到 {len(self._authorized_xboxes)} 台授权 Xbox 主机")

                        for xbox in self._authorized_xboxes:
                            self.logger.info(
                                f"  - {xbox.name} ({xbox.device_id[:16]}...): "
                                f"Power={xbox.power_state}, Type={xbox.console_type}, "
                                f"PlayPath={xbox.play_path}"
                            )

                        return self._authorized_xboxes

                    text = await resp.text()
                    self.logger.error(f"获取授权 Xbox 列表失败: {resp.status} - {text}")
                    return []

        except Exception as e:
            self.logger.error(f"获取授权 Xbox 列表异常: {e}", exc_info=True)
            return []

    async def discover_local_xboxes(self) -> Dict[str, XboxInfo]:
        """发现局域网内在线的 Xbox 主机（可选，不参与匹配决策）"""
        self.logger.info("正在发现局域网内的 Xbox 主机（可选，不参与匹配）...")

        try:
            local_xboxes = await self._discover_via_ssdp()

            if not local_xboxes:
                self.logger.warning("SSDP 发现失败，尝试备用扫描...")
                local_xboxes = await self._discover_via_ip_scan()

            self._local_xboxes = {xbox.device_id: xbox for xbox in local_xboxes}

            self.logger.info(f"✓ 发现 {len(self._local_xboxes)} 台本地 Xbox 主机")

            for device_id, xbox in self._local_xboxes.items():
                self.logger.info(f"  - {xbox.name} @ {xbox.ip_address}")

            return self._local_xboxes

        except Exception as e:
            self.logger.error(f"本地 Xbox 发现异常: {e}", exc_info=True)
            return {}

    async def _discover_via_ssdp(self) -> List[XboxInfo]:
        """通过 SSDP 发现 Xbox"""
        discovery = XboxDiscovery()
        devices = await discovery.discover(use_cloud_first=False)
        return [self._from_discovered_xbox(device) for device in devices]

    async def _discover_via_ip_scan(self) -> List[XboxInfo]:
        """通过 IP 扫描发现 Xbox"""
        discovery = XboxDiscovery()
        ips = await discovery._scan_local_network()
        xboxes: List[XboxInfo] = []
        for ip in ips:
            verified = await discovery._verify_xbox_device(ip)
            if verified:
                xboxes.append(XboxInfo(
                    id=verified.get('device_id', ip),
                    device_id=verified.get('device_id', ip),
                    name=verified.get('name', f'Xbox ({ip})'),
                    ip_address=ip,
                    port=verified.get('port', 5050),
                    live_id=verified.get('device_id', ip),
                    power_state=verified.get('power_state', 'On'),
                    console_type=verified.get('console_type', 'Xbox')
                ))
        return xboxes

    def _from_discovered_xbox(self, discovered: DiscoveredXboxInfo) -> XboxInfo:
        """将 XboxDiscovery 结果转换为匹配器本地 XboxInfo。"""
        return XboxInfo(
            id=discovered.device_id,
            device_id=discovered.device_id,
            name=discovered.name,
            ip_address=discovered.ip_address,
            port=discovered.port,
            live_id=discovered.live_id,
            power_state=discovered.power_state,
            console_type=discovered.console_type,
            play_path=discovered.play_path or self.DEFAULT_PLAY_PATH,
        )

    async def find_best_match(
        self,
        assigned_xbox: Optional[XboxInfo] = None,
        check_occupancy: Optional[Callable[[XboxInfo], Awaitable[bool]]] = None,
        wakeup: bool = True,
        wakeup_timeout: int = 30
    ) -> XboxMatchResult:
        """
        查找最优的 Xbox 主机匹配（纯云端路径）

        匹配流程（v4.0）：
        1. 获取云端授权的 Xbox 主机列表（必须至少有一个）
        2. 指定主机：云端授权校验 → 占用校验 → 唤醒
        3. 自动匹配：云端列表筛选电源状态 → 过滤占用 → 随机选择
        """
        self.logger.info("=" * 60)
        self.logger.info("Xbox 主机智能匹配流程（云端单路径）")
        self.logger.info("=" * 60)

        if not self._authorized_xboxes:
            await self.discover_authorized_xboxes()

        if not self._authorized_xboxes:
            self.logger.error("✗ 云端未发现任何已授权的 Xbox 主机")
            return XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.UNAUTHORIZED,
                is_authorized=False,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason="云端未发现已授权的 Xbox 主机",
                error_code="CLOUD_NO_AUTHORIZED",
                error_details={
                    "cloud_authorized_count": 0,
                    "suggestion": "请在 Xbox 应用中添加并授权此流媒体账号"
                }
            )

        self.logger.info(f"✓ 云端发现 {len(self._authorized_xboxes)} 台已授权的 Xbox 主机")

        if assigned_xbox is not None:
            return await self._match_assigned_xbox(
                assigned_xbox,
                check_occupancy=check_occupancy,
                wakeup=wakeup,
                wakeup_timeout=wakeup_timeout,
            )

        return await self._match_auto_xbox(
            check_occupancy=check_occupancy,
            wakeup=wakeup,
            wakeup_timeout=wakeup_timeout,
        )

    async def _match_assigned_xbox(
        self,
        assigned_xbox: XboxInfo,
        check_occupancy: Optional[Callable[[XboxInfo], Awaitable[bool]]],
        wakeup: bool,
        wakeup_timeout: int,
    ) -> XboxMatchResult:
        """校验并匹配任务指定的 Xbox 主机（仅云端授权）。"""
        self.logger.info(
            f"开始校验指定 Xbox: {assigned_xbox.name} "
            f"(id={assigned_xbox.id or assigned_xbox.live_id})"
        )

        cloud_match = self._find_authorized_match(assigned_xbox)
        if cloud_match is None:
            cloud_ids = [f"{x.name}({x.id or x.device_id})" for x in self._authorized_xboxes]
            self.logger.error("✗ 指定的 Xbox 主机不在云端授权列表中")
            return XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.UNAUTHORIZED,
                is_authorized=False,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason="指定的 Xbox 主机不在云端授权列表中",
                error_code="ASSIGNED_NOT_AUTHORIZED",
                error_details={
                    "assigned_xbox_name": assigned_xbox.name,
                    "assigned_xbox_id": assigned_xbox.id or assigned_xbox.live_id or assigned_xbox.mac_address,
                    "cloud_authorized": [{"id": x.id, "name": x.name} for x in self._authorized_xboxes],
                    "suggestion": "请在 Xbox 应用中授权该主机，或使用智能匹配让系统自动选择"
                }
            )

        self.logger.info(f"✓ 指定主机在云端授权列表中: {cloud_match.name}")
        final_xbox = cloud_match

        if check_occupancy is not None:
            try:
                occupied = await check_occupancy(final_xbox)
            except Exception as e:
                self.logger.warning(f"占用检测异常，按未占用处理: {e}")
                occupied = False

            if occupied:
                return XboxMatchResult(
                    xbox_info=None,
                    priority=XboxMatchPriority.AUTHORIZED_ONLINE_POWERED,
                    is_authorized=True,
                    is_local_online=False,
                    is_powered_on=self._is_powered_on(final_xbox.power_state),
                    success=False,
                    match_reason="指定的 Xbox 主机正在被其他串流账号使用",
                    error_code="ASSIGNED_OCCUPIED",
                    error_details={
                        "assigned_xbox_name": final_xbox.name,
                        "assigned_xbox_id": final_xbox.id,
                        "suggestion": "请等待其他任务结束后重试，或重新指派空闲的 Xbox 主机"
                    }
                )
            self.logger.info(f"✓ 指定主机未被占用: {final_xbox.name}")

        wakeup_result_payload = await self._ensure_powered_on(
            final_xbox, wakeup=wakeup, wakeup_timeout=wakeup_timeout
        )
        if not wakeup_result_payload["ok"]:
            return wakeup_result_payload["result"]

        return self._build_success_result(
            final_xbox,
            priority=XboxMatchPriority.AUTHORIZED_ONLINE_POWERED,
            reason="使用指定的 Xbox 主机（云端授权 + 未占用）",
            is_powered_on=self._is_powered_on(final_xbox.power_state),
        )

    async def _match_auto_xbox(
        self,
        check_occupancy: Optional[Callable[[XboxInfo], Awaitable[bool]]],
        wakeup: bool,
        wakeup_timeout: int,
    ) -> XboxMatchResult:
        """自动匹配 Xbox 主机：从云端授权列表筛选后随机选择。"""
        matches = self._build_match_results()
        candidates: List[XboxMatchResult] = [
            m for m in matches
            if m.is_powered_on or (wakeup and self._can_wakeup(m.xbox_info.power_state))
        ]

        if not candidates:
            cloud_count = len(self._authorized_xboxes)
            powered_count = sum(1 for m in matches if m.is_powered_on)
            standby_count = sum(
                1 for m in matches if self._can_wakeup(m.xbox_info.power_state)
            )
            self.logger.error("✗ 没有找到符合电源状态条件的云端授权 Xbox 主机")
            return XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.UNAUTHORIZED,
                is_authorized=True,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason="没有找到可用的云端授权 Xbox 主机",
                error_code="NO_AVAILABLE_HOST",
                error_details={
                    "cloud_authorized_count": cloud_count,
                    "powered_on_count": powered_count,
                    "standby_count": standby_count,
                    "suggestion": "请确保 Xbox 主机已开机或启用自动唤醒后重试"
                }
            )

        available: List[XboxMatchResult] = []
        for candidate in candidates:
            if check_occupancy is None:
                available.append(candidate)
                continue
            try:
                occupied = await check_occupancy(candidate.xbox_info)
            except Exception as e:
                self.logger.warning(f"占用检测异常，按未占用处理: {e}")
                occupied = False
            if occupied:
                self.logger.warning(
                    f"  - {candidate.xbox_info.name} 正在被其他串流账号占用，跳过"
                )
                continue
            available.append(candidate)

        if not available:
            return XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.AUTHORIZED_ONLINE_POWERED,
                is_authorized=True,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason="所有候选 Xbox 主机均被其他串流账号占用",
                error_code="ALL_OCCUPIED",
                error_details={
                    "candidate_count": len(candidates),
                    "occupied_candidates": [
                        {"id": c.xbox_info.id, "name": c.xbox_info.name}
                        for c in candidates
                    ],
                    "suggestion": "请等待其他任务结束或释放主机后再重试"
                }
            )

        if len(available) == 1:
            selected = available[0]
            self.logger.info(f"✓ 唯一可用主机: {selected.xbox_info.name}")
        else:
            selected = random.choice(available)
            self.logger.info(
                f"✓ 从 {len(available)} 台空闲主机中随机选择: {selected.xbox_info.name}"
            )

        wakeup_result_payload = await self._ensure_powered_on(
            selected.xbox_info, wakeup=wakeup, wakeup_timeout=wakeup_timeout
        )
        if not wakeup_result_payload["ok"]:
            return wakeup_result_payload["result"]

        if self._is_powered_on(selected.xbox_info.power_state):
            selected.is_powered_on = True
            selected.priority = XboxMatchPriority.AUTHORIZED_ONLINE_POWERED
        return selected

    async def _ensure_powered_on(
        self,
        xbox: XboxInfo,
        wakeup: bool,
        wakeup_timeout: int,
    ) -> Dict[str, Any]:
        """确保 Xbox 处于开机状态。"""
        if self._is_powered_on(xbox.power_state):
            return {"ok": True}

        if not self._can_wakeup(xbox.power_state):
            return {"ok": True}

        if not wakeup:
            self.logger.warning(f"Xbox {xbox.name} 处于 {xbox.power_state}，但唤醒功能已禁用")
            return {
                "ok": False,
                "result": XboxMatchResult(
                    xbox_info=None,
                    priority=XboxMatchPriority.UNAUTHORIZED,
                    is_authorized=True,
                    is_local_online=False,
                    is_powered_on=False,
                    success=False,
                    match_reason="Xbox 处于待机/关机状态，但唤醒功能已禁用",
                    error_code="WAKEUP_DISABLED",
                    error_details={"xbox_name": xbox.name, "power_state": xbox.power_state}
                )
            }

        self.logger.info(f"Xbox {xbox.name} 处于 {xbox.power_state}，尝试云端唤醒...")
        wakeup_result = await self._wakeup_xbox(xbox, timeout=wakeup_timeout)
        if wakeup_result.success:
            xbox.power_state = "On"
            self.logger.info(f"✓ Xbox 唤醒成功: {xbox.name}")
            return {"ok": True}

        self.logger.error(f"✗ 唤醒失败: {wakeup_result.error_message}")
        return {
            "ok": False,
            "result": XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.UNAUTHORIZED,
                is_authorized=True,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason=f"唤醒 Xbox 失败: {wakeup_result.error_message}",
                error_code="WAKEUP_FAILED",
                error_details={
                    "xbox_name": xbox.name,
                    "error_message": wakeup_result.error_message,
                }
            )
        }

    def _build_success_result(
        self,
        xbox: XboxInfo,
        priority: XboxMatchPriority,
        reason: str,
        is_powered_on: bool,
    ) -> XboxMatchResult:
        """构建成功的匹配结果并打印日志。"""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("Xbox 主机匹配结果")
        self.logger.info("=" * 60)
        self.logger.info(f"✓ 选择: {xbox.name}")
        self.logger.info(f"  设备 ID: {xbox.device_id[:16]}...")
        self.logger.info(f"  主机类型: {xbox.console_type}")
        self.logger.info(f"  电源状态: {xbox.power_state}")
        self.logger.info(f"  PlayPath: {xbox.play_path}")
        self.logger.info(f"  匹配原因: {reason}")
        self.logger.info("=" * 60)
        return XboxMatchResult(
            xbox_info=xbox,
            priority=priority,
            is_authorized=True,
            is_local_online=False,
            is_powered_on=is_powered_on,
            success=True,
            match_reason=reason,
        )

    def _find_authorized_match(self, xbox: XboxInfo) -> Optional[XboxInfo]:
        """在云端授权列表中查找与给定 Xbox 匹配的条目。"""
        candidates_id_keys = [
            (xbox.id or "").strip(),
            (xbox.device_id or "").strip(),
            (xbox.live_id or "").strip(),
            (xbox.mac_address or "").strip(),
        ]
        candidates_id_keys = [k for k in candidates_id_keys if k]

        for authorized in self._authorized_xboxes:
            authorized_keys = [
                (authorized.id or "").strip(),
                (authorized.device_id or "").strip(),
                (authorized.live_id or "").strip(),
            ]
            authorized_keys = [k for k in authorized_keys if k]
            if any(k in authorized_keys for k in candidates_id_keys):
                return authorized

        assigned_name = (xbox.name or "").strip().lower()
        if assigned_name:
            for authorized in self._authorized_xboxes:
                if assigned_name == (authorized.name or "").strip().lower():
                    return authorized

        return None

    def _build_match_results(self) -> List[XboxMatchResult]:
        """基于云端授权列表构建匹配结果。"""
        matches: List[XboxMatchResult] = []

        for authorized_xbox in self._authorized_xboxes:
            is_powered_on = self._is_powered_on(authorized_xbox.power_state)

            if is_powered_on:
                priority = XboxMatchPriority.AUTHORIZED_ONLINE_POWERED
                reason = "云端授权 + 已开机"
            elif self._can_wakeup(authorized_xbox.power_state):
                priority = XboxMatchPriority.AUTHORIZED_ONLINE_STANDBY
                reason = "云端授权 + 待唤醒"
            else:
                priority = XboxMatchPriority.AUTHORIZED_OFFLINE
                reason = "云端授权 + 电源状态不可用"

            match = XboxMatchResult(
                xbox_info=authorized_xbox,
                priority=priority,
                is_authorized=True,
                is_local_online=False,
                is_powered_on=is_powered_on,
                success=True,
                match_reason=reason,
            )
            matches.append(match)

            self.logger.info(
                f"  [{priority.value}] {authorized_xbox.name}: {reason}, "
                f"serverId={authorized_xbox.device_id[:16]}..."
            )

        return matches

    async def _wakeup_xbox(self, xbox: XboxInfo, timeout: int = 30) -> XboxWakeupResult:
        """通过云端 API 唤醒 Xbox 主机"""
        self.logger.info(f"开始唤醒 Xbox: {xbox.name} ({xbox.device_id})")

        start_time = asyncio.get_event_loop().time()
        attempts = 0
        last_error = None

        for attempt in range(self.WAKUP_MAX_RETRIES):
            attempts += 1
            self.logger.info(f"唤醒尝试 {attempt + 1}/{self.WAKUP_MAX_RETRIES}")

            success = await self._wakeup_via_api(xbox.device_id)
            if success:
                self.logger.info("✓ 云端 API 唤醒命令发送成功")
                self.logger.info(f"等待 Xbox 开机（最多 {timeout} 秒）...")

                if await self._wait_for_power_on(xbox.device_id, timeout):
                    elapsed = asyncio.get_event_loop().time() - start_time
                    return XboxWakeupResult(
                        success=True,
                        xbox_info=xbox,
                        wakeup_method="api",
                        attempts=attempts,
                        wait_time_seconds=elapsed,
                    )
                last_error = "等待开机超时"
            else:
                last_error = "唤醒命令发送失败"

        elapsed = asyncio.get_event_loop().time() - start_time
        return XboxWakeupResult(
            success=False,
            xbox_info=xbox,
            wakeup_method="none",
            attempts=attempts,
            wait_time_seconds=elapsed,
            error_message=last_error,
        )

    async def _wakeup_via_api(self, device_id: str) -> bool:
        """通过 Xbox Live API 唤醒"""
        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self._gssv_base_uri}/v6/servers/{device_id}/power"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json={"action": "on"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        self.logger.debug(f"API 唤醒成功: {device_id}")
                        return True
                    text = await resp.text()
                    self.logger.warning(f"API 唤醒失败: {resp.status} - {text}")
                    return False

        except Exception as e:
            self.logger.warning(f"API 唤醒异常: {e}")
            return False

    async def _wait_for_power_on(self, device_id: str, timeout: int) -> bool:
        """等待 Xbox 开机"""
        self.logger.info(f"开始轮询检查电源状态（超时: {timeout}s）...")

        elapsed = 0
        while elapsed < timeout:
            power_state = await self._check_power_state(device_id)

            if power_state == 'On':
                self.logger.info(f"✓ Xbox 已开机！（耗时: {elapsed}s）")
                return True

            self.logger.debug(f"当前电源状态: {power_state}，等待中... ({elapsed}s/{timeout}s)")

            await asyncio.sleep(self.WAKUP_CHECK_INTERVAL)
            elapsed += self.WAKUP_CHECK_INTERVAL

        self.logger.warning(f"等待开机超时（{timeout}s）")
        return False

    async def _check_power_state(self, device_id: str) -> str:
        """检查 Xbox 电源状态"""
        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self._gssv_base_uri}/v6/servers/{device_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('powerState', 'Unknown')
                    return 'Unknown'

        except Exception as e:
            self.logger.debug(f"检查电源状态失败: {e}")
            return 'Unknown'

    def get_authorized_xboxes_summary(self) -> List[Dict[str, Any]]:
        """获取授权 Xbox 主机摘要"""
        return [
            {
                'device_id': xbox.device_id,
                'name': xbox.name,
                'power_state': xbox.power_state,
                'console_type': xbox.console_type,
                'play_path': xbox.play_path,
            }
            for xbox in self._authorized_xboxes
        ]
