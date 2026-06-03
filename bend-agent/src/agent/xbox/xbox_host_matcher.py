"""
Xbox 主机智能匹配器
==================

功能说明：
- 通过云端 API 获取流媒体账号授权的 Xbox 主机列表
- 发现局域网内的 Xbox 主机
- 智能匹配云端授权列表和本地在线主机
- 自动唤醒待机的 Xbox 主机
- 优先选择已开机的 Xbox

匹配策略：
1. 账号授权 + 本地在线 + 已开机 → 最高优先级，直接连接
2. 账号授权 + 本地在线 + 待唤醒 → 次高优先级，自动唤醒
3. 账号授权 + 本地离线 → 低优先级，尝试唤醒
4. 未授权的 Xbox → 不使用

唤醒策略：
- 优先使用 Xbox Live API 唤醒
- 备用 SmartGlass 协议唤醒
- 等待 30 秒确认开机成功
- 最多重试 2 次

作者：技术团队
版本：3.0

版本历史：
- 2.0: 集成 PlaySession 管理和 SDP 握手功能
- 3.0: 优化 Xbox 发现逻辑（云端授权必须存在 + 局域网在线必须存在 + 随机选择）
"""

import asyncio
import json
import random
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import socket

import aiohttp

from ..core.logger import get_logger
from .xbox_discovery import XboxDiscovery, XboxInfo as DiscoveredXboxInfo


def _write_debug_log(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    """Write debug-mode NDJSON logs for session ba0362."""
    try:
        cwd = Path.cwd().resolve()
        log_path = cwd.parent / "debug-ba0362.log" if cwd.name == "bend-agent" else cwd / "debug-ba0362.log"
        payload = {
            "sessionId": "ba0362",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


class XboxMatchPriority(Enum):
    """Xbox 匹配优先级"""
    AUTHORIZED_ONLINE_POWERED = 1
    AUTHORIZED_ONLINE_STANDBY = 2
    AUTHORIZED_OFFLINE = 3
    UNAUTHORIZED = 99


@dataclass
class XboxInfo:
    """Xbox 主机信息
    
    兼容 task_context.XboxInfo 和 XboxHostMatcher 使用的扩展字段
    """
    id: str = ""  # Xbox主机唯一标识（兼容 task_context.XboxInfo）
    name: str = ""
    ip_address: str = ""
    live_id: str = ""
    mac_address: str = ""
    # 扩展字段（XboxHostMatcher 专用）
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
    Xbox 主机智能匹配器
    
    功能：
    1. 获取云端授权的 Xbox 主机列表
    2. 发现本地在线的 Xbox 主机
    3. 智能匹配并返回最优选择
    4. 自动唤醒待机的 Xbox 主机
    
    使用方式：
    matcher = XboxHostMatcher(gs_token)
    match_result = await matcher.find_best_match(wakeup=True)
    """
    
    WAKUP_MAX_RETRIES = 2
    WAKUP_WAIT_SECONDS = 30
    WAKUP_CHECK_INTERVAL = 3
    
    def __init__(self, gs_token: str):
        self.logger = get_logger('xbox_matcher')
        self._gs_token = gs_token
        
        self._authorized_xboxes: List[XboxInfo] = []
        self._local_xboxes: Dict[str, XboxInfo] = {}
    
    async def discover_authorized_xboxes(self) -> List[XboxInfo]:
        """通过云端 API 获取账号授权的 Xbox 主机列表"""
        self.logger.info("正在获取云端授权的 Xbox 主机列表...")
        
        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'x-xbl-contract-version': '1'
            }
            
            url = "https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home"
            
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
                            xbox_info = XboxInfo(
                                id=server_id,  # 兼容 task_context.XboxInfo
                                device_id=server_id,  # XboxHostMatcher 专用
                                name=server.get('deviceName', 'Xbox'),
                                ip_address="",
                                port=5050,
                                live_id=server_id,
                                power_state=server.get('powerState', 'Unknown'),
                                console_type=server.get('consoleType', 'Unknown'),
                                play_path=server.get('playPath', '')
                            )
                            self._authorized_xboxes.append(xbox_info)
                        
                        self.logger.info(f"✓ 获取到 {len(self._authorized_xboxes)} 台授权 Xbox 主机")
                        
                        for xbox in self._authorized_xboxes:
                            self.logger.info(
                                f"  - {xbox.name} ({xbox.device_id[:16]}...): "
                                f"Power={xbox.power_state}, Type={xbox.console_type}"
                            )
                        
                        return self._authorized_xboxes
                    else:
                        text = await resp.text()
                        self.logger.error(f"获取授权 Xbox 列表失败: {resp.status} - {text}")
                        return []
                        
        except Exception as e:
            self.logger.error(f"获取授权 Xbox 列表异常: {e}", exc_info=True)
            return []
    
    async def discover_local_xboxes(self) -> Dict[str, XboxInfo]:
        """发现局域网内在线的 Xbox 主机"""
        self.logger.info("正在发现局域网内的 Xbox 主机...")
        
        try:
            local_xboxes = await self._discover_via_ssdp()
            
            if not local_xboxes:
                self.logger.warning("SSDP 发现失败，尝试备用扫描...")
                local_xboxes = await self._discover_via_ip_scan()
            
            self._local_xboxes = {xbox.device_id: xbox for xbox in local_xboxes}
            # region agent log
            _write_debug_log(
                "H4",
                "xbox_host_matcher.discover_local_xboxes",
                "local_discovery_completed",
                {"localCount": len(self._local_xboxes)},
            )
            # endregion
            
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
        xboxes = [self._from_discovered_xbox(device) for device in devices]
        # region agent log
        _write_debug_log(
            "H4",
            "xbox_host_matcher._discover_via_ssdp",
            "ssdp_discovery_result",
            {"count": len(xboxes), "hasIp": [bool(xbox.ip_address) for xbox in xboxes]},
        )
        # endregion
        return xboxes
    
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
        # region agent log
        _write_debug_log(
            "H4",
            "xbox_host_matcher._discover_via_ip_scan",
            "ip_scan_result",
            {"candidateIpCount": len(ips), "verifiedCount": len(xboxes)},
        )
        # endregion
        return xboxes

    def _from_discovered_xbox(self, discovered: DiscoveredXboxInfo) -> XboxInfo:
        """Convert XboxDiscovery result to matcher-local XboxInfo."""
        return XboxInfo(
            id=discovered.device_id,
            device_id=discovered.device_id,
            name=discovered.name,
            ip_address=discovered.ip_address,
            port=discovered.port,
            live_id=discovered.live_id,
            power_state=discovered.power_state,
            console_type=discovered.console_type,
            play_path=discovered.play_path
        )
    
    async def find_best_match(
        self, 
        wakeup: bool = True,
        wakeup_timeout: int = 30
    ) -> XboxMatchResult:
        """
        查找最优的 Xbox 主机匹配
        
        优化后的匹配流程：
        1. 获取云端授权的 Xbox 主机列表（必须至少有一个）
        2. 发现局域网内的在线 Xbox 主机
        3. 过滤出同时在云端授权和局域网在线的 Xbox 主机（必须至少有一个）
        4. 如果有多个符合条件的主机，随机选择一个
        5. 如果选中的是待机状态且 wakeup=True，自动唤醒
        
        Args:
            wakeup: 是否启用自动唤醒
            wakeup_timeout: 唤醒超时时间（秒）
            
        Returns:
            XboxMatchResult: 包含匹配结果或详细错误信息的对象
        """
        self.logger.info("=" * 60)
        self.logger.info("Xbox 主机智能匹配流程")
        self.logger.info("=" * 60)
        
        # 步骤1: 获取云端授权的 Xbox 主机列表
        if not self._authorized_xboxes:
            await self.discover_authorized_xboxes()
        
        # 步骤1.1: 检查云端是否有授权主机（必须至少有一个）
        if not self._authorized_xboxes:
            self.logger.error("✗ 云端未发现任何已授权的 Xbox 主机")
            self.logger.error("  可能原因：流媒体账号未绑定 Xbox 主机，或账号权限不足")
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
        
        # 步骤2: 发现局域网内的在线 Xbox 主机
        await self.discover_local_xboxes()
        
        # 步骤3: 过滤出同时在云端授权和局域网在线的 Xbox 主机
        matches = await self._build_match_results()
        
        # 筛选出本地在线的主机（已授权且局域网在线）
        local_online_matches = [
            m for m in matches 
            if m.is_local_online and (m.is_powered_on or (wakeup and m.xbox_info.power_state == "Standby"))
        ]
        
        if not local_online_matches:
            # 检查是否有任何已授权但本地离线的主机
            offline_count = sum(1 for m in matches if not m.is_local_online)
            online_count = sum(1 for m in matches if m.is_local_online)
            standby_count = sum(1 for m in matches if m.is_local_online and not m.is_powered_on)
            
            self.logger.error("✗ 没有找到符合条件（云端授权 + 局域网在线）的 Xbox 主机")
            self.logger.error(f"  云端授权: {len(self._authorized_xboxes)} 台")
            self.logger.error(f"  局域网在线: {online_count} 台")
            self.logger.error(f"  待唤醒（局域网在线）: {standby_count} 台")
            self.logger.error(f"  本地离线: {offline_count} 台")
            
            suggestion = "请确保 Xbox 主机已开机并连接到局域网" if offline_count > 0 else "检查网络连接，确保 Xbox 和 PC 在同一局域网"
            self.logger.error(f"  建议：{suggestion}")
            
            return XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.UNAUTHORIZED,
                is_authorized=True,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason="没有找到云端授权且局域网在线的 Xbox 主机",
                error_code="NO_LOCAL_MATCH",
                error_details={
                    "cloud_authorized_count": len(self._authorized_xboxes),
                    "local_online_count": online_count,
                    "local_standby_count": standby_count,
                    "local_offline_count": offline_count,
                    "suggestion": suggestion
                }
            )
        
        self.logger.info(f"✓ 找到 {len(local_online_matches)} 台符合条件（云端授权 + 局域网在线）的 Xbox 主机")
        
        # 步骤4: 随机选择一个主机
        if len(local_online_matches) > 1:
            selected_match = random.choice(local_online_matches)
            self.logger.info(f"  从 {len(local_online_matches)} 台候选主机中随机选择")
        else:
            selected_match = local_online_matches[0]
        
        # 步骤5: 如果是待机状态，自动唤醒
        if selected_match.xbox_info.power_state == "Standby":
            if wakeup:
                self.logger.info(f"Xbox {selected_match.xbox_info.name} 处于待机模式，尝试唤醒...")
                wakeup_result = await self._wakeup_xbox(
                    selected_match.xbox_info,
                    timeout=wakeup_timeout
                )
                
                if wakeup_result.success:
                    selected_match.xbox_info.power_state = "On"
                    selected_match.is_powered_on = True
                    selected_match.match_reason = "已唤醒 + 开机成功"
                    selected_match.priority = XboxMatchPriority.AUTHORIZED_ONLINE_POWERED
                    selected_match.success = True
                    self.logger.info(f"✓ Xbox 唤醒成功: {selected_match.xbox_info.name}")
                else:
                    self.logger.error(f"✗ 唤醒失败: {wakeup_result.error_message}")
                    return XboxMatchResult(
                        xbox_info=None,
                        priority=XboxMatchPriority.UNAUTHORIZED,
                        is_authorized=True,
                        is_local_online=True,
                        is_powered_on=False,
                        success=False,
                        match_reason=f"唤醒 Xbox 失败: {wakeup_result.error_message}",
                        error_code="WAKEUP_FAILED",
                        error_details={
                            "xbox_name": selected_match.xbox_info.name,
                            "error_message": wakeup_result.error_message
                        }
                    )
            else:
                self.logger.warning(f"Xbox {selected_match.xbox_info.name} 处于待机模式，但唤醒功能已禁用")
                return XboxMatchResult(
                    xbox_info=None,
                    priority=XboxMatchPriority.UNAUTHORIZED,
                    is_authorized=True,
                    is_local_online=True,
                    is_powered_on=False,
                    success=False,
                    match_reason="Xbox 处于待机模式，但唤醒功能已禁用",
                    error_code="WAKEUP_DISABLED",
                    error_details={
                        "xbox_name": selected_match.xbox_info.name
                    }
                )
        
        # 记录最终选择
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("Xbox 主机匹配结果")
        self.logger.info("=" * 60)
        self.logger.info(f"✓ 选择: {selected_match.xbox_info.name}")
        self.logger.info(f"  设备 ID: {selected_match.xbox_info.device_id[:16]}...")
        self.logger.info(f"  本地 IP: {selected_match.xbox_info.ip_address}")
        self.logger.info(f"  主机类型: {selected_match.xbox_info.console_type}")
        self.logger.info(f"  电源状态: {selected_match.xbox_info.power_state}")
        self.logger.info(f"  匹配原因: {selected_match.match_reason}")
        self.logger.info("=" * 60)
        
        return selected_match
    
    async def _build_match_results(self) -> List[XboxMatchResult]:
        """构建匹配结果列表"""
        matches = []
        
        for authorized_xbox in self._authorized_xboxes:
            device_id = authorized_xbox.device_id
            local_xbox = self._find_local_match(authorized_xbox)
            is_local_online = local_xbox is not None
            is_powered_on = authorized_xbox.power_state == 'On'
            
            if is_local_online and is_powered_on:
                priority = XboxMatchPriority.AUTHORIZED_ONLINE_POWERED
                reason = "已授权 + 本地在线 + 已开机"
            elif is_local_online and not is_powered_on:
                priority = XboxMatchPriority.AUTHORIZED_ONLINE_STANDBY
                reason = "已授权 + 本地在线 + 待唤醒"
            else:
                priority = XboxMatchPriority.AUTHORIZED_OFFLINE
                reason = "已授权 + 本地离线"
            
            final_xbox = authorized_xbox
            if local_xbox:
                final_xbox.ip_address = local_xbox.ip_address
                final_xbox.port = local_xbox.port
            
            match = XboxMatchResult(
                xbox_info=final_xbox,
                priority=priority,
                is_authorized=True,
                is_local_online=is_local_online,
                is_powered_on=is_powered_on,
                success=True,
                match_reason=reason
            )
            
            matches.append(match)
            
            self.logger.info(
                f"  [{priority.value}] {final_xbox.name}: {reason}, "
                f"IP={final_xbox.ip_address or '未知'}"
            )
        
        return matches

    def _find_local_match(self, authorized_xbox: XboxInfo) -> Optional[XboxInfo]:
        """Find a local Xbox that likely corresponds to the cloud-authorized console."""
        direct = self._local_xboxes.get(authorized_xbox.device_id)
        if direct:
            return direct

        authorized_name = (authorized_xbox.name or "").strip().lower()
        for local in self._local_xboxes.values():
            if authorized_name and authorized_name == (local.name or "").strip().lower():
                return local

        if len(self._authorized_xboxes) == 1 and len(self._local_xboxes) == 1:
            local = next(iter(self._local_xboxes.values()))
            # region agent log
            _write_debug_log(
                "H5",
                "xbox_host_matcher._find_local_match",
                "single_candidate_fallback",
                {"authorizedCount": 1, "localCount": 1, "hasLocalIp": bool(local.ip_address)},
            )
            # endregion
            return local

        # region agent log
        _write_debug_log(
            "H5",
            "xbox_host_matcher._find_local_match",
            "no_local_identity_match",
            {"authorizedCount": len(self._authorized_xboxes), "localCount": len(self._local_xboxes)},
        )
        # endregion
        return None
    
    async def _wakeup_xbox(
        self,
        xbox: XboxInfo,
        timeout: int = 30
    ) -> XboxWakeupResult:
        """唤醒 Xbox 主机"""
        self.logger.info(f"开始唤醒 Xbox: {xbox.name} ({xbox.device_id})")
        
        start_time = asyncio.get_event_loop().time()
        attempts = 0
        last_error = None
        
        for attempt in range(self.WAKUP_MAX_RETRIES):
            attempts += 1
            self.logger.info(f"唤醒尝试 {attempt + 1}/{self.WAKUP_MAX_RETRIES}")
            
            wakeup_method = None
            
            if xbox.ip_address:
                success = await self._wakeup_via_smartglass(xbox)
                if success:
                    wakeup_method = "smartglass"
                    self.logger.info("✓ SmartGlass 唤醒成功")
            
            success = await self._wakeup_via_api(xbox.device_id)
            if success:
                wakeup_method = "api"
                self.logger.info("✓ API 唤醒命令发送成功")
            
            if success or wakeup_method:
                self.logger.info(f"等待 Xbox 开机（最多 {timeout} 秒）...")
                
                if await self._wait_for_power_on(xbox.device_id, timeout):
                    elapsed = asyncio.get_event_loop().time() - start_time
                    return XboxWakeupResult(
                        success=True,
                        xbox_info=xbox,
                        wakeup_method=wakeup_method or "none",
                        attempts=attempts,
                        wait_time_seconds=elapsed
                    )
                else:
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
            error_message=last_error
        )
    
    async def _wakeup_via_api(self, device_id: str) -> bool:
        """通过 Xbox Live API 唤醒"""
        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }
            
            url = f"https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/{device_id}/power"
            
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
                    else:
                        text = await resp.text()
                        self.logger.warning(f"API 唤醒失败: {resp.status} - {text}")
                        return False
                        
        except Exception as e:
            self.logger.warning(f"API 唤醒异常: {e}")
            return False
    
    async def _wakeup_via_smartglass(self, xbox: XboxInfo) -> bool:
        """通过 SmartGlass 协议唤醒"""
        if not xbox.ip_address:
            return False
        
        try:
            SMARTGLASS_PORT = 5050
            
            device_id_bytes = xbox.device_id.encode('utf-8')[:16].ljust(16, b'\x00')
            wakeup_packet = bytes([0] * 16) + device_id_bytes
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(wakeup_packet, (xbox.ip_address, SMARTGLASS_PORT))
            sock.close()
            
            self.logger.debug(f"SmartGlass 唤醒包发送成功: {xbox.ip_address}")
            return True
            
        except Exception as e:
            self.logger.warning(f"SmartGlass 唤醒失败: {e}")
            return False
    
    async def _wait_for_power_on(
        self,
        device_id: str,
        timeout: int
    ) -> bool:
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
            
            url = f"https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/{device_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('powerState', 'Unknown')
                    else:
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
                'local_ip': self._local_xboxes.get(xbox.device_id).ip_address 
                           if self._local_xboxes.get(xbox.device_id) else None
            }
            for xbox in self._authorized_xboxes
        ]
