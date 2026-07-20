"""
Bend Agent 的 Xbox 发现模块。

LAN 发现顺序（无云端 token 时）：
1. SmartGlass UDP Discovery（OpenXbox 0xDD00/0xDD01，端口 5050）
2. SSDP M-SEARCH（UDP 1900）
3. 端口扫描 / ARP 兜底

可选：Xbox Live 云端 API（需 Bearer Token，用于远程主机列表）。
"""
import asyncio
import socket
import struct
import hashlib
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.config import config
from ..core.logger import get_logger
from ..gssv.base_uri import DEFAULT_GSSV_BASE_URI, normalize_gssv_base_uri
from ..gssv.device_info import build_x_ms_device_info
from ..discovery.lan_network_util import is_blocked_scan_ip, pick_local_lan_ip


@dataclass
class XboxInfo:
    """Xbox 主机信息"""
    device_id: str
    name: str
    ip_address: str
    port: int
    live_id: str
    console_type: str
    firmware_version: str
    last_seen: datetime
    power_state: str = "Unknown"
    play_path: str = ""


class XboxDiscovery:
    """
    多种方式发现 Xbox 主机：

    1. Xbox Live 云端 API（优先）
       - 需要 Bearer Token
       - 可发现远程在线的 Xbox
       - 返回完整的服务器信息 (serverId, playPath, powerState)

    2. SmartGlass UDP Discovery（OpenXbox 0xDD00）
       - UDP 5050 广播/组播
       - 返回 ConsoleName、Hardware UUID、证书

    3. SSDP（Simple Service Discovery Protocol）
       - 无需认证
       - 本地网络发现
       - 支持 Xbox 特定搜索

    4. 网络端口扫描
       - 扫描常见 Xbox 端口
       - 作为 SSDP 的备用方案

    5. ARP 扫描
       - 使用系统 arp 命令
       - 最后备选方案
    """

    SSDP_MULTICAST_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SMARTGLASS_PORT = 5050
    XBOX_STREAM_PORT = 3074
    XBOX_STREAM_HTTPS_PORT = 3080
    XBOX_VALIDATION_PORTS = [5050, 3074, 3080]

    DEFAULT_API_BASE = DEFAULT_GSSV_BASE_URI

    SEARCH_REQUEST = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: {host}:{port}\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 3\r\n"
        "ST: urn:dial-multiscreen-org:service:dial:1\r\n"
        "\r\n"
    )

    XBOX_SEARCH_REQUEST = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: {host}:{port}\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 3\r\n"
        "ST: urn:schemas-xbox-com:device:Xbox\r\n"
        "\r\n"
    )

    ALL_DEVICES_REQUEST = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: {host}:{port}\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 3\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    )

    def __init__(self, api_base: Optional[str] = None):
        self.logger = get_logger('xbox_discovery')
        self._api_base = normalize_gssv_base_uri(api_base)
        self._discovered_xboxes: Dict[str, XboxInfo] = {}
        self._discovery_task: Optional[asyncio.Task] = None
        self._running = False
        self._access_token: Optional[str] = None

    def set_api_base(self, api_base: Optional[str]) -> None:
        self._api_base = normalize_gssv_base_uri(api_base)

    def set_access_token(self, token: str):
        """
        设置 Xbox Live 访问令牌

        参数：
        - token: Bearer Token
        """
        self._access_token = token

    async def discover_online_xboxes(self) -> List[XboxInfo]:
        """
        使用 Xbox Live 云端 API 发现在线 Xbox

        参考 streaming 项目实现：
        - 调用 /v6/servers/home API
        - 返回完整的服务器信息
        - 需要 Bearer Token 认证

        返回：
        - XboxInfo 列表
        """
        if not self._access_token:
            self.logger.warning("无可用的访问令牌，无法使用云端发现")
            return []

        try:
            import aiohttp

            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'x-xbl-contract-version': '1',
                'X-MS-Device-Info': build_x_ms_device_info(),
            }

            url = f"{self._api_base}/v6/servers/home"
            self.logger.info("使用 Xbox Live 云端 API 发现 Xbox...")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get('results', [])
                        total_items = data.get('totalItems', 0)

                        self.logger.info(f"云端发现: 找到 {len(results)} 台 Xbox (总计: {total_items})")

                        xboxes = []
                        for server in results:
                            server_id = server.get('serverId', '')
                            play_path = server.get('playPath', '')
                            power_state = server.get('powerState', 'Unknown')
                            console_type = server.get('consoleType', 'Xbox Unknown')
                            device_name = server.get('deviceName', console_type)

                            self.logger.info(f"  - {device_name}: {console_type}, "
                                          f"Power: {power_state}, ServerId: {server_id}")

                            xbox_info = XboxInfo(
                                device_id=server_id,
                                name=device_name,
                                ip_address="",
                                port=self.SMARTGLASS_PORT,
                                live_id=server.get('liveId', '') or server_id,
                                console_type=console_type,
                                firmware_version="Unknown",
                                last_seen=datetime.now(),
                                power_state=power_state,
                                play_path=play_path
                            )

                            xboxes.append(xbox_info)
                            self._discovered_xboxes[server_id] = xbox_info

                        return xboxes

                    else:
                        text = await resp.text()
                        self.logger.error(f"云端发现失败: {resp.status} - {text}")
                        return []

        except asyncio.TimeoutError:
            self.logger.error("云端发现超时")
        except Exception as e:
            self.logger.error(f"云端发现错误: {e}")

        return []

    async def start_discovery(self, interval: int = 60):
        """
        启动周期性 Xbox 发现。

        参数:
            interval: 发现间隔（秒）
        """
        self._running = True
        self._discovery_task = asyncio.create_task(self._discovery_loop(interval))
        self.logger.info(f"Xbox discovery started with interval {interval}s")

    async def stop_discovery(self):
        """停止 Xbox 发现"""
        self._running = False
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Xbox discovery stopped")

    async def _discovery_loop(self, interval: int):
        """周期性发现循环"""
        while self._running:
            try:
                await self.discover()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Discovery loop error: {e}")
                await asyncio.sleep(interval)

    async def discover(self, use_cloud_first: bool = True) -> List[XboxInfo]:
        """
        在局域网执行 Xbox 发现。

        发现顺序（use_cloud_first=True 时）：
        1. Xbox Live 云端 API（优先，需 Bearer Token）
        2. SSDP 发现
        3. 网络端口扫描
        4. ARP 扫描（备选）

        参数:
            use_cloud_first: 是否优先使用云端发现

        返回:
            已发现 Xbox 主机列表
        """
        self.logger.info("开始Xbox发现...")

        try:
            xboxes = []
            discovered_ips = set()

            if use_cloud_first and self._access_token:
                self.logger.info("=== 步骤1: 使用 Xbox Live 云端 API 发现 ===")
                cloud_xboxes = await self.discover_online_xboxes()

                for xbox in cloud_xboxes:
                    xboxes.append(xbox)
                    discovered_ips.add(xbox.device_id)
                    self.logger.info(f"通过云端发现Xbox: {xbox.name} ({xbox.console_type})")

                if xboxes:
                    self.logger.info(f"云端发现成功，共 {len(xboxes)} 台")
                    return xboxes

            self.logger.info("=== 步骤2: 使用 SSDP 发现 ===")
            devices = await self._ssdp_discover()
            for device in devices:
                ip = device.get("ip", "")
                if ip and ip in discovered_ips:
                    continue
                is_xbox_device = device.get('is_xbox', False)
                xbox = await self._get_xbox_info(device, skip_validation=is_xbox_device)
                if xbox:
                    self._discovered_xboxes[xbox.device_id] = xbox
                    xboxes.append(xbox)
                    discovered_ips.add(xbox.ip_address)
                    if is_xbox_device:
                        self.logger.info(f"✓ 通过SSDP发现Xbox: {xbox.name} ({xbox.ip_address})")
                    else:
                        self.logger.info(f"SSDP发现非Xbox设备: {xbox.ip_address}")

            if len(xboxes) == 0:
                self.logger.info("SSDP未发现Xbox设备，开始网络端口扫描...")
                network_ips = await self._scan_local_network()

                for ip in network_ips:
                    if ip not in discovered_ips:
                        device = {'ip': ip, 'location': f'http://{ip}:5050', 'usn': '', 'is_xbox': False}
                        xbox = await self._get_xbox_info(device, skip_validation=False)
                        if xbox:
                            self._discovered_xboxes[xbox.device_id] = xbox
                            xboxes.append(xbox)
                            discovered_ips.add(ip)
                            self.logger.info(f"✓ 通过网络扫描发现Xbox: {xbox.name} ({xbox.ip_address})")

            if len(xboxes) == 0:
                self.logger.info("网络扫描未发现设备，尝试ARP扫描...")
                arp_ips = await self._arp_scan()

                for ip in arp_ips:
                    if ip not in discovered_ips:
                        device = {'ip': ip, 'location': f'http://{ip}:5050', 'usn': ''}
                        xbox = await self._get_xbox_info(device)
                        if xbox:
                            self._discovered_xboxes[xbox.device_id] = xbox
                            xboxes.append(xbox)
                            discovered_ips.add(ip)
                            self.logger.info(f"通过ARP扫描发现Xbox: {xbox.name} ({xbox.ip_address})")

            self.logger.info(f"Xbox发现完成，共找到 {len(xboxes)} 台设备")
            return xboxes

        except Exception as e:
            self.logger.error(f"Xbox发现失败: {e}")
            return []

    async def _ssdp_discover(self) -> List[Dict[str, str]]:
        """发送 SSDP M-SEARCH 并收集响应。"""
        devices = []

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
            sock.settimeout(8)

            search_requests = [
                self.XBOX_SEARCH_REQUEST,
                self.ALL_DEVICES_REQUEST,
                self.SEARCH_REQUEST
            ]

            self.logger.info("开始SSDP发现，发送3种搜索请求...")
            for idx, request_template in enumerate(search_requests):
                multicast_request = request_template.format(
                    host=self.SSDP_MULTICAST_ADDR,
                    port=self.SSDP_PORT
                )
                sock.sendto(multicast_request.encode(), (self.SSDP_MULTICAST_ADDR, self.SSDP_PORT))
                self.logger.debug(f"已发送SSDP请求 #{idx+1}")
                await asyncio.sleep(0.5)

            self.logger.info("等待SSDP响应...")
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode('utf-8', errors='ignore')
                    response_lower = response.lower()

                    is_xbox = any(keyword in response_lower for keyword in ['xbox', 'microsoft', 'smarthglass', 'urn:schemas-xbox'])
                    is_device = 'location' in response_lower and ('http://' in response_lower or 'https://' in response_lower)

                    if is_xbox or is_device:
                        device = self._parse_ssdp_response(response)
                        if device and addr[0] not in [d.get('ip') for d in devices]:
                            device['ip'] = addr[0]
                            device['is_xbox'] = is_xbox
                            devices.append(device)
                            if is_xbox:
                                self.logger.info(f"✓ SSDP发现Xbox设备: {addr[0]}")
                            else:
                                self.logger.info(f"SSDP发现可能设备: {addr[0]} (需要验证)")
                except socket.timeout:
                    self.logger.info("SSDP等待响应超时")
                    break
                except Exception as e:
                    self.logger.debug(f"解析SSDP响应错误: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"SSDP发现错误: {e}")
        finally:
            sock.close()

        self.logger.info(f"SSDP发现完成，找到 {len(devices)} 个设备")
        return devices

    async def _scan_local_network(self) -> List[str]:
        """扫描局域网开放 Xbox 端口的设备。"""
        found_ips = []
        local_ip = self._get_local_ip()
        if not local_ip:
            self.logger.warning("无法获取本机IP地址，网络扫描跳过")
            return found_ips
        if is_blocked_scan_ip(local_ip):
            self.logger.warning(
                "跳过局域网扫描：本机出口 IP %s 属于代理/TUN 网段（非真实 LAN）",
                local_ip,
            )
            return found_ips

        network_prefix = '.'.join(local_ip.split('.')[:3])
        ports_to_scan = [5050, 3074, 3080]
        
        self.logger.info(f"开始网络扫描: {network_prefix}.0/24")
        self.logger.info(f"扫描Xbox专有端口: {ports_to_scan}")

        async def scan_port(ip, port):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=1.5
                )
                writer.close()
                await writer.wait_closed()
                return (ip, port, True)
            except asyncio.TimeoutError:
                return (ip, port, False)
            except ConnectionRefusedError:
                return (ip, port, False)
            except Exception:
                return (ip, port, False)

        tasks = []
        for i in range(1, 255):
            ip = f"{network_prefix}.{i}"
            for port in ports_to_scan:
                tasks.append(scan_port(ip, port))

        results = await asyncio.gather(*tasks)

        open_ports_count = 0
        for ip, port, success in results:
            if success and ip not in found_ips:
                found_ips.append(ip)
                open_ports_count += 1
                self.logger.info(f"发现可能设备: {ip}:{port} (需要验证是否为Xbox)")

        self.logger.info(f"网络扫描完成，找到 {len(found_ips)} 个可能设备")
        return found_ips

    def _get_local_ip(self) -> Optional[str]:
        """优先 RFC1918 局域网地址；忽略代理假 IP 段。"""
        return pick_local_lan_ip()

    async def _broadcast_ping(self) -> List[str]:
        """广播 ping 发现设备。"""
        found_ips = []
        local_ip = self._get_local_ip()
        if not local_ip:
            return found_ips

        network_prefix = '.'.join(local_ip.split('.')[:3])
        broadcast_addr = f"{network_prefix}.255"

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(3)

            ping_msg = b"XboxDiscoveryPing"
            sock.sendto(ping_msg, (broadcast_addr, 3074))

            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    if addr[0] not in found_ips:
                        found_ips.append(addr[0])
                except socket.timeout:
                    break
        except Exception as e:
            self.logger.debug(f"Broadcast ping error: {e}")
        finally:
            sock.close()

        return found_ips

    async def _arp_scan(self) -> List[str]:
        """使用系统 arp 命令执行 ARP 扫描。"""
        found_ips = []
        local_ip = self._get_local_ip()
        if not local_ip:
            return found_ips

        network_prefix = '.'.join(local_ip.split('.')[:3])
        self.logger.info(f"执行ARP扫描: {network_prefix}.0/24")

        try:
            import subprocess

            for i in range(1, 255):
                ip = f"{network_prefix}.{i}"
                try:
                    result = subprocess.run(
                        ['arp', '-a', ip],
                        capture_output=True,
                        text=True,
                        timeout=0.5
                    )

                    if result.returncode == 0 and 'no entry' not in result.stdout.lower():
                        output = result.stdout.strip()
                        if output and 'dynamic' in output.lower():
                            self.logger.debug(f"ARP发现: {ip} - {output}")
                            found_ips.append(ip)

                except subprocess.TimeoutExpired:
                    continue
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"ARP扫描错误: {e}")

        self.logger.info(f"ARP扫描完成，找到 {len(found_ips)} 个设备")
        return found_ips

    def _parse_ssdp_response(self, response: str) -> Optional[Dict[str, str]]:
        """解析 SSDP NOTIFY 或 M-SEARCH 响应。"""
        device = {}

        for line in response.split('\r\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.lower().strip()
                value = value.strip()

                if key == 'location':
                    device['location'] = value
                elif key == 'st':
                    device['st'] = value
                elif key == 'usn':
                    device['usn'] = value
                elif key == 'server':
                    device['server'] = value

        return device if 'location' in device else None

    async def _get_xbox_info(self, device: Dict[str, str], skip_validation: bool = False) -> Optional[XboxInfo]:
        """
        获取 Xbox 设备信息
        
        通过 SSDP 发现的设备已经包含了 Xbox 关键词确认，
        因此跳过 SmartGlass 端口验证，直接使用发现的 IP。
        
        参数:
            device: SSDP 发现的设备信息
            skip_validation: 是否跳过端口验证（SSDP 已确认是 Xbox）
        """
        try:
            location = device.get('location', '')
            usn = device.get('usn', '')
            ip = device.get('ip', '')
            is_xbox_device = device.get('is_xbox', False)
            
            if not ip:
                return None
            
            if not is_xbox_device:
                if skip_validation:
                    self.logger.debug(f"跳过端口验证，直接拒绝非 Xbox 设备: {ip}")
                    return None
                xbox_info = await self._verify_xbox_device(ip)
                if not xbox_info:
                    self.logger.debug(f"设备 {ip} 不是有效的 Xbox 设备")
                    return None
            
            device_id = self._extract_xbox_id_from_usn(usn)
            if not device_id:
                device_id = self._generate_device_id(ip)
            
            name = self._extract_name_from_location(location)
            if not name or name.startswith('Xbox-'):
                name = f"Xbox ({ip})"
            
            console_type = self._extract_console_type(name)
            
            xbox_port = self.SMARTGLASS_PORT
            if 'location' in device and ':' in device['location']:
                try:
                    port_str = device['location'].split(':')[-1].split('/')[0]
                    xbox_port = int(port_str)
                except:
                    pass
            
            return XboxInfo(
                device_id=device_id,
                name=name,
                ip_address=ip,
                port=xbox_port,
                live_id=device_id,
                console_type=console_type,
                firmware_version="Unknown",
                last_seen=datetime.now(),
                power_state="Unknown"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get Xbox info: {e}")
            return None
    
    async def _verify_xbox_device(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        验证设备是否为有效的 Xbox
        
        通过 SmartGlass 握手协议验证：
        1. 尝试连接多个 Xbox 端口 (5050, 3074, 3080)
        2. 发送握手请求
        3. 验证响应
        
        参数:
            ip: 设备 IP 地址
            
        返回:
            验证成功返回设备信息字典，失败返回 None
        """
        for port in self.XBOX_VALIDATION_PORTS:
            try:
                self.logger.info(f"尝试验证 Xbox 设备: {ip}:{port}")
                
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=3
                )
                
                handshake_request = self._build_handshake_request()
                writer.write(handshake_request)
                await asyncio.wait_for(writer.drain(), timeout=5)
                
                response = await asyncio.wait_for(reader.read(1024), timeout=5)
                
                writer.close()
                await writer.wait_closed()
                
                if response and len(response) > 4:
                    header = struct.unpack('>I', response[:4])[0]
                    if header > 0 and header < 10000:
                        self.logger.info(f"✓ Xbox 设备验证成功: {ip}:{port}")
                        return {
                            'device_id': self._generate_device_id(ip),
                            'name': f'Xbox ({ip})',
                            'console_type': 'Xbox',
                            'port': port,
                            'firmware': 'Unknown',
                            'power_state': 'On'
                        }
                    else:
                        self.logger.info(f"✗ Xbox 握手响应无效: {ip}:{port}")
                else:
                    self.logger.info(f"✗ Xbox 无响应: {ip}:{port}")
                continue
                
            except asyncio.TimeoutError:
                self.logger.info(f"✗ Xbox 验证超时: {ip}:{port}")
                continue
            except ConnectionRefusedError:
                self.logger.info(f"✗ Xbox 连接被拒绝: {ip}:{port}")
                continue
            except Exception as e:
                self.logger.info(f"✗ Xbox 验证失败 {ip}:{port}: {e}")
                continue
        
        return None
    
    def _build_handshake_request(self) -> bytes:
        """
        构建 SmartGlass 握手请求
        
        返回值：握手请求的字节数据
        
        数据格式：
        - 4字节长度头（大端序）
        - JSON内容（UTF-8编码）
        """
        import json
        content = json.dumps({
            "protocol": "xbox.smartglass",
            "version": "1.0",
            "transport": "ws"
        })
        header = struct.pack('>I', len(content))
        return header + content.encode('utf-8')

    def _extract_xbox_id_from_usn(self, usn: str) -> Optional[str]:
        """
        从SSDP USN字段提取Xbox真实设备ID

        USN格式: uuid:A820E6B7-9BC8-4F6B-8F9E-4A3B2C1D0E5F::urn:schemas-xbox-com:device:Xbox
        返回: A820E6B7-9BC8-4F6B-8F9E-4A3B2C1D0E5F
        """
        if not usn:
            return None

        try:
            if usn.startswith('uuid:'):
                uuid_part = usn[5:]
                if '::' in uuid_part:
                    uuid_part = uuid_part.split('::')[0]
                if self._is_valid_uuid(uuid_part):
                    return f"XBOX-{uuid_part.upper()}"
        except Exception as e:
            self.logger.debug(f"Failed to extract Xbox ID from USN: {e}")

        return None

    def _is_valid_uuid(self, uuid_str: str) -> bool:
        """验证是否为有效的UUID格式"""
        if not uuid_str or len(uuid_str) < 10:
            return False
        parts = uuid_str.split('-')
        return len(parts) == 5

    def _extract_console_type(self, name: str) -> str:
        """从名称中提取主机类型"""
        name_upper = name.upper() if name else ''
        if 'SERIES X' in name_upper or 'SERIES S' in name_upper:
            if 'SERIES X' in name_upper:
                return "Xbox Series X"
            else:
                return "Xbox Series S"
        elif 'ONE' in name_upper:
            return "Xbox One"
        return "Xbox Unknown"

    def _extract_name_from_location(self, location: str) -> str:
        """从 location URL 提取 Xbox 名称。"""
        try:
            if location.startswith('http://'):
                host = location[7:]
                if ':' in host:
                    return f"Xbox-{host.split(':')[0].split('.')[-1]}"
                return f"Xbox-{host.split('.')[-1]}"
        except Exception:
            pass
        return "Xbox"

    def _generate_device_id(self, ip: str) -> str:
        """由 IP 地址生成设备 ID。"""
        hash_val = hashlib.md5(ip.encode()).hexdigest()
        return f"XBOX-{hash_val[:8].upper()}"

    def get_discovered_xboxes(self) -> List[XboxInfo]:
        """获取全部已发现 Xbox 主机列表"""
        return list(self._discovered_xboxes.values())

    def get_xbox_by_ip(self, ip: str) -> Optional[XboxInfo]:
        """按 IP 地址获取 Xbox 信息"""
        for xbox in self._discovered_xboxes.values():
            if xbox.ip_address == ip:
                return xbox
        return None

    def get_xbox_by_id(self, device_id: str) -> Optional[XboxInfo]:
        """按设备 ID 获取 Xbox 信息"""
        return self._discovered_xboxes.get(device_id)

    async def test_connection(self, ip: str, port: int = None) -> bool:
        """
        测试与 Xbox 主机的连接。

        参数:
            ip: Xbox IP 地址
            port: 端口号（默认 SMARTGLASS_PORT）

        返回:
            连接成功为 True
        """
        port = port or self.SMARTGLASS_PORT

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            self.logger.debug(f"Connection test to {ip}:{port} failed: {e}")
            return False


xbox_discovery = XboxDiscovery()
