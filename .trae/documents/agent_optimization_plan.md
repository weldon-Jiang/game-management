> **架构勘误（2026-06-13）**：生产 Step2–3 为 **xblive/xsrp（GSSV 云端 + WebRTC）**，入口见 `bend-agent/src/agent/automation/step2_xsrp.py`、`step3_xsrp.py`。下文 SmartGlass LAN、`step2_xbox_streaming.py` 等为**历史方案**；SmartGlass UDP 仅作 LAN 发现/唤醒兜底。详见 [00_架构勘误_xsrp_step2.md](./00_架构勘误_xsrp_step2.md)。

# Agent 性能优化计划报告

**版本**: 1.0
**创建日期**: 2026-05-30
**基于**: STREAMING_TECHNICAL_ANALYSIS.md 技术分析

---

## 一、概述

### 1.1 背景

Bend Agent 是安装在用户 Windows 电脑上的桌面客户端程序，负责：
- 与后端平台（WebSocket）通信
- 控制 Xbox 主机执行游戏自动化
- 捕获游戏画面进行场景识别
- 模拟手柄输入控制游戏

### 1.2 问题分析

streaming 项目使用 C++ FFmpeg + SDL2 实现高性能串流，Agent 使用纯 Python 实现存在性能差距：

| 维度 | streaming | Agent | 差距 |
|------|----------|-------|------|
| 视频解码 | FFmpeg GPU | win32gui截图 | ⚠️ 10x性能差距 |
| 窗口渲染 | SDL2自绘 | 系统窗口 | ⚠️ 控制能力差 |
| 画面捕获 | SDL Surface | 窗口截图 | ⚠️ 效率低 |
| 延迟 | <100ms | 较高 | ⚠️ 影响响应 |

### 1.3 优化目标

- 视频解码：使用 FFmpeg GPU 硬件解码
- 窗口渲染：使用 SDL2 自绘窗口
- 画面捕获：统一使用 pygame.surfarray
- 延迟目标：<150ms（performance模式）

---

## 二、步骤与优化对应关系

### 2.1 优化任务映射

```
┌─────────────────────────────────────────────────────────────────────┐
│                    四步骤优化任务映射                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  步骤一：串流账号登录认证                                             │
│  ├── ✅ 无需优化（认证功能已完整）                                    │
│  └── 优化内容：无                                                   │
│                                                                      │
│  步骤二：Xbox串流连接  ←─────────────────────────────────┐          │
│  ├── ⚠️ 需要优化                                        │          │
│  ├── 优化项：FFmpeg GPU解码                            │          │
│  └── 原因：视频流解码性能                               │          │
│                                                        │          │
│  步骤三：串流前期准备      ←─────────────────────────┐  │          │
│  ├── ⚠️ 需要优化                                │  │  │          │
│  ├── 优化项：SDL2自绘窗口                       │  │  │          │
│  └── 原因：画面捕获和渲染                        │  │          │
│                                                    │  │          │
│  步骤四：自动操作Xbox主机  ←──────────────────┐   │  │  │          │
│  ├── ⚠️ 需要优化                          │   │  │  │  │          │
│  ├── 优化项：手柄信号发送                   │   │  │  │  │          │
│  └── 优化项：场景识别优化                   │   │  │  │  │          │
│                                                    │   │  │  │          │
└────────────────────────────────────────────────────┴───┴──┴──┴──────┘
```

### 2.2 优化步骤状态

| 优化步骤 | 对应步骤 | 名称 | 状态 | 优先级 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 优化一 | **步骤二** | FFmpeg GPU解码 | ✅ 已完成 | **P0** | 视频流解码 |
| 优化二 | **步骤三** | SDL2自绘窗口 | ✅ 已完成 | **P0** | 画面渲染 |
| 优化三 | **步骤四** | 手柄信号发送 | ✅ 已完成 | **P0** | 控制Xbox |
| **优化四** | **步骤四** | **场景识别优化** | **✅ 已完成** | **P1** | 检测效率 |

### 2.3 当前优化步骤

> **🎉 所有优化已完成！**

---

## 🎉 全部优化任务已完成！

| 优化 | 对应步骤 | 名称 | 状态 | 优先级 |
| --- | --- | --- | --- | --- |
| 优化一 | 步骤二 | FFmpeg GPU解码 | ✅ 已完成 | **P0** |
| 优化二 | 步骤三 | SDL2自绘窗口 | ✅ 已完成 | **P0** |
| 优化三 | 步骤四 | 手柄信号发送 | ✅ 已完成 | **P0** |
| 优化四 | 步骤四 | 场景识别优化 | ✅ 已完成 | **P1** |

---

## 三、优化一（对应步骤二）：FFmpeg GPU解码

### 3.1 执行状态

| 项目 | 内容 |
| --- | --- |
| **所属步骤** | 步骤二：Xbox串流连接 |
| **状态** | ✅ 已完成 |
| **开始时间** | 2026-05-30 |
| **完成时间** | 2026-05-30 |
| **优先级** | **P0** |

### 3.2 现状分析

**streaming 实现**：

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Xbox主机  │───▶│ FFmpeg   │───▶│ 解码帧   │
│ H.264流  │    │ GPU解码   │    │          │
└──────────┘    └──────────┘    └──────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
     NVDEC          AMF           QSV
    (NVIDIA)       (AMD)        (Intel)
```

**Agent 当前实现**：

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Xbox主机  │───▶│ 视频流   │───▶│ win32gui │───▶ OpenCV
│ H.264流  │    │ (未解码) │    │ 截图     │
└──────────┘    └──────────┘    └──────────┘
```

### 3.3 缺失功能

| 缺失项 | streaming实现 | Agent | 优先级 |
| --- | --- | --- | --- |
| FFmpeg解码器 | ✅ libavcodec | ❌ 无 | **P0** |
| GPU硬件加速 | ✅ NVDEC/AMF | ❌ 无 | **P0** |
| 帧管理 | ✅ 同步/异步 | ❌ 无 | P1 |

### 3.4 实现方案

#### 3.4.1 技术选型

| 方案 | 库 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **方案A** | imageio-ffmpeg | 轻量、易用 | 需处理解码流程 |
| 方案B | PyAV | Pythonic API | 依赖复杂 |
| 方案C | ffmpeg-python | 灵活 | 性能略低 |

**推荐方案**：imageio-ffmpeg（方案A）

#### 3.4.2 新增文件

```
src/agent/vision/
├── gpu_frame_capture.py    ← 新增
└── gpu_decoder.py          ← 新增
```

#### 3.4.3 核心代码设计

**gpu_decoder.py** - GPU解码器：

```python
class GPUDecoder:
    """GPU硬件解码器"""

    def __init__(self):
        self.decoder = None
        self.gpu_type = None  # nvidia/amd/intel/cpu

    def detect_gpu(self) -> str:
        """自动检测可用GPU"""
        # 1. 尝试 NVIDIA NVDEC
        # 2. 尝试 AMD AMF
        # 3. 尝试 Intel QSV
        # 4. 回退到 CPU 解码
        pass

    def create_decoder(self, codec: str = 'h264'):
        """创建解码器"""
        pass
```

**gpu_frame_capture.py** - GPU帧捕获器：

```python
class GPUFrameCapture:
    """GPU加速的视频帧捕获器"""

    def __init__(self, stream_url: str = None):
        self.decoder = GPUDecoder()
        self.reader = None

    async def initialize(self, stream_url: str) -> bool:
        """初始化GPU解码"""
        pass

    async def read_frame(self) -> Optional[np.ndarray]:
        """读取解码后的帧"""
        pass

    def get_stats(self) -> dict:
        """获取解码统计"""
        pass
```

#### 3.4.4 GPU检测策略

```python
def detect_available_gpu():
    """检测可用GPU"""
    gpu_priority = ['nvidia', 'amd', 'intel']

    for gpu_type in gpu_priority:
        if gpu_available(gpu_type):
            return gpu_type

    return 'cpu'  # 回退到CPU解码

def gpu_available(gpu_type: str) -> bool:
    """检查GPU是否可用"""
    try:
        if gpu_type == 'nvidia':
            import torch
            return torch.cuda.is_available()
        elif gpu_type == 'amd':
            # 检查 DirectX/Vulkan
            pass
        elif gpu_type == 'intel':
            # 检查 Quick Sync
            pass
    except:
        return False
    return False
```

### 3.5 依赖项

```txt
# requirements.txt 新增
imageio-ffmpeg>=0.4.0
torch>=2.0.0  # 可选，用于GPU检测
```

### 3.6 集成到现有代码

**修改文件**：`src/agent/vision/frame_capture.py`

```python
class VideoFrameCapture:
    """视频帧捕获器（优化版）"""

    def __init__(self, window, use_gpu: bool = True):
        self.window = window
        self.use_gpu = use_gpu

        # 选择捕获方式
        if use_gpu:
            self.gpu_capture = GPUFrameCapture()
        else:
            self.capture = None  # 回退到原方式

    async def initialize(self, stream_url: str = None):
        """初始化捕获器"""
        if self.use_gpu and stream_url:
            await self.gpu_capture.initialize(stream_url)
        else:
            # 使用原有截图方式
            pass
```

### 3.7 性能目标

| 指标 | 优化前 | 优化后 | 提升 |
| --- | --- | --- | --- |
| 帧率 | 10-15fps | 30-60fps | 3-4x |
| CPU占用 | 30-50% | 10-20% | 降低 |
| 延迟 | >200ms | <150ms | 改善 |

### 3.8 执行记录

| 日期 | 操作 | 结果 | 确认人 |
| --- | --- | --- | --- |
| 2026-05-30 | 创建GPUDecoder类 | ✅ 完成 | - |
| 2026-05-30 | 创建GPUFrameCapture类 | ✅ 完成 | - |
| 2026-05-30 | 更新VideoFrameCapture集成GPU | ✅ 完成 | - |
| 2026-05-30 | 更新step2_xsrp.py | ✅ 完成 | - |
| 2026-05-30 | 添加依赖项 | ✅ 完成 | - |

---

## 四、优化二（对应步骤三）：SDL2自绘窗口

### 4.1 执行状态

| 项目 | 内容 |
| --- | --- |
| **所属步骤** | 步骤三：串流前期准备 |
| **状态** | ✅ 已完成 |
| **开始时间** | 2026-05-30 |
| **完成时间** | 2026-05-30 |
| **优先级** | **P0** |

### 4.2 现状分析

**streaming 实现**：

```
┌──────────────────────────────────────┐
│           SDL2 自绘窗口              │
│  ┌────────────────────────────────┐ │
│  │                                │ │
│  │        游戏画面渲染             │ │
│  │                                │ │
│  └────────────────────────────────┘ │
│              │                       │
│              ▼                       │
│  ┌────────────────────────────────┐ │
│  │     pygame.surfarray           │ │
│  │     → numpy数组 → OpenCV       │ │
│  └────────────────────────────────┘ │
└──────────────────────────────────────┘
```

**Agent 当前实现**：

```
┌──────────────────────────────────────┐
│          win32gui 系统窗口           │
│  ┌────────────────────────────────┐ │
│  │                                │ │
│  │        游戏画面（不可控）       │ │
│  │                                │ │
│  └────────────────────────────────┘ │
│              │                       │
│              ▼                       │
│  ┌────────────────────────────────┐ │
│  │     win32gui.PrintWindow       │ │
│  │     → PIL → numpy → OpenCV    │ │
│  └────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### 4.3 缺失功能

| 缺失项 | streaming实现 | Agent | 优先级 |
| --- | --- | --- | --- |
| SDL2窗口 | ✅ SDL2 | ❌ 无 | **P0** |
| 自绘渲染 | ✅ 支持 | ❌ 无 | **P0** |
| pygame统一 | ✅ 可选 | ❌ 无 | P1 |

### 4.4 实现方案

#### 4.4.1 技术选型

| 方案 | 库 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **方案A** | pygame | 与手柄统一、简单 | UI能力弱 |
| 方案B | PySDL2 | 原生SDL2 | 需额外绑定 |
| 方案C | PySide6 | 功能强大 | 较重 |

**推荐方案**：pygame（方案A）- 与已实现的手柄控制器统一

#### 4.4.2 新增文件

```
src/agent/windows/
├── sdl_window.py           ← 新增
└── sdl_frame_capture.py    ← 新增
```

#### 4.4.3 核心代码设计

**sdl_window.py** - SDL自绘窗口：

```python
class SDLStreamWindow:
    """SDL2自绘串流窗口"""

    def __init__(self, width: int = 1280, height: int = 720):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = None
        self.running = False

    def initialize(self):
        """初始化窗口"""
        self.screen = pygame.display.set_mode(
            (self.width, self.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("Bend Agent - Xbox Streaming")
        self.running = True

    def update_frame(self, frame: np.ndarray):
        """更新画面"""
        # numpy → pygame Surface (RGB格式)
        surface = pygame.surfarray.make_surface(
            frame.swapaxes(0, 1)
        )
        self.screen.blit(pygame.transform.scale(
            surface, (self.width, self.height)
        ), (0, 0))
        pygame.display.flip()

    def capture_frame(self) -> np.ndarray:
        """捕获当前帧"""
        frame = pygame.surfarray.array3d(self.screen)
        return frame.swapaxes(0, 1)  # HWC格式

    def get_bgr_frame(self) -> np.ndarray:
        """获取BGR格式帧（用于OpenCV）"""
        frame = self.capture_frame()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def close(self):
        """关闭窗口"""
        self.running = False
        pygame.quit()
```

**sdl_frame_capture.py** - SDL帧捕获：

```python
class SDLFrameCapture:
    """SDL窗口帧捕获器"""

    def __init__(self, window: SDLStreamWindow):
        self.window = window
        self.frame_count = 0
        self.last_frame_time = 0

    async def capture_frame(self) -> Optional[np.ndarray]:
        """捕获帧"""
        return self.window.get_bgr_frame()

    def get_stats(self) -> dict:
        """获取捕获统计"""
        return {
            'frame_count': self.frame_count,
            'fps': self.calculate_fps(),
            'capture_time_ms': self.last_frame_time
        }

    def calculate_fps(self) -> float:
        """计算帧率"""
        pass
```

### 4.5 依赖项

```txt
# requirements.txt 已包含
pygame>=2.0.0
numpy>=1.20.0
opencv-python>=4.5.0
```

### 4.6 集成到现有代码

**修改文件**：`src/agent/windows/stream_window.py`

```python
class StreamWindow:
    """流窗口管理器（优化版）"""

    def __init__(self, use_sdl: bool = True):
        self.use_sdl = use_sdl

        if use_sdl:
            from .sdl_window import SDLStreamWindow
            self.sdl_window = SDLStreamWindow()
            self.frame_capture = SDLFrameCapture(self.sdl_window)
        else:
            # 回退到原win32gui方式
            self._init_win32gui()

    async def initialize(self):
        """初始化窗口"""
        if self.use_sdl:
            self.sdl_window.initialize()
        else:
            await self._init_win32gui()
```

### 4.7 性能目标

| 指标 | 优化前 | 优化后 | 提升 |
| --- | --- | --- | --- |
| 捕获延迟 | 50-100ms | 5-10ms | 5-10x |
| CPU占用 | 高 | 低 | 降低 |
| 显示控制 | 不可控 | 完全可控 | - |

### 4.8 执行记录

| 日期 | 操作 | 结果 | 确认人 |
| --- | --- | --- | --- |
| 2026-05-30 | 创建SDLStreamWindow类 | ✅ 完成 | - |
| 2026-05-30 | 创建SDLFrameCapture类 | ✅ 完成 | - |
| 2026-05-30 | 更新step3_xsrp.py | ✅ 完成 | - |
| 2026-05-30 | 更新windows/__init__.py | ✅ 完成 | - |

---

## 五、优化三（对应步骤四）：手柄信号发送

### 5.1 执行状态

| 项目 | 内容 |
| --- | --- |
| **所属步骤** | 步骤四：自动操作Xbox主机 |
| **状态** | ✅ 已完成 |
| **开始时间** | 2026-05-30 |
| **完成时间** | 2026-05-30 |
| **优先级** | **P0** |

### 5.2 现状分析

**streaming 实现**：

```cpp
// xsrpwrapper.cpp
void WriteControllerData(const char* username, const XSGamePad* signals) {
    // 发送到Xbox SmartGlass
    smartglass.send(username, signals);
}
```

**Agent 当前实现**：

```python
# controller_protocol.py
async def send_signal(self, signal: ControllerSignal):
    if not self._stream_controller:
        return False
    # ❌ 未完整实现
    await self._stream_controller.send_input("gamepad", signal.to_dict())
```

### 5.3 缺失功能

| 缺失项 | streaming实现 | Agent | 优先级 |
| --- | --- | --- | --- |
| 信号发送 | ✅ 完整实现 | ⚠️ 部分实现 | **P0** |
| 协议格式 | ✅ xsrp协议 | ⚠️ 待验证 | P1 |
| 响应延迟 | ✅ 低 | ⚠️ 待测试 | P1 |

### 5.4 实现方案

#### 5.4.1 Xbox SmartGlass 协议分析

```python
class SmartGlassProtocol:
    """SmartGlass协议"""

    # 按钮位掩码
    BUTTON_A = 0x0001
    BUTTON_B = 0x0002
    BUTTON_X = 0x0004
    BUTTON_Y = 0x0008
    # ...

    def pack_controller_data(self, signal: ControllerSignal) -> bytes:
        """打包控制器数据"""
        # 格式: buttons(2) + triggers(2) + left_x(2) + left_y(2) + right_x(2) + right_y(2)
        pass

    def unpack_response(self, data: bytes) -> dict:
        """解析响应"""
        pass
```

#### 5.4.2 完善发送逻辑

```python
class XboxStreamController:
    """Xbox流控制器（完善版）"""

    async def send_input(self, input_type: str, data: dict) -> bool:
        """发送输入到Xbox"""
        if input_type == "gamepad":
            return await self._send_gamepad(data)
        return False

    async def _send_gamepad(self, data: dict) -> bool:
        """发送手柄数据"""
        try:
            # 1. 打包数据
            protocol = SmartGlassProtocol()
            packet = protocol.pack_controller_data(
                ControllerSignal.from_dict(data)
            )

            # 2. 发送到SmartGlass
            await self._send_packet(packet)

            # 3. 等待响应
            response = await self._wait_response(timeout=1.0)

            return response.get('success', False)

        except Exception as e:
            logger.error(f"发送手柄数据失败: {e}")
            return False
```

### 5.5 集成到现有代码

**修改文件**：
- `src/agent/input/controller_protocol.py`
- `src/agent/xbox/stream_controller.py`

### 5.6 执行记录

| 日期 | 操作 | 结果 | 确认人 |
| --- | --- | --- | --- |
| 2026-05-30 | 完善Xbox SmartGlass协议 | ✅ 完成 | - |
| 2026-05-30 | 实现send_gamepad_state方法 | ✅ 完成 | - |
| 2026-05-30 | 更新ControllerProtocol | ✅ 完成 | - |
| 2026-05-30 | 更新step4_game_automation.py | ✅ 完成 | - |

---

## 六、优化四（对应步骤四）：场景识别优化

### 6.1 执行状态

| 项目 | 内容 |
| --- | --- |
| **所属步骤** | 步骤四：自动操作Xbox主机 |
| **状态** | ✅ 已完成 |
| **开始时间** | 2026-05-30 |
| **完成时间** | 2026-05-30 |
| **优先级** | P1 |

### 6.2 现状分析

**当前问题**：
- 每帧都进行模板匹配，CPU占用高
- 帧率受限于场景检测
- 场景切换响应慢

**优化方向**：
- 降频检测（每N帧检测一次）
- 增量检测（只检测变化区域）
- 缓存优化

### 6.3 实现方案

```python
class OptimizedSceneDetector:
    """优化的场景检测器"""

    def __init__(self, matcher, capture):
        self.matcher = matcher
        self.capture = capture
        self.frame_interval = 5  # 每5帧检测一次
        self.frame_count = 0
        self.last_scene = None
        self.last_scene_time = 0

    async def detect_scene(self, frame: np.ndarray) -> SceneState:
        """检测场景（优化版）"""
        self.frame_count += 1

        # 1. 检查是否需要检测
        if self.frame_count % self.frame_interval != 0:
            return self.last_scene

        # 2. 增量检测（如果有变化）
        scene = await self._detect_with_cache(frame)

        # 3. 更新状态
        if scene != self.last_scene:
            self.last_scene = scene
            self.last_scene_time = time.time()

        return scene

    async def _detect_with_cache(self, frame: np.ndarray) -> SceneState:
        """使用缓存的检测"""
        # 1. 检查画面是否有显著变化
        if self._is_scene_stable(frame):
            return self.last_scene  # 使用缓存

        # 2. 执行模板匹配
        return await self.matcher.find_scene(frame)
```

### 6.4 执行记录

| 日期 | 操作 | 结果 | 确认人 |
| --- | --- | --- | --- |
| 2026-05-30 | 创建OptimizedSceneDetector类 | ✅ 完成 | - |
| 2026-05-30 | 实现降频检测 | ✅ 完成 | - |
| 2026-05-30 | 实现增量检测优化 | ✅ 完成 | - |
| 2026-05-30 | 实现缓存机制 | ✅ 完成 | - |
| 2026-05-30 | 更新step4_game_automation.py | ✅ 完成 | - |

---

## 七、技术架构（优化后）

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Bend Agent 优化后架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  步骤二：Xbox串流连接                                        │   │
│  │                                                              │   │
│  │  H.264视频流 ──▶ FFmpeg GPU解码 ──▶ 解码帧              │   │
│  │                    ▲ 优化一                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  步骤三：串流前期准备                                        │   │
│  │                                                              │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │               SDL2 自绘窗口                           │  │   │
│  │  │                                                          │  │   │
│  │  │  ┌────────────────────────────────────────────────┐  │  │   │
│  │  │  │               游戏画面渲染                       │  │  │   │
│  │  │  └────────────────────────────────────────────────┘  │  │   │
│  │  │                          │                            │  │   │
│  │  │                          ▼                            │  │   │
│  │  │  ┌────────────────────────────────────────────────┐  │  │   │
│  │  │  │           pygame.surfarray → numpy             │  │  │   │
│  │  │  └────────────────────────────────────────────────┘  │  │   │
│  │  └──────────────────────────────────────────────────────┘  │   │
│  │                    ▲ 优化二                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│              ┌───────────────┴───────────────┐                       │
│              ▼                               ▼                       │
│  ┌──────────────────────────┐    ┌──────────────────────────────┐   │
│  │  步骤四：自动操作Xbox     │    │  步骤四：自动操作Xbox        │   │
│  │                          │    │                              │   │
│  │     场景检测              │    │     手柄控制                 │   │
│  │  (cv2模板匹配)           │    │  (pygame GamePad)          │   │
│  │     ▲ 优化四             │    │     ▲ 优化三                 │   │
│  └──────────────────────────┘    └──────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               Xbox SmartGlass 协议                       │   │
│  │                                                          │   │
│  │  手柄信号 ──▶ 协议打包 ──▶ 发送到 Xbox                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Xbox 主机                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 八、性能对比（预期）

| 指标 | 优化前 | 优化后 | 提升 | 说明 |
| --- | --- | --- | --- | --- |
| **视频解码帧率** | 10-15fps | 30-60fps | 3-4x | FFmpeg GPU |
| **画面捕获延迟** | 50-100ms | 5-10ms | 5-10x | SDL Surface |
| **场景检测帧率** | 5-8fps | 15-30fps | 3x | 降频优化 |
| **CPU占用** | 30-50% | 10-20% | 降低 | GPU解码 |
| **端到端延迟** | >200ms | <150ms | 改善 | 优化总延迟 |
| **手柄响应** | 待测试 | <50ms | - | 协议优化 |

---

## 九、风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
| --- | --- | --- | --- |
| GPU不可用 | 中 | 低 | 回退到CPU解码 |
| SDL2兼容问题 | 中 | 低 | 使用pygame兼容层 |
| 延迟仍然较高 | 中 | 中 | 进一步优化缓冲区 |
| streaming协议差异 | 高 | 中 | 参考streaming抓包分析 |

---

## 十、下一步行动

### 优化一：FFmpeg GPU解码（对应步骤二）

**所属步骤**：步骤二 - Xbox串流连接

**开始时间**：用户确认后

**任务清单**：
1. 创建 `src/agent/vision/gpu_decoder.py`
2. 创建 `src/agent/vision/gpu_frame_capture.py`
3. 更新 `src/agent/vision/frame_capture.py` 集成GPU捕获
4. 更新 `src/agent/automation/step2_xsrp.py` 使用GPU解码
5. 添加依赖项到 `requirements.txt`
6. 编写测试用例
7. 性能基准测试

---

*文档结束*
