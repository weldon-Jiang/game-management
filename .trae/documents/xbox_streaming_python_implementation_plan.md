# Xbox 流媒体 Python 实现计划

## 📋 计划概述

**目标**: 将 Xbox 流媒体协议处理从 C++ (xsrp.py) 迁移到纯 Python 实现
**核心技术**:

* aiortc: WebRTC 客户端实现

* PyAV: H.264 硬件加速解码

* 进程隔离: 每个流媒体实例独立进程

* 架构: 后台服务，由内部网络控制

**当前状态**: `bend-agent` 已有基础组件:

* WebRTC SDP/Offer/Answer 生成

* RTP 会话管理

* H.264 NALU 解析

* DTLS/SRTP 密钥处理

* GPU 检测和基于 FFmpeg 的解码

**缺失部分**: 实际 WebRTC 连接建立、完整的视频解码管道

***

## 🎯 阶段 1: aiortc WebRTC 客户端实现

### 1.1 创建 aiortc WebRTC 处理器模块

**文件**: `src/agent/xbox/aiortc_webrtc_client.py`

**目的**: 使用 aiortc 库实现完整的 WebRTC 客户端

**核心组件**:

```python
class AiortcWebRTCClient:
    """Xbox 流媒体的完整 WebRTC 客户端"""
    
    # 核心方法:
    async def connect(self, xbox_info: dict, sdp_offer: str) -> bool:
        """使用 Xbox SDP 建立 WebRTC 连接"""
    
    async def receive_video_frames(self) -> AsyncIterator[bytes]:
        """生成解码后的 H.264 帧"""
    
    async def send_input(self, gamepad_state: dict):
        """通过数据通道发送游戏手柄输入"""
    
    # 内部方法:
    async def _setup_tracks(self, pc: RTCPeerConnection):
        """设置视频/音频轨道"""
    
    async def _handle_rtp_packet(self, packet: RTCRtpPacket):
        """处理传入的 RTP 数据包"""
```

**实施步骤**:

1. 安装 aiortc: `pip install aiortc[pyav]`
2. 创建匹配 Xbox 要求的 WebRTC 配置
3. 实现 RTCPeerConnection 设置
4. 处理 H.264 编解码器的视频轨道
5. 实现输入数据通道
6. 添加适当的清理和错误处理

**依赖项**:

* aiortc >= 1.9.0

* av (PyAV) 用于帧处理

### 1.2 集成现有 SDP 处理器

**文件**: `src/agent/xbox/webrtc_handler.py` (增强)

**更改**:

* 添加基于 aiortc 的 WebRTC 连接方法

* 保留现有 SDP 生成以保持兼容性

* 在自定义 SDP 和 aiortc RTCSessionDescription 之间建立桥梁

```python
# 添加到 XboxWebRTCHandler 类:
async def establish_webrtc_connection(
    self, 
    xbox_session_info: dict
) -> Optional[AiortcWebRTCClient]:
    """
    使用 aiortc 建立完整 WebRTC 连接
    
    返回:
        AiortcWebRTCClient 实例或 None
    """
```

***

## 🔄 阶段 2: PyAV H.264 硬件解码

### 2.1 创建基于 PyAV 的帧解码器

**文件**: `src/agent/vision/pyav_decoder.py`

**目的**: 用原生 PyAV 替换 FFmpeg 子进程，实现硬件加速解码

**核心组件**:

```python
class PyAVH264Decoder:
    """
    使用 PyAV 的硬件加速 H.264 解码器
    
    功能:
    - 通过 PyAV 原生集成 FFmpeg
    - 自动硬件加速检测
    - NVIDIA NVDEC 支持 (如果可用)
    - 回退到软件解码
    """
    
    def __init__(self, enable_hwaccel: bool = True):
        self._container = None
        self._video_stream = None
        self._decoder = None
        self._hw_device = None
        
    async def initialize(
        self, 
        width: int = 1920, 
        height: int = 1080,
        codec_name: str = "h264"
    ) -> bool:
        """使用硬件加速初始化解码器"""
        
    async def decode_frame(self, h264_data: bytes) -> Optional[np.ndarray]:
        """解码单个 H.264 帧"""
        
    async def decode_rtp_packet(self, rtp_payload: bytes) -> Optional[np.ndarray]:
        """直接从 RTP payload 解码"""
        
    def _setup_hardware_acceleration(self) -> bool:
        """检测并设置 GPU 硬件加速"""
```

**硬件加速策略**:

```python
# 优先级顺序:
1. NVIDIA NVDEC (h264_cuvid via PyAV)
2. AMD AMF (h264_amf via PyAV)  
3. Intel QSV (h264_qsv via PyAV)
4. 软件解码 (libx264)
```

**验证**: 测试 PyAV 是否包含硬件加速

```python
# 检查 PyAV 硬件支持
import av
print(av.codec.codecs_available)
# 应该包括: h264_cuvid, h264_qsv, h264_amf
```

### 2.2 创建 RTP 到 PyAV 的管道

**文件**: `src/agent/xbox/rtp_to_decoder.py`

**目的**: 连接 RTP 会话和 PyAV 解码器，实现无缝帧处理

```python
class RTPDecoderPipeline:
    """
    RTP 数据包处理管道到 PyAV 解码器
    
    流程:
    RTP 数据包 -> H.264 解析器 -> PyAV 解码器 -> numpy 数组
    """
    
    def __init__(
        self,
        rtp_session: RTPSession,
        decoder: PyAVH264Decoder
    ):
        self._rtp = rtp_session
        self._decoder = decoder
        
    async def start(self) -> AsyncIterator[np.ndarray]:
        """处理 RTP 流并生成解码后的帧"""
        
    def _parse_h264_nalu(self, payload: bytes) -> List[bytes]:
        """从 RTP payload 解析 H.264 NALU"""
```

***

## 🔒 阶段 3: 进程隔离架构

### 3.1 创建流媒体进程管理器

**文件**: `src/agent/streaming/streaming_process_manager.py`

**目的**: 管理每个流媒体实例作为独立进程

**核心组件**:

```python
class StreamingProcessManager:
    """
    Xbox 流媒体实例的进程管理器
    
    设计原则:
    - 每个流媒体实例一个进程
    - 每个进程内异步 I/O
    - 用于控制命令的 IPC
    - 隔离的故障处理
    """
    
    def __init__(self):
        self._processes: Dict[str, multiprocessing.Process] = {}
        self._process_configs: Dict[str, StreamingConfig] = {}
        
    async def start_streaming_instance(
        self,
        instance_id: str,
        config: StreamingConfig,
        tokens: TokenBundle
    ) -> bool:
        """
        在单独进程中启动新的流媒体实例
        
        参数:
            instance_id: 此实例的唯一标识符
            config: 流媒体配置
            tokens: 认证令牌
            
        返回:
            如果启动成功返回 True
        """
        
    async def stop_streaming_instance(self, instance_id: str):
        """停止并清理流媒体实例"""
        
    async def get_instance_status(self, instance_id: str) -> InstanceStatus:
        """获取流媒体实例的当前状态"""
        
    def _streaming_process_main(
        self,
        instance_id: str,
        config: dict,
        tokens: dict
    ):
        """
        流媒体进程的主函数
        
        在独立进程中运行，拥有隔离的资源
        """
```

### 3.2 定义流媒体配置

**文件**: `src/agent/streaming/config.py`

```python
@dataclass
class StreamingConfig:
    """流媒体实例配置"""
    
    # Xbox 连接
    xbox_ip: str
    xbox_port: int = 5050
    xbox_id: str = ""
    
    # 认证
    access_token: str
    user_hash: str
    
    # 视频设置
    video_width: int = 1920
    video_height: int = 1080
    video_framerate: int = 60
    video_bitrate: int = 5000000
    
    # 解码
    enable_hardware_acceleration: bool = True
    preferred_gpu: str = "auto"  # "nvidia", "amd", "intel", "auto"
    
    # 网络
    rtp_receive_port: int = 50500
    control_port: int = 50501
    
    # 进程设置
    priority: int = 0  # 进程优先级
    max_memory_mb: int = 2048
```

### 3.3 进程间通信

**文件**: `src/agent/streaming/ipc.py`

**目的**: 启用主进程和流媒体进程之间的通信

```python
class StreamingIPC:
    """
    流媒体实例的进程间通信
    
    使用 multiprocessing.Queue 进行命令/响应
    """
    
    async def send_command(
        self,
        instance_id: str,
        command: StreamingCommand
    ) -> CommandResponse:
        """发送命令到流媒体进程"""
        
    async def receive_status(
        self,
        instance_id: str,
        timeout: float = 1.0
    ) -> Optional[InstanceStatus]:
        """从流媒体进程接收状态更新"""
        
    def register_status_callback(
        self,
        instance_id: str,
        callback: Callable[[InstanceStatus], None]
    ):
        """注册状态更新回调"""
```

**命令类型**:

```python
class StreamingCommand(Enum):
    START_STREAM = "start_stream"
    STOP_STREAM = "stop_stream"
    PAUSE_STREAM = "pause_stream"
    SEND_INPUT = "send_input"
    GET_STATUS = "get_status"
    RESTART_DECODER = "restart_decoder"
```

***

## 🎮 阶段 4: 输入控制系统

### 4.1 数据通道输入处理器

**文件**: `src/agent/streaming/input_handler.py`

**目的**: 通过 WebRTC 数据通道发送游戏手柄输入

```python
class DataChannelInputHandler:
    """
    通过 WebRTC 数据通道发送游戏手柄输入
    
    协议:
    - JSON 编码的输入状态
    - 高频更新使用二进制编码
    """
    
    def __init__(self, data_channel: RTCDataChannel):
        self._channel = data_channel
        
    async def send_gamepad_state(self, state: GamepadState):
        """发送完整游戏手柄状态"""
        
    async def send_button_press(self, button: str, pressed: bool):
        """发送单个按钮事件"""
        
    async def send_analog_input(
        self, 
        stick: str, 
        x: float, 
        y: float
    ):
        """发送模拟摇杆输入"""
```

***

## 📡 阶段 5: 网络控制服务

### 5.1 移除 PySide6 GUI

**要移除/修改的文件**:

* 移除: 所有 PySide6/Qt GUI 组件

* 修改: 主入口点作为服务运行

### 5.2 创建网络控制服务器

**文件**: `src/agent/streaming/control_server.py`

**目的**: HTTP/WebSocket 服务器，用于控制流媒体实例

```python
class StreamingControlServer:
    """
    流媒体实例的网络控制服务器
    
    提供 REST API 和 WebSocket 用于:
    - 实例生命周期管理
    - 实时状态流
    - 输入控制
    - 配置更新
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080
    ):
        self._app = FastAPI()
        self._manager = StreamingProcessManager()
        
    async def start(self):
        """启动控制服务器"""
        
    # REST 端点:
    @app.post("/api/streaming/start")
    async def start_instance(request: StartInstanceRequest):
        """启动新的流媒体实例"""
        
    @app.post("/api/streaming/{instance_id}/stop")
    async def stop_instance(instance_id: str):
        """停止流媒体实例"""
        
    @app.get("/api/streaming/{instance_id}/status")
    async def get_status(instance_id: str):
        """获取实例状态"""
        
    @app.post("/api/streaming/{instance_id}/input")
    async def send_input(instance_id: str, input_data: InputData):
        """发送输入到实例"""
        
    # 用于实时更新的 WebSocket:
    @app.websocket("/ws/streaming/{instance_id}")
    async def websocket_status(websocket, instance_id: str):
        """实时状态更新"""
```

### 5.3 主入口点 (服务模式)

**文件**: `src/main_service.py`

```python
async def main():
    """
    流媒体服务的主入口点
    
    作为后台服务运行，由网络 API 控制
    """
    config = load_config()
    
    # 初始化日志
    setup_logging(config.log_level)
    
    # 创建并启动控制服务器
    control_server = StreamingControlServer(
        host=config.host,
        port=config.port
    )
    
    # 启动服务器
    await control_server.start()
    
    # 保持运行
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

***

## 🧪 阶段 6: 测试和验证

### 6.1 测试 WebRTC 连接

**文件**: `tests/test_aiortc_webrtc.py`

```python
async def test_webrtc_connection():
    """测试到 Xbox 的 WebRTC 连接"""
    
    # 1. 设置 WebRTC 客户端
    client = AiortcWebRTCClient()
    
    # 2. 连接到 Xbox
    connected = await client.connect(xbox_info, sdp_offer)
    assert connected
    
    # 3. 接收帧
    frame_count = 0
    async for frame in client.receive_video_frames():
        frame_count += 1
        if frame_count >= 30:  # 测试 1 秒 30fps
            break
    
    assert frame_count > 0
```

### 6.2 测试 PyAV 硬件解码

**文件**: `tests/test_pyav_decoder.py`

```python
async def test_hardware_decoding():
    """测试 PyAV 硬件加速 H.264 解码"""
    
    decoder = PyAVH264Decoder(enable_hwaccel=True)
    await decoder.initialize(1920, 1080)
    
    # 检查硬件加速是否激活
    info = decoder.get_decoder_info()
    assert info['hardware_accelerated'] in [True, False]  # 两者都有效
    
    # 测试解码
    frame = await decoder.decode_frame(h264_test_data)
    assert frame is not None
```

### 6.3 测试进程隔离

**文件**: `tests/test_process_isolation.py`

```python
async def test_process_isolation():
    """测试流媒体实例运行在独立进程中"""
    
    manager = StreamingProcessManager()
    
    # 启动两个实例
    await manager.start_streaming_instance("test1", config1, tokens)
    await manager.start_streaming_instance("test2", config2, tokens)
    
    # 检查进程是独立的
    proc1 = manager._processes["test1"]
    proc2 = manager._processes["test2"]
    
    assert proc1.pid != proc2.pid
    
    # 停止一个并验证另一个继续运行
    await manager.stop_streaming_instance("test1")
    
    status2 = await manager.get_instance_status("test2")
    assert status2.state == StreamingState.RUNNING
```

***

## 📊 性能测试

### 7.1 基准测试脚本

**文件**: `scripts/benchmark_streaming.py`

```python
async def benchmark_streaming():
    """基准测试流媒体性能"""
    
    # 要收集的指标:
    metrics = {
        'fps': [],
        'decode_time_ms': [],
        'latency_ms': [],
        'cpu_percent': [],
        'gpu_percent': [],
        'memory_mb': []
    }
    
    # 运行 60 秒
    async with AiortcWebRTCClient() as client:
        start_time = time.time()
        
        while time.time() - start_time < 60:
            frame_start = time.time()
            frame = await client.receive_frame()
            frame_time = (time.time() - frame_start) * 1000
            
            metrics['fps'].append(1 / (frame_time / 1000))
            metrics['decode_time_ms'].append(frame_time)
            
            # 系统指标
            metrics['cpu_percent'].append(psutil.cpu_percent())
            metrics['memory_mb'].append(psutil.Process().memory_info().rss / 1024 / 1024)
            
    # 报告结果
    print_average_metrics(metrics)
```

***

## 📝 实施顺序

### 阶段 1: 核心 WebRTC (第 1 周)

1. 创建 `aiortc_webrtc_client.py`
2. 集成现有 SDP 处理器
3. 测试 WebRTC 连接

### 阶段 2: 视频解码 (第 1-2 周)

1. 创建 `pyav_decoder.py`
2. 验证硬件加速
3. 创建 RTP 到解码器管道

### 阶段 3: 进程隔离 (第 2 周)

1. 创建 `streaming_process_manager.py`
2. 实现 IPC 机制
3. 添加进程生命周期管理

### 阶段 4: 输入控制 (第 2 周)

1. 创建 `data_channel_input_handler.py`
2. 测试输入延迟

### 阶段 5: 控制服务器 (第 3 周)

1. 移除 PySide6 依赖
2. 创建 `control_server.py`
3. 创建 `main_service.py`

### 阶段 6: 测试 (第 3-4 周)

1. 每个组件的单元测试
2. 集成测试
3. 性能基准测试
4. 稳定性测试

***

## 🔧 配置文件

### `configs/streaming_service.yaml`

```yaml
streaming:
  service:
    host: "0.0.0.0"
    port: 8080
    max_instances: 10
    
  video:
    default_width: 1920
    default_height: 1080
    default_framerate: 60
    default_bitrate: 5000000
    
  decoding:
    enable_hardware_acceleration: true
    preferred_gpu: "auto"  # nvidia, amd, intel, auto
    decoder_threads: 4
    
  network:
    rtp_port_range_start: 50500
    rtp_port_range_end: 50600
    control_port_range_start: 50601
    control_port_range_end: 50700
    
  process:
    max_memory_per_instance_mb: 2048
    max_cpu_percent: 80
    restart_on_error: true
    
  logging:
    level: "INFO"
    file: "logs/streaming_service.log"
```

***

## ⚠️ 已知挑战

### 1. PyAV 硬件加速

**问题**: 默认 PyAV 分发可能不包含硬件加速
**解决方案**:

```bash
# 检查 PyAV 是否在构建时支持硬件
python -c "import av; print(av.codec.codecs_available)"

# 如果缺失，使用支持 NVENC/NVDEC 的 FFmpeg 重新编译 PyAV
pip install --no-binary av av
conda install ffmpeg nv-codec-headers
```

### 2. aiortc 性能

**问题**: aiortc 可能比 C++ 实现有更高的 CPU 开销
**解决方案**:

* 使用带有优化的最新 aiortc 版本

* 监控性能并添加进程优先级调整

* 考虑使用编译的 aiortc 扩展

### 3. Xbox SDP 兼容性

**问题**: Xbox 可能使用非标准 SDP 扩展
**解决方案**:

* 保留现有 SDP 生成器作为参考

* 使用各种 Xbox 固件版本进行测试

* 添加 SDP 协商详情的日志记录

***

## ✅ 成功标准

1. **功能**: 成功连接到 Xbox 并接收视频流
2. **性能**: 在 1080p 下达到 30+ FPS，解码延迟 <50ms
3. **稳定性**: 运行 1 小时无崩溃或内存泄漏
4. **隔离**: 一个实例崩溃不影响其他实例
5. **控制**: 所有实例可通过网络 API 控制

***

## 📚 参考资料

* aiortc 文档: <https://aiortc.readthedocs.io/>

* PyAV 文档: <https://pyav.org/docs/stable/>

* Xbox 流媒体协议: 见 `XSTREAMING_ARCHITECTURE.md`

* WebRTC H.264: RFC 6184

* SRTP: RFC 3711

