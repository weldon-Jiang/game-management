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
版本：2.0
"""

import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import socket

import aiohttp

from ..core.logger import get_logger


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
class XboxHostMatch:
    """Xbox 主机匹配结果"""
    xbox_info: XboxInfo
    priority: XboxMatchPriority
    is_authorized: bool
    is_local_online: bool
    is_powered_on: bool
    match_reason: str


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
            
            self.logger.info(f"✓ 发现 {len(self._local_xboxes)} 台本地 Xbox 主机")
            
            for device_id, xbox in self._local_xboxes.items():
                self.logger.info(f"  - {xbox.name} @ {xbox.ip_address}")
            
            return self._local_xboxes
            
        except Exception as e:
            self.logger.error(f"本地 Xbox 发现异常: {e}", exc_info=True)
            return {}
    
    async def _discover_via_ssdp(self) -> List[XboxInfo]:
        """通过 SSDP 发现 Xbox"""
        self.logger.debug("SSDP 发现待实现")
        return []
    
    async def _discover_via_ip_scan(self) -> List[XboxInfo]:
        """通过 IP 扫描发现 Xbox"""
        self.logger.debug("IP 扫描发现待实现")
        return []
    
    async def find_best_match(
        self, 
        wakeup: bool = True,
        wakeup_timeout: int = 30
    ) -> Optional[XboxHostMatch]:
        """查找最优的 Xbox 主机匹配"""
        if not self._authorized_xboxes:
            await self.discover_authorized_xboxes()
        
        if not self._authorized_xboxes:
            self.logger.error("没有获取到授权 Xbox 列表")
            return None
        
        await self.discover_local_xboxes()
        
        matches = await self._build_match_results()
        
        if not matches:
            self.logger.warning("没有找到可用的 Xbox 主机")
            return None
        
        matches.sort(key=lambda m: m.priority.value)
        
        best_match = matches[0]
        
        if best_match.priority == XboxMatchPriority.AUTHORIZED_ONLINE_STANDBY:
            if wakeup:
                self.logger.info(f"Xbox {best_match.xbox_info.name} 处于待机模式，尝试唤醒...")
                wakeup_result = await self._wakeup_xbox(
                    best_match.xbox_info,
                    timeout=wakeup_timeout
                )
                
                if wakeup_result.success:
                    best_match.xbox_info.power_state = "On"
                    best_match.is_powered_on = True
                    best_match.match_reason = "已唤醒 + 开机成功"
                    best_match.priority = XboxMatchPriority.AUTHORIZED_ONLINE_POWERED
                else:
                    self.logger.error(f"唤醒失败: {wakeup_result.error_message}")
                    return None
        
        self.logger.info(
            f"✓ 选择: {best_match.xbox_info.name} "
            f"({best_match.match_reason})"
        )
        
        return best_match
    
    async def _build_match_results(self) -> List[XboxHostMatch]:
        """构建匹配结果列表"""
        matches = []
        
        for authorized_xbox in self._authorized_xboxes:
            device_id = authorized_xbox.device_id
            local_xbox = self._local_xboxes.get(device_id)
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
            
            match = XboxHostMatch(
                xbox_info=final_xbox,
                priority=priority,
                is_authorized=True,
                is_local_online=is_local_online,
                is_powered_on=is_powered_on,
                match_reason=reason
            )
            
            matches.append(match)
            
            self.logger.info(
                f"  [{priority.value}] {final_xbox.name}: {reason}, "
                f"IP={final_xbox.ip_address or '未知'}"
            )
        
        return matches
    
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
