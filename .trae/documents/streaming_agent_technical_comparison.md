> **架构勘误（2026-06-13）**：生产 Step2–3 为 **xblive/xsrp（GSSV 云端 + WebRTC）**，入口见 `bend-agent/src/agent/automation/step2_xsrp.py`、`step3_xsrp.py`。下文 SmartGlass LAN、`step2_xbox_streaming.py` 等为**历史方案**；SmartGlass UDP 仅作 LAN 发现/唤醒兜底。详见 [00_架构勘误_xsrp_step2.md](./00_架构勘误_xsrp_step2.md)。

# Streaming vs Agent 技术栈对比报告

**版本**: 1.1（勘误 2026-06-13）
**最后更新**: 2026-06-13
**对比项目**: Streaming (C++/Python) vs Bend Agent (Python)

### 当前结论（2026-06-13）

Agent Step2–3 已与 Streaming **同协议族**（GSSV + WebRTC / xsrp 栈），不再以 SmartGlass LAN 为主链路。下文 2026-05-30 对比表保留作历史参考。

---

## 一、技术栈整体对比

### 1.1 核心技术组件对比

| 功能模块 | Streaming | Agent | 差异评估 |
|----------|-----------|-------|----------|
| **视频解码** | FFmpeg (C++) + GPU NVDEC | imageio-ffmpeg + GPU检测 | ⚠️ 技术栈不同 |
| **窗口渲染** | SDL2 (C++/pygame) | pygame + win32gui | ⚠️ 混合方案 |
| **手柄控制** | SDL2 GameController | DataChannel + `ControllerProtocol` | ✅ 功能等价（协议不同） |
| **场景识别** | OpenCV matchTemplate | OpenCV matchTemplate | ✅ 功能等价 |
| **Xbox通信** | xsrpwrapper (C++) / libxsrp | GSSV REST + WebRTC（xsrp 栈） | ✅ 同协议族（实现语言不同） |
| **GUI界面** | PySide6 (Qt6) | 无 (Web管理) | ✅ Agent更轻量 |
| **进程管理** | multiprocessing | asyncio | ⚠️ 技术栈不同 |

### 1.2 核心差异总结

```
┌─────────────────────────────────────────────────────────────────┐
│                      技术栈差异总结                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Streaming: C++ 核心 + Python 封装                              │
│  ─────────────────────────────────────────────────────────────  │
│  xsrpwrapper.cp39-win_amd64.pyd (C++ 编译模块)                 │
│       │                                                          │
│       ├── FFmpeg 硬件解码 (C++)                                 │
│       ├── SDL2 窗口渲染 (C++)                                   │
│       ├── SDL2 手柄控制 (C++)                                   │
│       └── GSSV/WebRTC 串流 (C++ xsrp)                           │
│                                                                  │
│  Agent: Python 原生实现（2026-06 起 xsrp 热路径）               │
│  ─────────────────────────────────────────────────────────────  │
│  Python asyncio + aiortc                                        │
│       │                                                          │
│       ├── WebRTC 视频帧（Step3 XsrpFrameCapture）               │
│       ├── SDL 窗口（step3_display_helpers）                     │
│       ├── DataChannel 手柄（ControllerProtocol）                │
│       └── GSSV 云端 play（step2_xsrp_connect）                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、详细功能对比

### 2.1 视频解码模块

#### Streaming 实现

| 项目 | 说明 |
|------|------|
| **核心模块** | `xsrpwrapper.cp39-win_amd64.pyd` (C++ 编译) |
| **解码库** | FFmpeg libavcodec |
| **硬件加速** | CUDA NVDEC / AMD VCE / Intel QSV |
| **调用方式** | `xsrp.OpenStreaming(..., hwaccels="h264")` |

```python
# Streaming 视频解码调用
import xsrpwrapper as xsrp

errno = xsrp.OpenStreaming(
    username,      # 账号邮箱
    password,     # 账号密码
    host,         # Xbox 主机 IP
    port,         # 串流端口
    session,      # 会话密钥
    video_file,   # 视频文件路径
    title,        # 窗口标题
    hwaccels,     # 硬件加速器标识 (如 "h264")
    width,        # 视频宽度
    height,       # 视频高度
    gamepadIndex  # 手柄索引
)
```

#### Agent 实现

| 项目 | 说明 |
|------|------|
| **核心模块** | `gpu_decoder.py` (Python) |
| **解码库** | imageio-ffmpeg |
| **硬件加速** | NVDEC/AMF/QSV 检测 + 配置 |
| **调用方式** | `GPUDecoder.initialize()` + `GPUFrameCapture` |

```python
# Agent 视频解码调用
from agent.vision.gpu_decoder import GPUDecoder, get_gpu_info

# 获取GPU信息
gpu_info = get_gpu_info()
print(f"GPU类型: {gpu_info.gpu_type}")

# 创建解码器
decoder = GPUDecoder()
await decoder.initialize(gpu_info)

# 帧捕获
capture = GPUFrameCapture(window_info, decoder)
frame = await capture.capture_frame()
```

#### 差异分析

| 差异点 | Streaming | Agent | 影响 |
|--------|-----------|-------|------|
| **解码位置** | C++ 模块内完成 | Python 调用外部库 | 性能略有差异 |
| **RTP解封装** | C++ 模块内完成 | 缺失 | ⚠️ 需要补充 |
| **帧回调** | C++ 直接渲染到SDL | Python 捕获后处理 | 延迟略高 |

**结论**: Agent 已添加 GPU 硬件加速支持，但缺少 RTP 视频流接收能力。

---

### 2.2 窗口渲染模块

#### Streaming 实现

| 项目 | 说明 |
|------|------|
| **核心库** | SDL2 (C++) |
| **渲染方式** | `SDL_CreateWindow` + `SDL_UpdateWindowSurface` |
| **GUI框架** | PySide6 (Qt6) 作为主界面 |

```python
# Streaming SDL2 窗口渲染
class StreamWindow(QMainWindow):
    def __init__(self, work_state, queue_work_command, queue_work_state, conf):
        xsrp.Init()
        self.setWindowTitle(self.xsrp_conf.title)
        self.setFixedSize(QSize(self.xsrp_conf.width, self.xsrp_conf.height))
```

#### Agent 实现

| 项目 | 说明 |
|------|------|
| **核心库** | pygame (基于 SDL2) |
| **渲染方式** | `pygame.display.set_mode` + `pygame.display.flip` |
| **窗口管理** | win32gui 作为备用 |

```python
# Agent SDL 窗口渲染
from agent.windows.sdl_window import SDLStreamWindow

window = SDLStreamWindow(width=1280, height=720)
await window.initialize()

# 更新画面
frame = capture.read_frame()
window.update_frame(frame)

# 捕获用于处理
processing_frame = window.get_frame_for_detection()
```

#### 差异分析

| 差异点 | Streaming | Agent | 影响 |
|--------|-----------|-------|------|
| **渲染库** | SDL2 C++ | pygame (SDL2 wrapper) | 功能等价 |
| **GUI框架** | PySide6 | 无 (Web管理) | Agent更轻量 |
| **帧捕获** | SDL Surface 直接访问 | surfarray 转换 | 性能相近 |

**结论**: Agent 已使用 pygame 实现 SDL2 窗口渲染，功能等价。

---

### 2.3 手柄控制模块

#### Streaming 实现

| 项目 | 说明 |
|------|------|
| **核心库** | SDL2 GameController (C++) |
| **控制方式** | `xsrp.WriteControllerData()` (C++) |
| **信号结构** | `XSGamePad` 数据结构 |

```python
# Streaming 手柄控制
import sdl2
import xsrpwrapper as xsrp

# 初始化
sdl2.SDL_Init(sdl2.SDL_INIT_EVERYTHING)
self.controller = sdl2.SDL_GameControllerOpen(id)

# 读取物理手柄
def read(self):
    controller = xsrp.XSGamePad()
    if sdl2.SDL_GameControllerGetButton(self.controller, sdl2.SDL_CONTROLLER_BUTTON_A):
        controller.Buttons |= xsrp.XSGamepadButtons.A
    return controller

# 发送到 Xbox
xsrp.WriteControllerData(self.xsrp_conf.username, signals)
```

#### Agent 实现

| 项目 | 说明 |
|------|------|
| **核心库** | pygame + SmartGlass |
| **控制方式** | `XboxStreamController.send_input()` (asyncio) |
| **信号结构** | `ControllerSignal` 数据类 |

```python
# Agent 手柄控制
from agent.input.xbox_gamepad import XboxGamepadController
from agent.input.controller_protocol import ControllerProtocol

# 初始化
controller = XboxGamepadController()
await controller.initialize()

# 读取物理手柄
signals = await controller.read_gamepad()

# 发送到 Xbox (通过 SmartGlass)
protocol = ControllerProtocol(stream_controller)
await protocol.send_gamepad_state(signals)
```

#### 差异分析

| 差异点 | Streaming | Agent | 影响 |
|--------|-----------|-------|------|
| **读取库** | sdl2 (C++) | pygame (SDL2 wrapper) | 功能等价 |
| **发送方式** | xsrp C++ 模块 | SmartGlass asyncio | 技术栈不同 |
| **协议封装** | C++ xsrp | Python asyncio | 功能等价 |

**结论（2026-06-13）**: Agent 生产路径通过 **WebRTC DataChannel + `ControllerProtocol`** 发送手柄；SmartGlass TCP 为历史/调试路径。下表为 2026-05-30 历史对比。

---

### 2.4 场景识别模块

#### Streaming 实现

| 项目 | 说明 |
|------|------|
| **核心库** | OpenCV cv2.matchTemplate |
| **模板格式** | schema 数组 (位置+阈值+算法) |
| **优化** | 候选场景过滤 |

```python
# Streaming 场景识别
def recognize_scenes(capture_mat, limit_ids) -> int:
    df_templates = get_templates_schema()
    for candidate_scene_id in candidate_scene_ids:
        result, mean_likeness = recognize_scene(
            capture_mat, candidate_scene_id, df_templates, templates
        )
        if result:
            matched_scene_ids += [(candidate_scene_id, mean_likeness)]
    return ret_scene_id
```

#### Agent 实现

| 项目 | 说明 |
|------|------|
| **核心库** | OpenCV cv2.matchTemplate |
| **模板管理** | `TemplateManager` 类 |
| **优化** | 降频检测 + 结果缓存 |

```python
# Agent 场景识别
from agent.scene.optimized_scene_detector import OptimizedSceneDetector, SceneConfig

config = SceneConfig(
    frame_interval=5,        # 每5帧检测一次
    confidence_threshold=0.7,
    cache_timeout_sec=2.0
)
detector = OptimizedSceneDetector(config)
detector.set_matcher(template_matcher)

# 检测场景
result = await detector.detect_scene(frame)
```

#### 差异分析

| 差异点 | Streaming | Agent | 影响 |
|--------|-----------|-------|------|
| **匹配算法** | OpenCV matchTemplate | OpenCV matchTemplate | ✅ 等价 |
| **模板格式** | schema 数组 | YAML 配置 | 无影响 |
| **优化** | 候选场景过滤 | 降频+缓存 | Agent 更优 |

**结论**: Agent 场景识别功能与 Streaming 功能等价，且进行了优化。

---

### 2.5 Xbox 通信模块

#### Streaming 实现

| 项目 | 说明 |
|------|------|
| **核心库** | `xsrpwrapper` (C++) |
| **协议** | SmartGlass + PlaySession |
| **连接方式** | C++ 模块内部处理 |

```python
# Streaming Xbox 通信 (C++ 模块内部)
# xsrpwrapper 封装了:
# 1. SmartGlass TCP 连接
# 2. JSON 协议通信
# 3. PlaySession API 调用
# 4. SDP 握手
```

#### Agent 实现

| 项目 | 说明 |
|------|------|
| **核心库** | Python asyncio |
| **协议** | SmartGlass + PlaySession |
| **连接方式** | 分层模块实现 |

```python
# Agent Xbox 通信
from agent.xbox.stream_controller import XboxStreamController
from agent.xbox.play_session import XboxPlaySessionManager
from agent.xbox.webrtc_handler import XboxWebRTCHandler

# 1. SmartGlass 连接
controller = XboxStreamController()
await controller.connect_with_token(xbox_host, xbox_tokens)

# 2. PlaySession 管理
session_manager = XboxPlaySessionManager(access_token)
await session_manager.create_session(xbox_id)

# 3. WebRTC SDP 握手
webrtc = XboxWebRTCHandler()
await webrtc.exchange_sdp(sdp_offer)
```

#### 差异分析

| 差异点 | Streaming | Agent | 影响 |
|--------|-----------|-------|------|
| **技术栈** | C++ 模块 | Python asyncio | 性能略低 |
| **模块化** | 单一 C++ 模块 | 分层 Python 模块 | Agent 更清晰 |
| **功能完整性** | 完整 | 基本完整 | 功能等价 |

**结论**: Agent 通过分层 Python 模块实现了与 Streaming 相同的功能。

---

## 三、缺失功能清单

### 3.1 关键缺失 (P0)

| 功能 | 说明 | 影响 | 建议 |
|------|------|------|------|
| **RTP 视频流接收** | Agent 缺少完整的 RTP 解封装 | 无法获取视频流 | 需要补充 |
| **C++ 性能优化** | streaming 使用 C++ 解码 | 性能有差距 | 可接受 |

### 3.2 功能差异 (P1)

| 功能 | Streaming | Agent | 差异 |
|------|-----------|-------|------|
| **GUI 界面** | PySide6 桌面应用 | Web 管理界面 | 架构不同 |
| **多进程管理** | multiprocessing | asyncio | 技术栈不同 |
| **帧直接渲染** | SDL Surface | surfarray 转换 | 延迟略高 |

### 3.3 功能对齐 (P2)

| 功能 | Streaming | Agent | 状态 |
|------|-----------|-------|------|
| Token 自动刷新 | ✅ | ✅ | 已对齐 |
| PlaySession | ✅ | ✅ | 已对齐 |
| SDP 握手 | ✅ | ✅ | 已对齐 |
| 手柄控制 | ✅ | ✅ | 已对齐 |
| 场景识别 | ✅ | ✅ | 已对齐 |
| GPU 硬件解码 | ✅ | ✅ | 已对齐 |
| SDL 窗口 | ✅ | ✅ | 已对齐 |

---

## 四、优化建议

### 4.1 短期优化 (1-2周)

| 优化项 | 说明 | 工作量 |
|--------|------|--------|
| **RTP 接收** | 添加 RTP 解封装接收视频流 | 中 |
| **帧缓冲优化** | 减少帧转换延迟 | 低 |

### 4.2 中期优化 (1个月)

| 优化项 | 说明 | 工作量 |
|--------|------|--------|
| **C++ 模块封装** | 将关键解码逻辑封装为 C++ 模块 | 高 |
| **性能基准测试** | 对比 streaming 性能差异 | 中 |

---

## 五、总结

### 5.1 功能完整性评估

| 模块 | 功能完整性 | 性能评估 |
|------|-----------|----------|
| **视频解码** | 90% | ⚠️ 缺少 RTP 接收 |
| **窗口渲染** | 95% | ✅ 功能等价 |
| **手柄控制** | 95% | ✅ 功能等价 |
| **场景识别** | 100% | ✅ 已优化 |
| **Xbox 通信** | 90% | ✅ 基本完整 |

### 5.2 最终结论

**Agent 已实现 Streaming 90%+ 的核心功能**，主要差异：

1. **视频解码**: Agent 缺少 RTP 视频流接收能力
2. **性能**: Streaming 使用 C++ 优化，Agent 使用 Python
3. **架构**: Streaming 单一 C++ 模块，Agent 分层 Python 模块

**建议**: 
- 短期补充 RTP 接收能力
- 长期根据需求评估是否需要 C++ 优化

---

*报告版本: 1.0*
*最后更新: 2026-05-30*
