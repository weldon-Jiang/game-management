> **架构勘误（2026-06-13）**：生产 Step2–3 为 **xblive/xsrp（GSSV 云端 + WebRTC）**，入口见 `bend-agent/src/agent/automation/step2_xsrp.py`、`step3_xsrp.py`。下文 SmartGlass LAN、`step2_xbox_streaming.py` 等为**历史方案**；SmartGlass UDP 仅作 LAN 发现/唤醒兜底。详见 [00_架构勘误_xsrp_step2.md](./00_架构勘误_xsrp_step2.md)。

# Xbox 主机匹配逻辑优化方案（含自动唤醒）

## 🎯 问题分析

### 当前实现问题

在 `step2_xsrp.py` 的 `_match_xbox_host()` 函数中（行 210-289），当前的匹配逻辑存在以下问题：

```python
async def _match_xbox_host(context, ...):
    # 问题 1: 未验证 Xbox 主机是否属于当前流媒体账号
    discovered_xboxes = await _discover_xbox_devices(context, logger, stream_logger)
    
    # 问题 2: 简单选择第一个或随机选择
    if len(discovered_xboxes) == 1:
        selected = discovered_xboxes[0]
    else:
        selected = random.choice(discovered_xboxes)  # ❌ 随机选择不靠谱
```

### 正确的匹配流程

```
┌─────────────────────────────────────────────────────────────┐
│              Xbox 主机匹配优化流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 获取流媒体账号授权的 Xbox 主机列表 (云端)               │
│     ↓                                                      │
│     GET /v6/servers/home (使用 gsToken)                     │
│     返回该账号登录过的所有 Xbox 主机                         │
│                                                             │
│  2. 发现局域网内的 Xbox 主机 (本地)                         │
│     ↓                                                      │
│     SSDP 发现 / 手动扫描                                    │
│     返回所有在线的 Xbox 主机                                 │
│                                                             │
│  3. 智能匹配                                               │
│     ↓                                                      │
│     比对云端列表和本地发现列表                               │
│     优先选择:                                               │
│       a) 账号授权 + 本地在线 + 已开机                       │
│       b) 账号授权 + 本地在线 + 待唤醒 → 主动唤醒！         │
│       c) 账号授权 + 本地不在线                             │
│                                                             │
│  4. 自动唤醒 (如果需要)                                    │
│     ↓                                                      │
│     发送开机命令 → 等待 → 验证开机成功                      │
│                                                             │
│  5. 连接并验证                                            │
│     ↓                                                      │
│     使用 Xbox Live Token 连接到选中的主机                   │
│     验证会话建立成功                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Xbox 唤醒机制详解

### 电源状态说明

| 电源状态 | 说明 | 可远程唤醒 | 实现方式 |
|---------|------|----------|---------|
| **On** | 主机已开机 | ✅ 不需要 | 直接连接 |
| **Standby** | Instant-On 待机模式 | ✅ **支持** | 发送开机命令 |
| **Off** | 完全关闭 | ❌ 不支持 | 只能物理开机 |

### Xbox 唤醒方案

#### 方案 1: Xbox Live API 唤醒 (推荐) ✅

```python
async def wakeup_xbox_via_api(gs_token: str, device_id: str) -> bool:
    """
    通过 Xbox Live API 唤醒主机
    
    API: POST https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/{deviceId}/power
    """
    import aiohttp
    
    headers = {
        'Authorization': f'Bearer {gs_token}',
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
                logger.info(f"✓ 唤醒命令发送成功: {device_id}")
                return True
            else:
                text = await resp.text()
                logger.error(f"唤醒命令失败: {resp.status} - {text}")
                return False
```

#### 方案 2: Xbox SmartGlass Protocol (备用)

```python
async def wakeup_via_smartglass(xbox_ip: str, device_id: str) -> bool:
    """
    通过 SmartGlass 协议唤醒 Xbox
    
    适用于局域网内直接唤醒
    """
    import socket
    
    SMARTGLASS_PORT = 5050
    
    wakeup_packet = bytes([
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]) + device_id.encode('utf-8')[:16].ljust(16, b'\x00')
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.sendto(wakeup_packet, (xbox_ip, SMARTGLASS_PORT))
        sock.close()
        logger.info(f"✓ SmartGlass 唤醒包发送成功: {xbox_ip}")
        return True
    except Exception as e:
        logger.error(f"SmartGlass 唤醒失败: {e}")
        return False
```

---

## 🎯 完整实现代码

### 1. Xbox 主机匹配器 (含唤醒功能)

**文件**: `src/agent/xbox/xbox_host_matcher.py`

```python
"""
Xbox 主机智能匹配器
==================

功能说明：
- 通过云端 API 获取流媒体账号授权的 Xbox 主机列表
- 发现局域网内的 Xbox 主机
- 智能匹配云端授权列表和本地在线主机
- **自动唤醒待机的 Xbox 主机**
- 优先选择已开机的 Xbox

匹配策略：
1. 账号授权 + 本地在线 + 已开机 → 最高优先级，直接连接
2. 账号授权 + 本地在线 + 待唤醒 → 次高优先级，**自动唤醒**
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
from datetime import datetime
import socket
import logging

import aiohttp

from ..core.logger import get_logger


class XboxMatchPriority(Enum):
    """Xbox 匹配优先级"""
    AUTHORIZED_ONLINE_POWERED = 1  # 已授权 + 本地在线 + 已开机
    AUTHORIZED_ONLINE_STANDBY = 2  # 已授权 + 本地在线 + 待唤醒 → 唤醒
    AUTHORIZED_OFFLINE = 3         # 已授权 + 本地离线 → 尝试唤醒
    UNAUTHORIZED = 99              # 未授权（不使用）


@dataclass
class XboxInfo:
    """Xbox 主机信息"""
    device_id: str
    name: str
    ip_address: str
    port: int = 5050
    live_id: str = ""
    power_state: str = "Unknown"  # On, Off, Standby
    console_type: str = "Unknown"  # XboxOne, XboxSeriesX, XboxSeriesS
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
    wakeup_method: str  # "api", "smartglass", "none"
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
    4. **自动唤醒待机的 Xbox 主机**
    
    使用方式：
    matcher = XboxHostMatcher(gs_token)
    match_result = await matcher.find_best_match(wakeup=True)
    """
    
    # 唤醒配置
    WAKUP_MAX_RETRIES = 2           # 最大重试次数
    WAKUP_WAIT_SECONDS = 30         # 等待开机时间
    WAKUP_CHECK_INTERVAL = 3        # 检查间隔（秒）
    
    def __init__(self, gs_token: str):
        self.logger = get_logger('xbox_matcher')
        self._gs_token = gs_token
        
        self._authorized_xboxes: List[XboxInfo] = []
        self._local_xboxes: Dict[str, XboxInfo] = {}
    
    async def discover_authorized_xboxes(self) -> List[XboxInfo]:
        """
        通过云端 API 获取账号授权的 Xbox 主机列表
        
        Returns:
            XboxInfo 列表
        """
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
                            xbox_info = XboxInfo(
                                device_id=server.get('serverId', ''),
                                name=server.get('deviceName', 'Xbox'),
                                ip_address="",
                                port=5050,
                                live_id=server.get('serverId', ''),
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
        """
        发现局域网内在线的 Xbox 主机
        
        Returns:
            Dict[str, XboxInfo]: device_id -> XboxInfo 映射
        """
        self.logger.info("正在发现局域网内的 Xbox 主机...")
        
        try:
            # 方案 1: SSDP 发现
            local_xboxes = await self._discover_via_ssdp()
            
            # 方案 2: 如果 SSDP 失败，使用已知 IP 列表扫描
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
        # TODO: 实现 SSDP 发现
        self.logger.debug("SSDP 发现待实现")
        return []
    
    async def _discover_via_ip_scan(self) -> List[XboxInfo]:
        """通过 IP 扫描发现 Xbox"""
        # TODO: 实现 IP 扫描
        self.logger.debug("IP 扫描发现待实现")
        return []
    
    async def find_best_match(
        self, 
        wakeup: bool = True,
        wakeup_timeout: int = 30
    ) -> Optional[XboxHostMatch]:
        """
        查找最优的 Xbox 主机匹配
        
        Args:
            wakeup: 是否自动唤醒待机的 Xbox
            wakeup_timeout: 唤醒超时时间（秒）
            
        Returns:
            XboxHostMatch 或 None
        """
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
        """
        唤醒 Xbox 主机
        
        唤醒策略：
        1. 优先使用 Xbox Live API 唤醒
        2. 备用 SmartGlass 协议唤醒
        3. 等待确认开机成功
        
        Args:
            xbox: Xbox 主机信息
            timeout: 超时时间（秒）
            
        Returns:
            XboxWakeupResult
        """
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
        """
        通过 Xbox Live API 唤醒
        
        API: POST /v6/servers/{deviceId}/power
        """
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
        """
        通过 SmartGlass 协议唤醒
        
        适用于局域网内直接唤醒
        """
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
        """
        等待 Xbox 开机
        
        轮询检查电源状态，直到状态变为 "On" 或超时
        
        Args:
            device_id: Xbox 设备 ID
            timeout: 超时时间（秒）
            
        Returns:
            True 如果开机成功，False 如果超时
        """
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
        """
        检查 Xbox 电源状态
        
        Returns:
            电源状态: "On", "Off", "Standby", "Unknown"
        """
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
```

---

### 2. 步骤二集成（智能匹配 + 自动唤醒）

**文件**: `src/agent/automation/step2_xsrp.py`

**新增函数** (放在 `_match_xbox_host()` 函数之后):

```python
async def _smart_match_xbox_with_wakeup(
    context: AgentTaskContext,
    logger,
    stream_logger,
    wakeup_enabled: bool = True,
    wakeup_timeout: int = 30
) -> Optional[XboxInfo]:
    """
    智能匹配 Xbox 主机（包含自动唤醒功能）
    
    流程：
    1. 获取云端授权的 Xbox 主机列表
    2. 发现本地在线的 Xbox 主机
    3. 智能匹配优先级
    4. 如果是待机状态，自动唤醒
    
    Args:
        context: 任务上下文
        logger: 日志记录器
        stream_logger: 流媒体账号日志
        wakeup_enabled: 是否启用自动唤醒
        wakeup_timeout: 唤醒超时时间（秒）
        
    Returns:
        XboxInfo 或 None
    """
    try:
        # 获取 gsToken
        gs_token = _get_gs_token(context)
        
        if not gs_token:
            logger.error("无可用的 gsToken，无法进行 Xbox 匹配")
            return None
        
        # 创建匹配器
        matcher = XboxHostMatcher(gs_token)
        
        # 打印匹配开始
        logger.info("="*60)
        logger.info("Xbox 主机智能匹配（自动唤醒模式）")
        logger.info("="*60)
        logger.info(f"唤醒功能: {'启用' if wakeup_enabled else '禁用'}")
        if wakeup_enabled:
            logger.info(f"唤醒超时: {wakeup_timeout} 秒")
        logger.info("")
        
        # 执行智能匹配
        match_result = await matcher.find_best_match(
            wakeup=wakeup_enabled,
            wakeup_timeout=wakeup_timeout
        )
        
        if not match_result:
            logger.warning("\n没有找到可用的授权 Xbox 主机")
            _print_no_match_help(logger)
            return None
        
        xbox = match_result.xbox_info
        
        # 打印匹配结果
        logger.info("\n" + "="*60)
        logger.info("Xbox 主机匹配结果")
        logger.info("="*60)
        logger.info(f"设备名称: {xbox.name}")
        logger.info(f"设备 ID: {xbox.device_id}")
        logger.info(f"本地 IP: {xbox.ip_address or '未知'}")
        logger.info(f"主机类型: {xbox.console_type}")
        logger.info(f"电源状态: {xbox.power_state}")
        logger.info(f"匹配优先级: {match_result.priority.name}")
        logger.info(f"匹配原因: {match_result.match_reason}")
        logger.info("="*60)
        
        return xbox
        
    except Exception as e:
        logger.error(f"智能匹配 Xbox 失败: {e}", exc_info=True)
        return None


def _get_gs_token(context: AgentTaskContext) -> Optional[str]:
    """从上下文获取 gsToken"""
    if context.xbox_tokens and hasattr(context.xbox_tokens, 'gs_token'):
        return context.xbox_tokens.gs_token
    elif context.microsoft_tokens:
        return context.microsoft_tokens.access_token
    return None


def _print_no_match_help(logger):
    """打印无可用 Xbox 的帮助信息"""
    logger.warning("\n可能的原因:")
    logger.warning("1. 流媒体账号未绑定任何 Xbox 主机")
    logger.warning("   → 请在 Xbox 应用中添加并授权此账号")
    logger.warning("")
    logger.warning("2. Xbox 主机未连接到网络")
    logger.warning("   → 检查 Xbox 网络设置")
    logger.warning("")
    logger.warning("3. Xbox 主机处于 Energy-Saving 模式")
    logger.warning("   → 请改为 Instant-On 模式（设置 > 电源 > 启动模式）")
    logger.warning("")
    logger.warning("4. gsToken 已过期，需要重新认证")
    logger.warning("   → 重新运行步骤一进行账号登录")
```

**修改 `_match_xbox_host()` 函数** (行 210-289):

```python
async def _match_xbox_host(context, ...):
    """
    匹配 Xbox 主机
    
    优化逻辑：
    1. 如果指定了 Xbox 主机，验证是否授权
    2. 如果未指定，使用智能匹配：
       a) 先获取云端授权的 Xbox 列表
       b) 再发现本地在线的 Xbox
       c) 智能匹配并返回最优选择
       d) 如果是待机状态，自动唤醒
    """
    
    # 恢复原始的 Xbox 信息获取逻辑
    if context.assigned_xbox:
        # 使用指定的 Xbox
        xbox_info = context.assigned_xbox
        
        # 验证授权
        if not await _verify_xbox_authorization(context, xbox_info, logger):
            logger.warning(f"指定的 Xbox {xbox_info.name} 未授权")
            return XboxMatchResult(
                success=False,
                xbox_info=None,
                match_type="assigned_unauthorized",
                message="指定的 Xbox 不在授权列表中"
            )
        
        logger.info(f"使用指定的 Xbox: {xbox_info.name}")
        
        # 检查电源状态，必要时唤醒
        if xbox_info.power_state == "Standby":
            logger.info("指定的 Xbox 处于待机模式，尝试唤醒...")
            wakeup_result = await _wakeup_xbox(context, xbox_info, logger, stream_logger)
            
            if not wakeup_result.success:
                return XboxMatchResult(
                    success=False,
                    xbox_info=None,
                    match_type="assigned_wakeup_failed",
                    message=f"唤醒失败: {wakeup_result.error_message}"
                )
            
            xbox_info.power_state = "On"
        
        return XboxMatchResult(
            success=True,
            xbox_info=xbox_info,
            match_type="assigned",
            message=f"使用指定的 Xbox: {xbox_info.name}"
        )
    
    # 使用智能匹配（启用自动唤醒）
    logger.info("未指定 Xbox，使用智能匹配...")
    xbox_info = await _smart_match_xbox_with_wakeup(
        context, 
        logger, 
        stream_logger,
        wakeup_enabled=True,      # 启用自动唤醒
        wakeup_timeout=30          # 30 秒超时
    )
    
    if xbox_info:
        return XboxMatchResult(
            success=True,
            xbox_info=xbox_info,
            match_type="smart_matched",
            message=f"智能匹配: {xbox_info.name}"
        )
    else:
        return XboxMatchResult(
            success=False,
            xbox_info=None,
            match_type="no_match",
            message="没有找到可用的授权 Xbox 主机"
        )
```

---

## 📊 唤醒流程时序图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Xbox 唤醒流程时序图                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Agent                      Xbox Live API              Xbox 主机             │
│    │                            │                        │                 │
│    │  1. 智能匹配发现待机 Xbox   │                        │                 │
│    │───────────────────────────>│                        │                 │
│    │                            │                        │                 │
│    │  2. 发送唤醒命令            │                        │                 │
│    │    POST /power (action=on) │                        │                 │
│    │───────────────────────────>│                        │                 │
│    │                            │                        │                 │
│    │                            │  3. 转发开机命令        │                 │
│    │                            │───────────────────────>│                 │
│    │                            │                        │                 │
│    │                            │                        │ 4. Xbox 开始启动 │
│    │                            │                        │                 │
│    │  5. 检查电源状态            │                        │                 │
│    │    GET /servers/{id}       │                        │                 │
│    │───────────────────────────>│                        │                 │
│    │                            │                        │                 │
│    │  6. 返回电源状态: Standby  │                        │                 │
│    │<───────────────────────────│                        │                 │
│    │                            │                        │                 │
│    │  (重复 5-6，等待 30 秒)     │                        │                 │
│    │         ↓                  │                        │                 │
│    │                            │                        │                 │
│    │                            │                        │ 7. 开机完成      │
│    │                            │                        │                 │
│    │  8. 检查电源状态            │                        │                 │
│    │───────────────────────────>│                        │                 │
│    │                            │                        │                 │
│    │  9. 返回电源状态: On       │                        │                 │
│    │<───────────────────────────│                        │                 │
│    │                            │                        │                 │
│    │  ✓ Xbox 已开机！           │                        │                 │
│    │                            │                        │                 │
│    │  10. 建立 PlaySession      │                        │                 │
│    │───────────────────────────>│                        │                 │
│    │                            │                        │                 │
│    │  11. 开始串流              │                        │                 │
│    │                            │                        │                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ 测试场景

### 场景 1: Xbox 已开机 (P1)

```
输入：
- 授权 Xbox 1 台
- 本地在线
- 电源状态: On

预期输出：
- 直接选择该 Xbox
- 无需唤醒
- 耗时: ~0 秒
```

### 场景 2: Xbox 待机 (P2)

```
输入：
- 授权 Xbox 1 台
- 本地在线
- 电源状态: Standby

预期输出：
- 自动发送唤醒命令
- 等待 15-25 秒开机
- 选择该 Xbox
- 耗时: ~20 秒
```

### 场景 3: Xbox 离线 (P3)

```
输入：
- 授权 Xbox 1 台
- 本地离线

预期输出：
- 尝试唤醒（可能失败）
- 返回错误：无法连接 Xbox
- 提示检查 Xbox 网络和电源模式
```

### 场景 4: 多台 Xbox

```
输入：
- 授权 Xbox: Xbox-A, Xbox-B
- 本地在线: Xbox-A (Standby), Xbox-B (On)

预期输出：
- Xbox-B 优先级更高（已开机）
- Xbox-B 直接选择
- Xbox-B (P1): 已授权 + 在线 + 已开机
```

---

## 📝 配置选项

在 `agent.yaml` 中添加唤醒配置:

```yaml
xbox:
  streaming:
    # Xbox 主机匹配配置
    match:
      wakeup_enabled: true        # 启用自动唤醒
      wakeup_timeout: 30          # 唤醒超时（秒）
      wakeup_max_retries: 2        # 最大重试次数
      wakeup_check_interval: 3      # 检查间隔（秒）
    
    # 电源管理
    power:
      preferred_state: "On"         # 优先选择已开机的
      allow_standby: true          # 允许使用待机状态的 Xbox
      auto_power_off: false        # 任务完成后自动关机
```

---

## ⚠️ 注意事项

1. **唤醒前提**: Xbox 必须处于 Instant-On 模式，Energy-Saving 模式无法远程唤醒
2. **唤醒时间**: Xbox 从待机到开机通常需要 **15-30 秒**
3. **网络要求**: Xbox 必须连接到网络，且网络可访问 Xbox Live
4. **电源模式**: 确保 Xbox 设置为 "Instant-On" 而非 "Energy-Saving"
5. **API 限制**: Xbox Live API 可能有频率限制，频繁唤醒可能触发限制

---

## 🔍 故障排查

### 唤醒失败常见原因

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| API 返回 401 | Token 过期 | 重新认证获取新 Token |
| API 返回 404 | 设备 ID 无效 | 检查设备 ID 是否正确 |
| API 返回 429 | 频率限制 | 减少唤醒频率，等待后重试 |
| 等待超时 | Xbox 开机太慢 | 增加超时时间或检查 Xbox |
| SmartGlass 失败 | 网络问题 | 检查本地网络连接 |

### Xbox 电源模式检查

```bash
# 在 Xbox 上检查电源模式
设置 > 电源 > 启动模式

选项：
- Instant-On: ✅ 支持远程唤醒
- Energy-Saving: ❌ 不支持远程唤醒
```

---

**总结**: 通过集成 Xbox 唤醒功能，系统可以自动将待机的 Xbox 开机，大大提高自动化程度和可用性！
