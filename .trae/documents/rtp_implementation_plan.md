> **架构勘误（2026-06-13）**：生产 Step2–3 为 **xblive/xsrp（GSSV 云端 + WebRTC）**，入口见 `bend-agent/src/agent/automation/step2_xsrp.py`、`step3_xsrp.py`。下文 SmartGlass LAN、`step2_xbox_streaming.py` 等为**历史方案**；SmartGlass UDP 仅作 LAN 发现/唤醒兜底。详见 [00_架构勘误_xsrp_step2.md](./00_架构勘误_xsrp_step2.md)。

# RTP 解封装实现方案

**版本**: 1.0
**最后更新**: 2026-05-30
**目标**: 实现 Xbox 视频流的 RTP 接收、解封装和解码

---

## 一、当前架构分析

### 1.1 当前视频流处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 当前视频流架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   XboxStreamController (SmartGlass TCP:5050)                   │
│   ├── 控制命令发送 ✅                                          │
│   ├── 手柄状态发送 ✅                                          │
│   └── 视频流接收 ❌                                            │
│                                                                  │
│   XboxWebRTCHandler (SDP)                                     │
│   ├── SDP Offer 创建 ✅                                        │
│   ├── SDP Answer 处理 ✅                                       │
│   ├── ICE 候选处理 ✅                                          │
│   └── DTLS/SRTP 握手 ❌                                       │
│                                                                  │
│   VideoFrameCapture (win32gui)                                 │
│   ├── 窗口截图 ✅                                              │
│   └── GPU 解码（准备但未使用）⚠️                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 缺失组件

| 组件 | 状态 | 说明 |
|------|------|------|
| **DTLS 握手** | ❌ 缺失 | SRTP 加密密钥交换 |
| **SRTP 解密** | ❌ 缺失 | 解密 RTP 视频流 |
| **RTP 解封装** | ❌ 缺失 | 提取 H.264 NALU |
| **H.264 解码** | ⚠️ 准备 | GPUDecoder 已准备 |
| **帧回调** | ❌ 缺失 | 帧数据传递给上层 |

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 目标视频流架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              XboxStreamingSession                        │   │
│   │                                                         │   │
│   │  ┌───────────────────┐                                 │   │
│   │  │ XboxStreamController│                                 │   │
│   │  │  (SmartGlass)     │                                 │   │
│   │  └───────────────────┘                                 │   │
│   │           │                                              │   │
│   │           │                                              │   │
│   │  ┌────────▼────────┐                                    │   │
│   │  │  WebRTCHandler  │  ←── SDP + DTLS                  │   │
│   │  │                 │                                    │   │
│   │  │  - create_offer() ✅                                │   │
│   │  │  - handle_answer() ✅                               │   │
│   │  │  - dtls_handshake() ❌ 新增                        │   │
│   │  └────────┬────────┘                                    │   │
│   │           │                                              │   │
│   │           │                                              │   │
│   │  ┌────────▼────────┐                                    │   │
│   │  │  RTPSession      │  ←── RTP 接收 (新增)             │   │
│   │  │                 │                                    │   │
│   │  │  - srtp_decrypt() ❌                                │   │
│   │  │  - rtp_demux() ❌                                   │   │
│   │  │  - h264_parse() ❌                                  │   │
│   │  └────────┬────────┘                                    │   │
│   │           │                                              │   │
│   │           │                                              │   │
│   │  ┌────────▼────────┐                                    │   │
│   │  │  GPUDecoder      │  ←── H.264 解码                   │   │
│   │  │  (已有)         │                                    │   │
│   │  └───────────────────┘                                 │   │
│   │                                                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、需要新增的文件

### 3.1 新增模块列表

| 文件 | 路径 | 功能 |
|------|------|------|
| **rtp_session.py** | `agent/xbox/rtp_session.py` | RTP 会话管理 |
| **srtp_handler.py** | `agent/xbox/srtp_handler.py` | SRTP 加解密 |
| **h264_parser.py** | `agent/xbox/h264_parser.py` | H.264 NALU 解析 |
| **dtls_handler.py** | `agent/xbox/dtls_handler.py` | DTLS 握手 |

### 3.2 模块详细说明

#### 3.2.1 `rtp_session.py` - RTP 会话管理

```python
"""
RTP 会话管理器
=============

功能说明：
- 管理 RTP 视频流接收
- 处理 RTP 数据包
- 维护 RTP 序列号和时间戳
- 支持 H.264 视频流

技术实现：
- UDP socket 接收
- RTP 头部解析
- H.264 NALU 提取

作者：技术团队
版本：1.0
"""

import asyncio
import struct
from dataclasses import dataclass
from typing import Optional, Callable, List
from enum import Enum

class RTPHeader:
    """RTP 头部结构"""
    version: int
    padding: int
    extension: int
    csrc_count: int
    marker: int
    payload_type: int
    sequence_number: int
    timestamp: int
    ssrc: int

class RTPPacket:
    """RTP 数据包"""
    header: RTPHeader
    payload: bytes
    payload_offset: int

class RTPSession:
    """
    RTP 会话管理器

    功能：
    - 绑定 UDP 端口接收 RTP 流
    - 解析 RTP 头部
    - 提取 H.264 NALU
    - 处理乱序和重传

    使用方式：
    session = RTPSession()
    await session.bind('0.0.0.0', 50500)
    async for packet in session.packets():
        process_h264(packet)
    """

    def __init__(self):
        self._socket: Optional[asyncio.DatagramProtocol] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._expected_seq = 0

    async def bind(self, host: str, port: int):
        """绑定 UDP 端口"""
        loop = asyncio.get_event_loop()
        self._socket = RTPProtocol(self._queue)
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self._socket,
            local_addr=(host, port)
        )
        self._running = True

    async def packets(self) -> AsyncIterator[RTPPacket]:
        """异步获取 RTP 数据包"""
        while self._running:
            packet = await self._queue.get()
            yield packet

    def close(self):
        """关闭会话"""
        self._running = False
        if self._transport:
            self._transport.close()
```

#### 3.2.2 `srtp_handler.py` - SRTP 加解密

```python
"""
SRTP 处理器
==========

功能说明：
- SRTP (Secure RTP) 解密
- 使用 DTLS 协商的密钥
- 支持 AES-CM 和 AES-GCM 加密

技术实现：
- AES-128/256 加密
- 同步计数器模式
- ROC (Roll-over Counter) 维护

作者：技术团队
版本：1.0
"""

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class SRTPHandler:
    """
    SRTP 解密处理器

    功能：
    - 使用 SRTP 密钥解密 RTP 包
    - 维护加密状态
    - 支持 H.264 负载

    使用方式：
    handler = SRTPHandler()
    handler.set_keys(
        send_key=b'\x00'*16,  # 发送密钥
        recv_key=b'\x00'*16   # 接收密钥
    )
    decrypted = handler.decrypt_rtp(encrypted_packet)
    """

    def __init__(self):
        self._send_key: Optional[bytes] = None
        self._recv_key: Optional[bytes] = None
        self._send_roc = 0  # Roll-over Counter
        self._recv_roc = 0

    def set_keys(self, send_key: bytes, recv_key: bytes):
        """设置 SRTP 密钥"""
        self._send_key = send_key
        self._recv_key = recv_key

    def decrypt_rtp(self, packet: bytes) -> bytes:
        """解密 SRTP 包"""
        # 1. 提取 RTP 头部
        # 2. 计算 SRTCP 索引
        # 3. AES 解密
        # 4. 验证 auth tag
        pass
```

#### 3.2.3 `h264_parser.py` - H.264 NALU 解析

```python
"""
H.264 NALU 解析器
================

功能说明：
- 解析 RTP H.264 负载
- 处理 STAP-A / FU-A 分片
- 组装完整 NALU
- 提取 NALU 类型

技术实现：
- RTP H.264 payload format (RFC 6184)
- NALU 类型解析
- 分片组装

作者：技术团队
版本：1.0
"""

class H264Parser:
    """
    H.264 NALU 解析器

    功能：
    - 解析 H.264 RTP 负载
    - 处理 STAP-A (聚合包)
    - 处理 FU-A (分片)
    - 组装完整 NALU

    NALU 类型：
    - 1: 非 IDR 图像
    - 5: IDR 图像
    - 6: SEI
    - 7: SPS (序列参数集)
    - 8: PPS (图像参数集)

    使用方式：
    parser = H264Parser()
    parser.set_callback(on_nalu)
    parser.feed(rtp_payload)
    """

    NALU_TYPE_SPS = 7
    NALU_TYPE_PPS = 8
    NALU_TYPE_IDR = 5
    NALU_TYPE_NON_IDR = 1

    def __init__(self):
        self._fragment_buf: Optional[bytes] = None
        self._frag_header: Optional[int] = None
        self._callback: Optional[Callable] = None

    def set_callback(self, callback: Callable[[bytes, int], None]):
        """设置 NALU 回调"""
        self._callback = callback

    def feed(self, payload: bytes):
        """输入 RTP H.264 负载"""
        if not payload:
            return

        nal_type = payload[0] & 0x1F

        if nal_type == 24:  # STAP-A
            self._parse_stap_a(payload)
        elif nal_type == 28:  # FU-A
            self._parse_fu_a(payload)
        else:  # Single NALU
            self._emit_nalu(payload, nal_type)

    def _parse_stap_a(self, payload: bytes):
        """解析 STAP-A 聚合包"""
        # STAP-A header (1 byte) + NALU size (2 bytes) + NALU
        offset = 1
        while offset < len(payload) - 2:
            size = struct.unpack('>H', payload[offset:offset+2])[0]
            offset += 2
            nalu = payload[offset:offset+size]
            offset += size
            self._emit_nalu(nalu, nalu[0] & 0x1F)

    def _parse_fu_a(self, payload: bytes):
        """解析 FU-A 分片"""
        # FU indicator (1) + FU header (1) + data
        indicator = payload[0]
        fu_header = payload[1]
        nal_type = indicator & 0x1F

        start = fu_header & 0x80  # S bit
        end = fu_header & 0x40    # E bit

        if start:
            self._fragment_buf = bytes([indicator & 0xE0 | nal_type])
            self._frag_header = nal_type

        if self._fragment_buf is not None:
            self._fragment_buf += payload[2:]

        if end:
            self._emit_nalu(self._fragment_buf, self._frag_header)
            self._fragment_buf = None

    def _emit_nalu(self, nalu: bytes, nal_type: int):
        """发送完整 NALU"""
        if self._callback:
            self._callback(nalu, nal_type)
```

#### 3.2.4 `dtls_handler.py` - DTLS 握手

```python
"""
DTLS 握手处理器
=============

功能说明：
- 实现 DTLS 客户端握手
- 生成 SRTP 密钥材料
- 支持 SRTP 加密

技术实现：
- DTLS 1.0/1.2
- SRTP 密钥导出
- OpenSSL 绑定 (可选)

作者：技术团队
版本：1.0
"""

class DTLSHandler:
    """
    DTLS 握手处理器

    功能：
    - 执行 DTLS 客户端握手
    - 从 master secret 导出 SRTP 密钥
    - 管理 DTLS 连接状态

    SRTP 密钥导出 (RFC 5764):
    - client_master_key
    - server_master_key
    - client_master_salt
    - server_master_salt

    使用方式：
    handler = DTLSHandler()
    await handler.connect('xbox_ip', 50500)
    keys = handler.get_srtp_keys()
    """

    def __init__(self):
        self._connected = False
        self._keys: Optional[dict] = None

    async def connect(self, host: str, port: int) -> bool:
        """连接到 DTLS 服务器"""
        # 1. 创建 UDP socket
        # 2. 发送 ClientHello
        # 3. 接收 ServerHello
        # 4. 交换证书
        # 5. 发送 ClientKeyExchange
        # 6. 导出 SRTP 密钥
        pass

    def get_srtp_keys(self) -> dict:
        """获取 SRTP 密钥"""
        return self._keys
```

---

## 四、需要修改的文件

### 4.1 修改 `webrtc_handler.py`

**当前状态**：
- ✅ SDP Offer 创建
- ✅ SDP Answer 处理
- ✅ ICE 候选处理
- ❌ DTLS 握手

**需要添加**：

```python
# 新增方法

async def dtls_handshake(self, host: str, port: int) -> bool:
    """
    执行 DTLS 握手

    返回：
    - True: 握手成功
    - False: 握手失败
    """
    dtls = DTLSHandler()
    success = await dtls.connect(host, port)
    if success:
        self._dtls_handler = dtls
        self._srtp_keys = dtls.get_srtp_keys()
    return success

def get_srtp_keys(self) -> Optional[dict]:
    """获取 SRTP 密钥"""
    return self._srtp_keys
```

### 4.2 修改 `stream_controller.py`

**当前状态**：
- ✅ SmartGlass 控制
- ✅ 手柄状态发送
- ❌ 视频流接收

**需要添加**：

```python
# 新增属性

from .rtp_session import RTPSession
from .h264_parser import H264Parser

class XboxStreamController:
    def __init__(self):
        # ... 现有代码 ...
        self._rtp_session: Optional[RTPSession] = None
        self._h264_parser: Optional[H264Parser] = None
        self._video_callback: Optional[Callable] = None

    # 新增方法

    async def start_video_stream(self, port: int, callback: Callable):
        """
        启动视频流接收

        参数：
        - port: RTP 接收端口
        - callback: 视频帧回调函数
        """
        self._video_callback = callback

        # 1. 创建 RTP 会话
        self._rtp_session = RTPSession()
        await self._rtp_session.bind('0.0.0.0', port)

        # 2. 创建 H.264 解析器
        self._h264_parser = H264Parser()
        self._h264_parser.set_callback(self._on_h264_nalu)

        # 3. 启动接收循环
        asyncio.create_task(self._rtp_receive_loop())

    async def _rtp_receive_loop(self):
        """RTP 接收循环"""
        async for packet in self._rtp_session.packets():
            # 解密 SRTP
            decrypted = self._srtp_handler.decrypt_rtp(packet.payload)
            # 解析 H.264
            self._h264_parser.feed(decrypted)

    def _on_h264_nalu(self, nalu: bytes, nal_type: int):
        """H.264 NALU 回调"""
        if self._video_callback:
            self._video_callback(nalu, nal_type)
```

### 4.3 修改 `step2_xsrp.py`

**当前状态**：
- Xbox 连接
- PlaySession 创建
- SDP 握手

**需要添加**：

```python
# 新增步骤

async def step2_xbox_streaming(...):
    # ... 现有代码 ...

    # 新增：启动视频流接收
    await _start_video_receiver(context, ...)

    return Step2Result(success=True, ...)

async def _start_video_receiver(context, ...):
    """
    启动视频流接收（新增）
    """
    # 1. 等待 SDP 握手完成
    # 2. 获取视频接收端口
    # 3. 启动 RTPSession
    # 4. 配置 SRTP 解密
    # 5. 设置帧回调
    pass
```

---

## 五、实现步骤

### 5.1 阶段一：基础框架（1-2天）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| 创建 `rtp_session.py` | RTP 会话管理 | 0.5天 |
| 创建 `h264_parser.py` | H.264 NALU 解析 | 0.5天 |
| 创建单元测试 | 验证解析逻辑 | 0.5天 |

### 5.2 阶段二：安全层（2-3天）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| 创建 `srtp_handler.py` | SRTP 解密 | 1天 |
| 创建 `dtls_handler.py` | DTLS 握手 | 1.5天 |
| 集成到 WebRTCHandler | DTLS + SRTP 集成 | 0.5天 |

### 5.3 阶段三：集成（1-2天）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| 修改 `stream_controller.py` | 添加视频接收 | 0.5天 |
| 修改 `step2_xsrp.py` | 集成视频流 | 0.5天 |
| 端到端测试 | 验证完整流程 | 1天 |

---

## 六、技术依赖

### 6.1 Python 库

| 库 | 用途 | 是否需要 |
|------|------|----------|
| `cryptography` | AES 加解密 | ✅ 需要 |
| `asyncio` | 异步网络 | ✅ 已有 |
| `struct` | 二进制解析 | ✅ 已有 |

### 6.2 可选库

| 库 | 用途 | 备选方案 |
|------|------|----------|
| `pyOpenSSL` | DTLS 实现 | 自实现（复杂） |
| `pynspr` | SRTP 实现 | 自实现（简单） |

---

## 七、配置参数

### 7.1 Xbox 视频流配置

```python
VIDEO_STREAM_CONFIG = {
    'protocol': 'UDP',
    'video_port': 50500,       # RTP 接收端口
    'audio_port': 50501,       # 音频端口
    'codec': 'H264',
    'profile': 'baseline',
    'level': '3.1',
    'resolution': (1280, 720),
    'framerate': 30,
    'bitrate': 5000000,        # 5 Mbps
}
```

### 7.2 SRTP 配置

```python
SRTP_CONFIG = {
    'cipher': 'AES-128-CM',    # 或 AES-128-GCM
    'auth_tag': 80,            # 80-bit
    'roc_bootstrap': True,     # 从 SDP 恢复 ROC
}
```

---

## 八、测试计划

### 8.1 单元测试

| 测试项 | 说明 |
|--------|------|
| RTP 头部解析 | 验证序列号、时间戳解析 |
| H.264 STAP-A | 验证聚合包解析 |
| H.264 FU-A | 验证分片组装 |
| SRTP 解密 | 验证 AES 解密 |

### 8.2 集成测试

| 测试项 | 说明 |
|--------|------|
| 视频流接收 | 验证完整视频流接收 |
| 延迟测试 | 测量端到端延迟 |
| 稳定性测试 | 长时间运行测试 |

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| DTLS 实现复杂 | 高 | 使用 pyOpenSSL 或简化实现 |
| Xbox 不支持直接 RTP | 中 | 使用 WebRTC 代理模式 |
| NAT 穿透问题 | 中 | 使用 TURN 服务器 |

---

## 十、替代方案

### 10.1 方案一：继续使用 win32gui（当前方案）

**优点**：
- 实现简单
- 无需理解协议细节
- 已验证可用

**缺点**：
- 性能有限
- 依赖 Xbox Streaming 功能

### 10.2 方案二：实现完整 RTP（本文方案）

**优点**：
- 性能最优
- 不依赖 Xbox Streaming
- 完全控制

**缺点**：
- 实现复杂
- 需要理解协议细节

### 10.3 方案三：混合模式

**优点**：
- 兼顾性能和实现难度
- 降级使用 win32gui

**缺点**：
- 代码复杂度增加

---

## 十一、建议

1. **短期**：继续使用 win32gui 方案，快速验证功能
2. **中期**：实现 H.264 NALU 解析，配合现有 GPU 解码
3. **长期**：根据需求评估是否需要完整 RTP 实现

---

*文档版本: 1.0*
*最后更新: 2026-05-30*
