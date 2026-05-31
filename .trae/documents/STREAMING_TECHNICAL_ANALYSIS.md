# Xbox Streaming 项目技术分析文档

## 项目概述

本项目是一个 **Xbox 远程串流与自动化控制系统**，通过 PC 连接到 Xbox 主机，实现远程画面传输和自动化游戏操作。

---

## 一、项目架构

```
streaming/
├── xsrp/                          # C++ 编译的串流核心模块
│   ├── xsrpwrapper.cp39-win_amd64.pyd  # Python 扩展模块
│   └── *.dll                      # FFmpeg/SDL2 动态库
├── xsplayer.py                    # WebRTC 播放器示例
├── xsrp.py                        # 串流核心 Python 封装
├── xsrputil.py                    # 手柄控制与配置工具
├── xsrpst.py                      # 场景识别与模板匹配
├── accutil.py                     # 账号管理工具
├── payload.py                     # 数据包定义与序列化
├── logutil.py                     # 日志工具
├── data/                         # 配置文件
│   ├── keybinding.csv            # 键盘-手柄映射配置
│   └── gamecontrollerdb.txt      # SDL2 手柄映射库
├── capture/                       # 截图存放目录
└── ui/                           # Qt UI 界面文件
```

---

## 二、技术栈详解

### 2.1 核心技术组件

| 组件 | 技术 | 用途 |
|------|------|------|
| **视频解码** | FFmpeg (libavcodec) | 硬件加速 H.264 解码 |
| **窗口渲染** | SDL2 | 自行绘制串流窗口 |
| **手柄控制** | SDL2 GameController | 读取物理手柄 / 模拟虚拟手柄 |
| **GUI 界面** | PySide6 (Qt6) | 控制台界面 |
| **图像处理** | OpenCV (cv2) | 模板匹配 |
| **网络通信** | HTTP REST API | 与后端 FC 服务通信 |
| **进程管理** | multiprocessing | 多进程串流管理 |

---

## 三、微软账号认证流程

### 3.1 认证机制概述

项目使用 **Xbox Live 授权服务** 进行账号认证，认证流程涉及以下步骤：

```
┌─────────────┐     1. 设备码认证      ┌─────────────────┐
│   Xbox     │ ──────────────────────▶│   Xbox Live    │
│   Console  │                       │   授权服务器    │
└─────────────┘                       └─────────────────┘
       │                                      │
       │     2. 获取 Refresh Token            │
       ▼                                      ▼
┌─────────────┐                       ┌─────────────────┐
│   本地 PC   │ ◀─────────────────────│   XBL Auth     │
│   串流程序  │     3. 返回 Token      │   服务          │
└─────────────┘                       └─────────────────┘
```

### 3.2 认证流程详解

根据 `xsplayer.py` 中的 `test_offer_sdp` 函数，认证流程如下：

#### 步骤 1：获取 Bearer Token
```python
# Token 包含用户身份信息
token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkUxQTVGQTBELUhBMEItNDAxRC..."
# Token 解码后包含:
# - xuid: Xbox User ID (如 "2535461863327221")
# - deviceId: 设备ID
# - pusId: 发布者ID
# -puid: Xbox Live 用户ID
```

#### 步骤 2：发现 Xbox 主机
```python
# 调用 Xbox Live 服务器 API 获取在线主机列表
url_servers = 'https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home'
headers = {'Authorization': f'Bearer {token}'}

# 响应示例:
# {
#   "totalItems": 1,
#   "results": [{
#     "serverId": "F4001DF754519C00",
#     "playPath": "v5/sessions/home/play",
#     "powerState": "On",
#     "consoleType": "XboxSeriesS"
#   }]
# }
```

#### 步骤 3：建立串流会话
```python
# 创建播放会话
url_play = f'{url_root}/{play_path}'
data_play = {
    "clientSessionId": "",
    "titleId": "",  # 游戏 Title ID
    "serverId": server_id,
    "settings": {
        "nanoVersion": "V3;WebrtcTransport.dll",
        "osName": "windows",
        "sdkType": "web",
        "useIceConnection": False
    }
}
```

#### 步骤 4：交换 SDP 建立 WebRTC 连接
```python
# 发送 offer SDP
url = f'{url_root}/{session_path}/sdp'
data_sdp = {
    "messageType": "offer",
    "sdp": x.sdp,  # WebRTC Offer
    "configuration": {
        "chatConfiguration": {"codec": "opus", ...},
        "control": {"minVersion": 1, "maxVersion": 3},
        "input": {"minVersion": 1, "maxVersion": 8}
    }
}
```

### 3.3 认证关键点

| 关键点 | 说明 |
|--------|------|
| **Token 有效期** | Refresh Token 长期有效，Bearer Token 有时效 |
| **设备码认证** | 支持 OAuth 2.0 设备码流程 |
| **多设备支持** | 同一账号可授权多台设备 |
| **权限范围** | Token 包含用户身份、Xbox Live 权限等 |

---

## 四、显卡解码方案

### 4.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Xbox 主机 (发送端)                        │
│  游戏画面 ──▶ H.264 编码 ──▶ RTP 流 ──▶ 网络传输            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PC (接收端)                               │
│  网络接收 ──▶ RTP 解封装 ──▶ H.264 解码 ──▶ SDL2 渲染      │
│                                  │                          │
│                                  ▼                          │
│                           GPU 硬件解码 (NVIDIA/AMD/Intel)    │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 解码实现

#### 核心模块: `xsrpwrapper` (C++ 扩展)

```python
# 加载串流模块
import xsrpwrapper as xsrp

# 打开串流
errno = xsrp.OpenStreaming(
    username,      # 账号邮箱
    password,      # 账号密码
    host,          # Xbox 主机 IP
    port,          # 串流端口
    session,       # 会话密钥
    video_file,    # 视频文件路径
    title,         # 窗口标题
    hwaccels,      # 硬件加速器标识 (如 "h264")
    width,         # 视频宽度
    height,        # 视频高度
    gamepadIndex   # 手柄索引
)
```

#### 关键配置

```python
# 视频解码参数
DECODE_VIDEO_WIDTH = 1280
DECODE_VIDEO_HEIGHT = 720
DECODE_VIDEO_FPS = 30
DECODE_HARDWARE_ACCELS = "h264"  # 使用 H.264 硬件解码
```

### 4.3 硬件加速支持

| 平台 | 硬件加速方案 |
|------|-------------|
| **NVIDIA** | CUDA NVDEC (通过 FFmpeg) |
| **AMD** | AMD VCE/UVD (通过 FFmpeg) |
| **Intel** | Quick Sync Video (通过 FFmpeg) |
| **通用** | 软件解码 (libavcodec) 作为回退 |

---

## 五、自绘窗口实现

### 5.1 SDL2 窗口渲染

项目使用 **SDL2** 自行绘制串流窗口，不依赖系统窗口：

```python
class StreamWindow(QMainWindow):
    def __init__(self, work_state, queue_work_command, queue_work_state, conf):
        # 初始化 Xbox 串流模块
        xsrp.Init()

        # 设置窗口标题
        self.setWindowTitle(self.xsrp_conf.title)

        # 设置窗口尺寸
        self.setFixedSize(QSize(self.xsrp_conf.width, self.xsrp_conf.height))

        # 创建显示组件
        self.label_frame = QLabel()
```

### 5.2 视频帧显示流程

```python
@Slot(object)
def show_capture(self, captured: np.ndarray):
    if self.stream_state == StreamWindow.STREAM_ON:
        if captured.size > 0:
            # 获取游戏画面
            self.game_mat = captured

            # 缩放画面
            self.capture_mat = cv2.resize(
                self.game_mat.copy(),
                (self.xsrp_conf.width, self.xsrp_conf.height),
                interpolation=cv2.INTER_LINEAR
            )

            # 色彩空间转换 (BGR → RGB)
            rgb_image = cv2.cvtColor(self.capture_mat, cv2.COLOR_BGR2RGB)

            # 转换为 Qt 图像
            h, w, c = rgb_image.shape
            qimage = QImage(rgb_image.data, w, h, c * w, QImage.Format_RGB888)

            # 更新显示
            self.label_frame.setPixmap(QPixmap.fromImage(qimage))
```

### 5.3 窗口工作线程

```python
# 截图线程
self.task_capture = QThread()
self.worker_capture = WorkerCapture(conf)
self.worker_capture.moveToThread(self.task_capture)

# 链接信号
self.task_capture.started.connect(self.worker_capture.run)
self.worker_capture.signal_capture.connect(self.show_capture)
self.worker_capture.signal_finished.connect(self.task_capture.quit)

# 启动线程
self.task_capture.start()
```

---

## 六、模板匹配详解

### 6.1 模板匹配原理

使用 **OpenCV 的 matchTemplate** 函数进行图像区域匹配：

```python
# 模板匹配核心代码
result = cv2.matchTemplate(src_mat, template_mat, method)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
```

### 6.2 支持的匹配算法

```python
cv.TM_SQDIFF = 0        # 平方差匹配 (越小越好)
cv.TM_SQDIFF_NORMED = 1  # 归一化平方差
cv.TM_CCORR = 2          # 相关匹配
cv.TM_CCORR_NORMED = 3   # 归一化相关
cv.TM_CCOEFF = 4         # 相关系数
cv.TM_CCOEFF_NORMED = 5  # 归一化相关系数
```

### 6.3 模板定义结构

每个场景包含多个模板定义：

```python
schema = [
    2,      # 场景编号---【西瓜主页界面】
    960,    # 场景显示宽度
    540,    # 场景显示高度

    1,      # 场景的模板 编号---【西瓜图标】
    42,     # 模板 左上角 X
    108,    # 模板 左上角 Y
    45,     # 模板 右下角 X
    130,    # 模板 右下角 Y

    1,      # 查找区域编号
    40,     # 查找区域 左上角 X
    106,    # 查找区域 左上角 Y
    47,     # 查找区域 右下角 X
    132,    # 查找区域 右下角 Y
    90,     # 相似度阈值 (90%)
    3       # 比对算法编号 (TM_CCORR_NORMED)
]
```

### 6.4 场景识别流程

```python
def recognize_scenes(capture_mat, limit_ids) -> int:
    # 1. 加载所有场景模板
    df_templates = get_templates_schema()

    # 2. 逐个识别候选场景
    for candidate_scene_id in candidate_scene_ids:
        result, mean_likeness = recognize_scene(
            capture_mat,
            candidate_scene_id,
            df_templates,
            templates
        )
        if result:
            matched_scene_ids += [(candidate_scene_id, mean_likeness)]

    # 3. 返回相似度最高的场景
    return ret_scene_id
```

### 6.5 模板生成

```python
def generate_templates():
    # 从场景截图中提取模板区域
    scene_mat = cv2.imread(f'scene/{scene_id}.png')

    # 根据定义裁剪模板区域
    template_mat = scene_mat[y1:y2, x1:x2]

    # 保存模板
    cv2.imwrite(f'template/{scene_id}.{template_id}.png', template_mat)
```

---

## 七、自动模拟手柄

### 7.1 手柄控制架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    手柄输入处理流程                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  物理手柄 ──▶ SDL2 读取 ──▶ 虚拟手柄 ──▶ XSRP 协议 ──▶ Xbox    │
│                                                                  │
│  键盘映射 ──▶ 手柄模拟 ──▶ XSRP 协议 ──▶ Xbox                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 手柄初始化

```python
class XsrpController:
    def __init__(self, id: int):
        # 初始化 SDL2
        sdl2.SDL_Init(sdl2.SDL_INIT_EVERYTHING)

        # 启用手柄事件
        sdl2.SDL_JoystickEventState(sdl2.SDL_ENABLE)
        sdl2.SDL_GameControllerEventState(sdl2.SDL_ENABLE)

        # 打开手柄
        self.controller = sdl2.SDL_GameControllerOpen(id)
```

### 7.3 读取物理手柄

```python
def read(self):
    controller = xsrp.XSGamePad()

    # 读取按钮状态
    if sdl2.SDL_GameControllerGetButton(self.controller, sdl2.SDL_CONTROLLER_BUTTON_A):
        controller.Buttons |= xsrp.XSGamepadButtons.A

    # 读取摇杆
    controller.LeftThumbstickX = sdl2.SDL_GameControllerGetAxis(
        self.controller, sdl2.SDL_CONTROLLER_AXIS_LEFTX
    )
    controller.LeftThumbstickY = sdl2.SDL_GameControllerGetAxis(
        self.controller, sdl2.SDL_CONTROLLER_AXIS_LEFTY
    )

    return controller
```

### 7.4 键盘到手柄映射

```python
class KeyBinding:
    # 键盘-手柄映射配置
    KEY_SEQ = "KeySeq"

    # 键盘码定义
    KEY_A = 27
    KEY_B = 40
    KEY_X = 37
    KEY_Y = 22
    KEY_UP = 13
    KEY_DOWN = 14
    # ...

# 映射配置 (keybinding.csv)
# TapSeq,KeySeq
# TAP_A, KEY_A    (A键 → 键盘 A)
# TAP_B, KEY_B    (B键 → 键盘 B)
```

### 7.5 发送手柄数据

```python
def write_controller_final(self, signals: list):
    # 发送手柄数据到 Xbox
    xsrp.WriteControllerData(self.xsrp_conf.username, signals)

    # 记录发送时间
    self.controller_written_timestamp = time.time()
```

### 7.6 手柄数据包结构

```python
class XSGamePad:
    GamepadIndex: int       # 手柄索引
    Buttons: int            # 按钮状态位掩码
    LeftTrigger: int        # 左扳机 [0-32767]
    RightTrigger: int       # 右扳机 [0-32767]
    LeftThumbstickX: int   # 左摇杆 X [-32768-32767]
    LeftThumbstickY: int   # 左摇杆 Y [-32768-32767]
    RightThumbstickX: int  # 右摇杆 X
    RightThumbstickY: int  # 右摇杆 Y
```

### 7.7 摇杆角度转换

```python
@staticmethod
def GetAxisOffset(orientation: float):
    # 将角度转换为摇杆偏移量
    offset_x = math.floor(AXIS_RANGE_MAX * math.cos(orientation))
    offset_y = math.floor(AXIS_RANGE_MAX * math.sin(orientation))
    return [offset_x, offset_y]
```

---

## 八、与后端 FC 服务通信

### 8.1 通信架构

```
┌──────────────────────────────────────────────────────────────┐
│                    PC 串流客户端                              │
│                                                              │
│  游戏画面 ──▶ Frame Payload ──▶ HTTP POST ──▶ FC 服务      │
│                              │                               │
│                              ▼                               │
│                      FC 服务处理                             │
│                              │                               │
│              ┌───────────────┼───────────────┐             │
│              ▼               ▼               ▼              │
│        场景识别        帧分析处理        手柄指令            │
│              │               │               │              │
│              └───────────────┼───────────────┘             │
│                              │                               │
│                              ▼                               │
│                    HTTP Response                            │
│                     Scene/Controller Payload                 │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 数据包类型

```python
class PayloadBase:
    PAYLOAD_TYPE_CONFIG = 0x01   # 配置数据包
    PAYLOAD_TYPE_FRAME = 0x02    # 帧数据包
    PAYLOAD_TYPE_REPORT = 0x03   # 报告数据包
    PAYLOAD_TYPE_SCENE = 0x04    # 场景数据包
    PAYLOAD_TYPE_CONTROLLER = 0x05  # 手柄数据包

    PAYLOAD_ACTION_INIT = 0x01    # 初始化动作
    PAYLOAD_ACTION_PLAY = 0x02    # 播放动作
    PAYLOAD_ACTION_GRAPH = 0x03   # 图形/场景动作
    PAYLOAD_ACTION_TERMINATE = 0x04  # 终止动作
```

### 8.3 远程游戏初始化

```python
def remote_game_init(self):
    payload = PayloadConfig(
        PayloadBase.PAYLOAD_ACTION_INIT,
        PayloadBase.PAYLOAD_TYPE_CONFIG,
        username,
        session_token,
        gamepad_index,
        video_height,
        video_width
    )

    reply = payload_request_response_http(fc_host, fc_port, payload.to_packet())
    report = PayloadReport.UnpackReport(reply)

    # 获取会话密钥
    self.session_token = report.session
    return report.errno
```

### 8.4 发送游戏帧

```python
def remote_game_play(self, input_frame):
    payload = PayloadFrame(
        PayloadBase.PAYLOAD_ACTION_PLAY,
        PayloadBase.PAYLOAD_TYPE_FRAME,
        username,
        gamepad_index,
        session_token,
        frame_seq,
        "",
        input_frame,  # 游戏画面
        []            # 手柄操作
    )

    reply = payload_request_response_http(fc_host, fc_port, payload.to_packet())

    # 解析返回的手柄指令
    controller = PayloadController.UnpackController(reply)

    # 执行返回的手柄操作
    for action in controller.controller_actions:
        self.write_controller(action)
```

---

## 九、项目流程总结

### 9.1 启动流程

```
1. 加载账号配置
   └── 读取 CSV 配置文件

2. 初始化 Xbox 串流
   └── xsrp.Init()

3. 建立 WebRTC 连接
   └── 认证 → 发现主机 → 建立会话 → SDP 交换

4. 启动工作线程
   ├── 截图线程 (QThread)
   ├── 手柄线程 (threading)
   ├── 游戏处理线程 (threading)
   └── 流程控制线程 (threading)
```

### 9.2 自动化游戏流程

```
1. 场景识别
   └── 截图 → 模板匹配 → 识别场景 ID

2. 场景决策
   ├── 非比赛场景 → 导航操作
   ├── 比赛中场景 → 启动自动比赛
   └── 比赛结束场景 → 结算操作

3. 自动比赛
   ├── 发送游戏帧
   ├── 接收手柄指令
   └── 执行手柄操作
```

---

## 十、关键文件说明

| 文件 | 说明 |
|------|------|
| `xsrp.py` | 串流核心，封装 xsrpwrapper C++ 模块 |
| `xsrputil.py` | 手柄控制、配置管理、模板定义 |
| `xsrpst.py` | 场景识别、模板生成、模板匹配 |
| `accutil.py` | Xbox 账号读取与管理 |
| `payload.py` | 数据包序列化/反序列化 |
| `xsrpd.py` | 守护进程入口 |
| `xsrpst.py` | 场景识别与模板匹配核心 |

---

*文档版本: 1.0*
*最后更新: 2026-05-30*
