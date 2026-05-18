"""
Xbox discovery module for Bend Agent
Discovers Xbox consoles on the local network using SSDP and Xbox SmartGlass protocol
"""
import asyncio
import socket
import struct
import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..core.logger import get_logger


@dataclass
class XboxInfo:
    """Xbox console information"""
    device_id: str
    name: str
    ip_address: str
    port: int
    live_id: str
    console_type: str
    firmware_version: str
    last_seen: datetime


class XboxDiscovery:
    """
    Xbox console discovery using SSDP (Simple Service Discovery Protocol)
    and Xbox SmartGlass protocol for detailed device information
    """

    SSDP_MULTICAST_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SMARTGLASS_PORT = 5050

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

    def __init__(self):
        self.logger = get_logger('xbox_discovery')
        self._discovered_xboxes: Dict[str, XboxInfo] = {}
        self._discovery_task: Optional[asyncio.Task] = None
        self._running = False

    async def start_discovery(self, interval: int = 60):
        """
        Start periodic Xbox discovery

        Args:
            interval: Discovery interval in seconds
        """
        self._running = True
        self._discovery_task = asyncio.create_task(self._discovery_loop(interval))
        self.logger.info(f"Xbox discovery started with interval {interval}s")

    async def stop_discovery(self):
        """Stop Xbox discovery"""
        self._running = False
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Xbox discovery stopped")

    async def _discovery_loop(self, interval: int):
        """Periodic discovery loop"""
        while self._running:
            try:
                await self.discover()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Discovery loop error: {e}")
                await asyncio.sleep(interval)

    async def discover(self) -> List[XboxInfo]:
        """
        Perform Xbox discovery on the local network

        Returns:
            List of discovered Xbox consoles
        """
        self.logger.info("Starting Xbox discovery...")

        try:
            xboxes = []
            discovered_ips = set()

            devices = await self._ssdp_discover()
            for device in devices:
                xbox = await self._get_xbox_info(device)
                if xbox:
                    self._discovered_xboxes[xbox.device_id] = xbox
                    xboxes.append(xbox)
                    discovered_ips.add(xbox.ip_address)
                    self.logger.info(f"Discovered Xbox via SSDP: {xbox.name} ({xbox.ip_address})")

            if len(xboxes) == 0:
                self.logger.info("SSDP discovery found nothing, trying network scan...")
                network_ips = await self._scan_local_network()
                
                for ip in network_ips:
                    if ip not in discovered_ips:
                        device = {'ip': ip, 'location': f'http://{ip}:5050', 'usn': ''}
                        xbox = await self._get_xbox_info(device)
                        if xbox:
                            self._discovered_xboxes[xbox.device_id] = xbox
                            xboxes.append(xbox)
                            discovered_ips.add(ip)
                            self.logger.info(f"Discovered Xbox via network scan: {xbox.name} ({xbox.ip_address})")

            self.logger.info(f"Xbox discovery completed, found {len(xboxes)} devices")
            return xboxes

        except Exception as e:
            self.logger.error(f"Xbox discovery failed: {e}")
            return []

    async def _ssdp_discover(self) -> List[Dict[str, str]]:
        """Send SSDP M-SEARCH request and collect responses"""
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

            for request_template in search_requests:
                multicast_request = request_template.format(
                    host=self.SSDP_MULTICAST_ADDR,
                    port=self.SSDP_PORT
                )
                sock.sendto(multicast_request.encode(), (self.SSDP_MULTICAST_ADDR, self.SSDP_PORT))
                await asyncio.sleep(0.5)

            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode('utf-8', errors='ignore')
                    
                    if 'xbox' in response.lower() or 'microsoft' in response.lower():
                        device = self._parse_ssdp_response(response)
                        if device and addr[0] not in [d.get('ip') for d in devices]:
                            device['ip'] = addr[0]
                            devices.append(device)
                except socket.timeout:
                    break
                except Exception as e:
                    self.logger.debug(f"Error parsing SSDP response: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"SSDP discover error: {e}")
        finally:
            sock.close()

        self.logger.debug(f"SSDP discovery found {len(devices)} devices")
        return devices

    async def _scan_local_network(self) -> List[str]:
        """Scan local network for devices with open Xbox ports"""
        found_ips = []
        local_ip = self._get_local_ip()
        if not local_ip:
            return found_ips

        network_prefix = '.'.join(local_ip.split('.')[:3])
        ports_to_scan = [5050, 3074, 5000]
        
        async def scan_port(ip, port):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=2
                )
                writer.close()
                await writer.wait_closed()
                return ip
            except:
                return None

        tasks = []
        for i in range(1, 255):
            ip = f"{network_prefix}.{i}"
            for port in ports_to_scan:
                tasks.append(scan_port(ip, port))

        results = await asyncio.gather(*tasks)
        for ip in results:
            if ip and ip not in found_ips:
                found_ips.append(ip)

        self.logger.debug(f"Network scan found {len(found_ips)} potential devices")
        return found_ips

    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return None

    async def _broadcast_ping(self) -> List[str]:
        """Send broadcast ping to discover devices"""
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

    def _parse_ssdp_response(self, response: str) -> Optional[Dict[str, str]]:
        """Parse SSDP NOTIFY or M-SEARCH response"""
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

    async def _get_xbox_info(self, device: Dict[str, str]) -> Optional[XboxInfo]:
        """Get detailed Xbox information using SmartGlass protocol"""
        try:
            location = device.get('location', '')
            usn = device.get('usn', '')
            if not location:
                return None

            ip = device.get('ip', '')
            
            name = self._extract_name_from_location(location)
            if name and name.startswith('Xbox-'):
                name = None
            
            console_type = self._extract_console_type(name)

            device_id = self._extract_xbox_id_from_usn(usn)
            if not device_id:
                device_id = self._generate_device_id(ip)
                self.logger.debug(f"无法获取Xbox UUID，使用IP生成device_id: {device_id}")

            return XboxInfo(
                device_id=device_id,
                name=name,
                ip_address=ip,
                port=self.SMARTGLASS_PORT,
                live_id=device_id,
                console_type=console_type,
                firmware_version="Unknown",
                last_seen=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"Failed to get Xbox info: {e}")
            return None

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
        """Extract Xbox name from location URL"""
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
        """Generate a device ID from IP address"""
        hash_val = hashlib.md5(ip.encode()).hexdigest()
        return f"XBOX-{hash_val[:8].upper()}"

    def get_discovered_xboxes(self) -> List[XboxInfo]:
        """Get list of all discovered Xbox consoles"""
        return list(self._discovered_xboxes.values())

    def get_xbox_by_ip(self, ip: str) -> Optional[XboxInfo]:
        """Get Xbox info by IP address"""
        for xbox in self._discovered_xboxes.values():
            if xbox.ip_address == ip:
                return xbox
        return None

    def get_xbox_by_id(self, device_id: str) -> Optional[XboxInfo]:
        """Get Xbox info by device ID"""
        return self._discovered_xboxes.get(device_id)

    async def test_connection(self, ip: str, port: int = None) -> bool:
        """
        Test connection to an Xbox console

        Args:
            ip: Xbox IP address
            port: Port number (default: SMARTGLASS_PORT)

        Returns:
            True if connection successful
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
