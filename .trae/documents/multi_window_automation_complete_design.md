# 多窗口自动化串流系统 - 完整版设计方案

## 一、设计目标

| 目标 | 说明 |
|------|------|
| **多账号并行** | 多个串流账号同时运行自动化，互不干扰 |
| **独立窗口** | 每个账号对应一个 Electron 窗口 + 独立的 VideoFrameCapture |
| **窗口自由操作** | 窗口可拖拽、最小化、隐藏（不支持最大化） |
| **实时视频流** | 从 Xbox 获取实时视频帧用于图像识别 |
| **模板匹配** | 基于视频帧的实时模板匹配（归一化坐标 0-1） |
| **B端管理** | 统一管理账号、监控状态、下发任务 |
| **游戏账号切换** | 支持自动化切换 Xbox 游戏账号 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           XStreaming 管理平台 (B-End)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        Java Backend (Spring Boot)                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ Streaming   │  │   Game      │  │   Agent     │  │    Task     │  │  │
│  │  │ Account API  │  │ Account API │  │  API        │  │    API      │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    WebSocket Handler (实时推送)                   │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      │ HTTP / WebSocket                            │
└──────────────────────────────────────│──────────────────────────────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   Agent 1        │      │   Agent 2        │      │   Agent N        │
│ (Python进程)     │      │ (Python进程)     │      │ (Python进程)     │
└────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CentralManager (每个 Agent 内)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  StreamWindow 1  │  StreamWindow 2  │  StreamWindow 3  │  StreamWindow N  │  │
│  │  (串流账号1)     │  (串流账号2)     │  (串流账号3)     │  (串流账号N)    │  │
│  │                  │                  │                  │                  │  │
│  │  ┌────────────┐ │  ┌────────────┐ │  ┌────────────┐ │  ┌────────────┐ │  │
│  │  │  可拖拽    │ │  │  可拖拽    │ │  │  可拖拽    │ │  │  可拖拽    │ │  │
│  │  │ Electron  │ │  │ Electron  │ │  │ Electron  │ │  │ Electron  │ │  │
│  │  │  窗口     │ │  │  窗口     │ │  │  窗口     │ │  │  窗口     │ │  │
│  │  └────────────┘ │  └────────────┘ │  └────────────┘ │  └────────────┘ │  │
│  │        │        │        │        │        │        │        │        │  │
│  │        ▼        │        ▼        │        ▼        │        ▼        │  │
│  │  ┌──────────┐  │  ┌──────────┐  │  ┌──────────┐  │  ┌──────────┐  │  │
│  │  │VideoFrame│  │  │VideoFrame│  │  │VideoFrame│  │  │VideoFrame│  │  │
│  │  │ Capture  │  │  │ Capture  │  │  │ Capture  │  │  │ Capture  │  │  │
│  │  └──────────┘  │  └──────────┘  │  └──────────┘  │  └──────────┘  │  │
│  │        │        │        │        │        │        │        │        │  │
│  │        ▼        │        ▼        │        ▼        │        ▼        │  │
│  │  ┌──────────┐  │  ┌──────────┐  │  ┌──────────┐  │  ┌──────────┐  │  │
│  │  │ Template │  │  │ Template │  │  │ Template │  │  │ Template │  │  │
│  │  │ Matcher  │  │  │ Matcher  │  │  │ Matcher  │  │  │ Matcher  │  │  │
│  │  └──────────┘  │  └──────────┘  │  └──────────┘  │  └──────────┘  │  │
│  │        │        │        │        │        │        │        │        │  │
│  │        ▼        │        ▼        │        ▼        │        ▼        │  │
│  │  ┌──────────┐  │  ┌──────────┐  │  ┌──────────┐  │  ┌──────────┐  │  │
│  │  │  Input   │  │  │  Input   │  │  │  Input   │  │  │  Input   │  │  │
│  │  │Controller│  │  │Controller│  │  │Controller│  │  │Controller│  │  │
│  │  └──────────┘  │  └──────────┘  │  └──────────┘  │  └──────────┘  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件

### 3.1 CentralManager (中央管理器)

**职责**：
- 管理多个 StreamWindow 实例
- 分配唯一 Instance ID
- 接收后端任务并分发
- 汇总状态上报后端

```python
class CentralManager:
    def __init__(self, backend_url: str, agent_id: str):
        self.backend_url = backend_url
        self.agent_id = agent_id
        self.windows: Dict[str, StreamWindow] = {}
        self.running = True

    async def register_to_backend(self):
        """向后端注册 Agent"""
        await ApiClient.register_agent(
            agent_id=self.agent_id,
            host=socket.gethostname(),
            port=CONFIG.AGENT_PORT
        )

    async def start_streaming_account(self, account_config: AccountConfig) -> str:
        """
        为串流账号启动独立窗口
        返回 instance_id
        """
        instance_id = f"{self.agent_id}_{account_config.id}_{len(self.windows)}"

        # 1. 创建独立 Electron 窗口
        window = StreamWindow(
            instance_id=instance_id,
            config=account_config,
            on_state_change=self._on_window_state_change
        )

        # 2. 初始化并启动
        await window.init()
        await window.start_streaming()

        # 3. 保存实例
        self.windows[instance_id] = window

        # 4. 启动该窗口的自动化循环
        asyncio.create_task(window.run_automation())

        return instance_id

    async def stop_instance(self, instance_id: str):
        """停止指定实例"""
        if instance_id in self.windows:
            await self.windows[instance_id].close()
            del self.windows[instance_id]

    async def _on_window_state_change(self, instance_id: str, state: WindowState):
        """窗口状态变更回调"""
        # 上报状态到后端
        await ApiClient.update_instance_status(
            agent_id=self.agent_id,
            instance_id=instance_id,
            state=state.value
        )
```

### 3.2 StreamWindow (串流窗口)

**职责**：
- 管理单个串流账号的独立 Electron 窗口
- 绑定 xStreamingPlayer 视频流
- 执行自动化逻辑

```python
class StreamWindow:
    def __init__(self, instance_id: str, config: AccountConfig,
                 on_state_change: Callable):
        self.instance_id = instance_id
        self.config = config
        self.on_state_change = on_state_change

        self.state = WindowState.INITIALIZING
        self.xplayer = None
        self.frame_capture = None
        self.template_matcher = None
        self.input_controller = None

        # 创建独立 BrowserWindow
        self.browser_window = self._create_browser_window()

    def _create_browser_window(self):
        """创建独立的 Electron 窗口"""
        window = BrowserWindow({
            'width': 1280,
            'height': 720,
            'title': f"串流-{self.config.name}",
            'webPreferences': {
                'nodeIntegration': False,
                'contextIsolation': True,
                'preload': self._get_preload_path()
            }
        })

        # 支持拖拽
        window.setMovable(True)

        # 加载串流页面
        window.loadURL(f"http://localhost:{CONFIG.MANAGER_PORT}/stream.html?instance={self.instance_id}")

        return window

    async def init(self):
        """初始化组件"""
        self.state = WindowState.INITIALIZING
        self._notify_state_change()

        # 等待页面加载完成
        await self._wait_for_page_ready()

        # 获取 xStreamingPlayer 实例
        self.xplayer = await self._get_xplayer()

        # 初始化帧捕获器
        video_element = await self._get_video_element()
        self.frame_capture = VideoFrameCapture(video_element)

        # 初始化模板匹配器
        self.template_matcher = TemplateMatcher()
        await self.template_matcher.load_templates(CONFIG.TEMPLATE_DIR)

        # 初始化输入控制器
        self.input_controller = InputController(self.xplayer)

        self.state = WindowState.READY
        self._notify_state_change()

    async def start_streaming(self):
        """启动串流"""
        self.state = WindowState.CONNECTING
        self._notify_state_change()

        # 通过 IPC 启动串流
        session_id = await IpcClient.start_stream(
            target=self.config.server_id,
            type='home'
        )

        self.session_id = session_id
        self.state = WindowState.CONNECTED
        self._notify_state_change()

    async def run_automation(self):
        """执行自动化循环"""
        self.state = WindowState.AUTOMATING
        self._notify_state_change()

        while self.state == WindowState.AUTOMATING:
            try:
                # 1. 捕获当前帧
                frame = self.frame_capture.capture_frame()

                # 2. 模板匹配
                match_result = self.template_matcher.match(frame, 'login_button')

                if match_result.found:
                    # 检测到登录按钮
                    await self._handle_login_button(match_result)
                    continue

                # 检查其他状态...
                await self._check_and_handle_states(frame)

            except Exception as e:
                logger.error(f"[{self.instance_id}] 自动化异常: {e}")

            await asyncio.sleep(0.1)  # ~10fps

    def _handle_login_button(self, match):
        """处理登录按钮点击"""
        # 使用归一化坐标点击
        self.input_controller.click_at_normalized(match.x, match.y)
        logger.info(f"[{self.instance_id}] 点击登录按钮")
```

### 3.3 VideoFrameCapture (视频帧捕获器)

**职责**：从视频流捕获帧，使用归一化坐标

```python
class VideoFrameCapture:
    def __init__(self, video_element):
        self.video = video_element
        self.canvas = None
        self.ctx = None

    def capture_frame(self) -> np.ndarray:
        """
        捕获当前视频帧
        返回 BGR 格式的 numpy 数组
        """
        if self.canvas is None:
            self.canvas = np.zeros((self.video.videoHeight,
                                    self.video.videoWidth, 3), dtype=np.uint8)

        # 绘制当前帧
        self.ctx.drawImage(self.video, 0, 0,
                          self.video.videoWidth, self.video.videoHeight)

        # 获取像素数据并转换为 BGR
        pixels = np.array(self.ctx.getImageData(0, 0,
                         self.video.videoWidth, self.video.videoHeight).data)
        frame = pixels.reshape((self.video.videoHeight,
                                self.video.videoWidth, 4))
        frame = frame[:, :, :3][:, :, ::-1]  # RGBA -> BGR

        return frame

    def get_coordinate_transform(self) -> CoordinateTransform:
        """
        获取坐标变换矩阵
        用于处理 letterbox/pillarbox 黑边
        """
        video_w = self.video.videoWidth
        video_h = self.video.videoHeight
        client_w = self.video.clientWidth
        client_h = self.video.clientHeight

        video_aspect = video_w / video_h
        client_aspect = client_w / client_h

        if video_aspect > client_aspect:
            # 视频更宽，按宽度填充
            scale = client_w / video_w
            offset_y = (client_h - video_h * scale) / 2
            offset_x = 0
        else:
            # 视频更高，按高度填充
            scale = client_h / video_h
            offset_x = (client_w - video_w * scale) / 2
            offset_y = 0

        return CoordinateTransform(
            offset_x=offset_x,
            offset_y=offset_y,
            scale=scale
        )

### 3.4 OCRTextMatcher (文字识别匹配器)

**职责**：从视频帧中识别文字并匹配目标字符串

```python
class OCRTextMatcher:
    """
    基于 OCR 的文字识别匹配器
    使用 EasyOCR 或 PaddleOCR 进行文字识别
    """

    def __init__(self):
        self.reader = None  # OCR 引擎
        self.text_cache = {}  # 缓存识别结果

    async def initialize(self, use_gpu: bool = True):
        """初始化 OCR 引擎"""
        try:
            import easyocr
            self.reader = easyocr.Reader(
                ['ch_sim', 'en'],  # 中文 + 英文
                gpu=use_gpu,
                verbose=False
            )
            logger.info("EasyOCR 引擎初始化完成")
        except ImportError:
            logger.warning("EasyOCR 未安装，尝试使用 PaddleOCR")
            try:
                from paddleocr import PaddleOCR
                self.reader = PaddleOCR(
                    use_angle_cls=True,
                    lang='ch',
                    use_gpu=use_gpu,
                    show_log=False
                )
                logger.info("PaddleOCR 引擎初始化完成")
            except ImportError:
                raise RuntimeError("请安装 easyocr 或 paddleocr")

    def recognize_text(self, frame: np.ndarray) -> List[Dict]:
        """
        识别帧中的所有文字

        Returns:
            List of dicts: [{'text': 'Hello', 'bbox': (x1,y1,x2,y2), 'center': (x,y)}, ...]
        """
        # 转换为 RGB (EasyOCR 需要)
        frame_rgb = frame[:, :, ::-1]

        # OCR 识别
        if hasattr(self.reader, 'readtext'):
            # EasyOCR
            results = self.reader.readtext(frame_rgb)
        else:
            # PaddleOCR
            results = self.reader.ocr(frame_rgb, cls=True)

        # 解析结果
        text_items = []
        for item in results:
            if hasattr(self.reader, 'readtext'):
                # EasyOCR 格式: (bbox, text, confidence)
                bbox = item[0]
                text = item[1]
                confidence = item[2]
            else:
                # PaddleOCR 格式: [[bbox], text, confidence]
                bbox = item[0]
                text = item[1]
                confidence = item[2][0] if isinstance(item[2], list) else item[2]

            # 计算边界框中心和归一化坐标
            x1 = min(p[0] for p in bbox)
            y1 = min(p[1] for p in bbox)
            x2 = max(p[0] for p in bbox)
            y2 = max(p[1] for p in bbox)

            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            text_items.append({
                'text': text.strip(),
                'bbox': (x1, y1, x2, y2),
                'center': (center_x, center_y),
                'norm_center': (center_x / frame.shape[1], center_y / frame.shape[0]),
                'confidence': confidence
            })

        return text_items

    def find_text(self, frame: np.ndarray, target: str,
                  match_type: str = 'exact') -> Optional[Dict]:
        """
        在帧中查找指定文字

        Args:
            frame: 视频帧 (BGR 格式)
            target: 要查找的文字
            match_type: 'exact'(完全匹配), 'contains'(包含), 'fuzzy'(模糊匹配)

        Returns:
            匹配的文字信息，包含归一化坐标，或 None
        """
        text_items = self.recognize_text(frame)

        target_lower = target.lower()

        for item in text_items:
            text_lower = item['text'].lower()

            if match_type == 'exact' and text_lower == target_lower:
                return item
            elif match_type == 'contains' and target_lower in text_lower:
                return item
            elif match_type == 'fuzzy' and self._fuzzy_match(target_lower, text_lower):
                return item

        return None

    def _fuzzy_match(self, s1: str, s2: str, threshold: float = 0.8) -> bool:
        """模糊匹配 (基于编辑距离)"""
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, s1, s2).ratio()
        return ratio >= threshold

    def wait_for_text(self, frame_getter, target: str,
                      timeout: float = 30,
                      match_type: str = 'exact') -> Optional[Dict]:
        """
        等待指定文字出现

        Args:
            frame_getter: 获取当前帧的函数
            target: 要等待的文字
            timeout: 超时时间(秒)
            match_type: 匹配方式

        Returns:
            匹配的文字信息，或 None (超时)
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            frame = frame_getter()
            result = self.find_text(frame, target, match_type)
            if result:
                return result
            time.sleep(0.5)

        return None
```

### 3.5 InputController (输入控制器)

```python
class InputController:
    def __init__(self, xplayer):
        self.xplayer = xplayer

    def click_at_normalized(self, norm_x: float, norm_y: float):
        """
        使用归一化坐标点击 (0-1)
        自动处理黑边偏移
        """
        transform = self.frame_capture.get_coordinate_transform()

        # 归一化坐标 -> 视频像素坐标
        video_x = norm_x * self.video.videoWidth
        video_y = norm_y * self.video.videoHeight

        # 视频像素坐标 -> 显示坐标
        display_x = video_x * transform.scale + transform.offset_x
        display_y = video_y * transform.scale + transform.offset_y

        # 移动光标到位置
        self._move_cursor(display_x, display_y)

        # 点击 A 确认
        self._press_button('A')

    def _move_cursor(self, x: float, y: float):
        """移动光标到指定显示坐标"""
        # Xbox 光标移动逻辑
        # 使用 D-Pad 或摇杆移动
        pass

    def _press_button(self, button: str):
        """按下按钮"""
        processor = self.xplayer.getChannelProcessor('input')
        processor.pressButtonStart(button)
        time.sleep(0.1)
        processor.pressButtonEnd(button)
```

### 3.6 HybridMatcher (综合匹配器)

结合模板匹配和 OCR 文字识别，根据场景选择最优匹配方式：

```python
class HybridMatcher:
    """
    综合匹配器 - 结合模板匹配和 OCR
    自动选择最佳匹配方式
    """

    def __init__(self):
        self.template_matcher = TemplateMatcher()
        self.ocr_matcher = OCRTextMatcher()
        self._initialized = False

    async def initialize(self, template_dir: str, use_gpu: bool = True):
        """初始化所有匹配器"""
        await self.template_matcher.load_templates(template_dir)
        await self.ocr_matcher.initialize(use_gpu=use_gpu)
        self._initialized = True

    MatchResult = namedtuple('MatchResult', ['found', 'method', 'data', 'norm_coords'])

    def match(self, frame: np.ndarray, target: str) -> MatchResult:
        """
        综合匹配

        Args:
            frame: 视频帧
            target: 目标 (模板名或文字)

        Returns:
            MatchResult(found, method, data, norm_coords)
        """
        if not self._initialized:
            raise RuntimeError("Matcher 未初始化")

        # 优先尝试模板匹配 (更快)
        template_result = self.template_matcher.match(frame, target)
        if template_result.found:
            return self.MatchResult(
                found=True,
                method='template',
                data=template_result,
                norm_coords=(template_result.x, template_result.y)
            )

        # 尝试 OCR 文字匹配
        ocr_result = self.ocr_matcher.find_text(frame, target, match_type='contains')
        if ocr_result:
            return self.MatchResult(
                found=True,
                method='ocr',
                data=ocr_result,
                norm_coords=ocr_result['norm_center']
            )

        return self.MatchResult(found=False, method=None, data=None, norm_coords=None)

    def match_any(self, frame: np.ndarray, targets: List[str]) -> Optional[MatchResult]:
        """
        匹配多个目标，返回第一个匹配的

        Args:
            frame: 视频帧
            targets: 目标列表

        Returns:
            第一个匹配的结果
        """
        for target in targets:
            result = self.match(frame, target)
            if result.found:
                return result
        return None

    async def wait_for_match(self, frame_getter, target: str,
                            timeout: float = 30) -> Optional[MatchResult]:
        """
        等待匹配成功

        Args:
            frame_getter: 获取帧的函数
            target: 目标
            timeout: 超时时间

        Returns:
            匹配结果或 None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            frame = frame_getter()
            result = self.match(frame, target)
            if result.found:
                return result
            time.sleep(0.3)

        return None
```

### 3.7 SceneBasedMatcher (场景智能匹配器)

根据当前场景自动选择最优匹配方式：

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Callable
import time

class Scene(Enum):
    """自动化场景枚举"""
    # 登录/认证场景 - 可用 OCR
    LOGIN = "login"
    AUTH = "auth"

    # 系统菜单场景 - 可用 OCR
    MENU = "menu"
    SETTINGS = "settings"
    ACCOUNT = "account"

    # 游戏/比赛场景 - 只用模板 (性能要求高)
    GAMING = "gaming"
    COMPETITION = "competition"  # 比赛模式，只用模板匹配

    # 串流场景 - 可用 OCR
    STREAMING = "streaming"

    # 通用场景 - 混合使用
    GENERAL = "general"


@dataclass
class MatcherConfig:
    """匹配器配置"""
    preferred_method: str = "auto"  # "template", "ocr", "auto"
    allow_ocr: bool = True
    allow_template: bool = True
    ocr_timeout_ms: int = 100  # OCR 超时
    template_timeout_ms: int = 50  # 模板匹配超时


class SceneBasedMatcher:
    """
    场景智能匹配器

    核心策略：
    - GAMING/COMPETITION 场景：只用模板匹配（延迟 < 20ms）
    - 其他场景：模板优先，OCR 作为 fallback
    """

    # 各场景配置
    SCENE_CONFIGS = {
        Scene.COMPETITION: MatcherConfig(
            preferred_method="template",
            allow_ocr=False,  # 比赛模式禁用 OCR
            allow_template=True
        ),
        Scene.GAMING: MatcherConfig(
            preferred_method="template",
            allow_ocr=False,  # 游戏模式禁用 OCR
            allow_template=True
        ),
        Scene.LOGIN: MatcherConfig(
            preferred_method="template",  # 优先模板
            allow_ocr=True,  # 但允许 OCR fallback
            allow_template=True
        ),
        Scene.MENU: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True
        ),
        Scene.SETTINGS: MatcherConfig(
            preferred_method="ocr",  # 设置界面文字多，用 OCR
            allow_ocr=True,
            allow_template=True
        ),
        Scene.ACCOUNT: MatcherConfig(
            preferred_method="ocr",
            allow_ocr=True,
            allow_template=True
        ),
        Scene.STREAMING: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True
        ),
        Scene.GENERAL: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True
        ),
    }

    # 目标 -> 推荐匹配方式 (场景 -> 方法)
    TARGET_RECOMMENDATIONS = {
        # 固定 UI 元素 - 优先模板
        'a_button': Scene.GAMING,
        'b_button': Scene.GAMING,
        'x_button': Scene.GAMING,
        'y_button': Scene.GAMING,
        'home_btn': Scene.GENERAL,
        'guide_icon': Scene.GENERAL,
        'back_btn': Scene.GENERAL,
        'menu_btn': Scene.MENU,

        # 文字按钮 - 根据场景决定
        'login_button': Scene.LOGIN,
        'sign_in_btn': Scene.LOGIN,
        'continue_btn': Scene.GENERAL,

        # Xbox 系统文字 - 用 OCR
        'Sign in': Scene.LOGIN,
        'Sign out': Scene.ACCOUNT,
        'Settings': Scene.SETTINGS,
        'Home': Scene.GENERAL,
        'Account': Scene.ACCOUNT,
        'My games': Scene.MENU,
        'Guide': Scene.GENERAL,
        'OK': Scene.GENERAL,
        'Cancel': Scene.GENERAL,
        'Confirm': Scene.GENERAL,
        'Back': Scene.GENERAL,
        '下一步': Scene.GENERAL,
        '取消': Scene.GENERAL,
        '确定': Scene.GENERAL,
    }

    def __init__(self, template_matcher, ocr_matcher):
        self.template_matcher = template_matcher
        self.ocr_matcher = ocr_matcher
        self.current_scene = Scene.GENERAL
        self._result_cache = {}  # 缓存匹配结果
        self._cache_ttl = 0.5  # 缓存 500ms

    def set_scene(self, scene: Scene):
        """设置当前场景"""
        self.current_scene = scene
        logger.info(f"场景切换: {scene.value}")

    def match(self, frame, target: str, force_method: str = None) -> Optional[dict]:
        """
        智能匹配

        Args:
            frame: 视频帧
            target: 目标 (模板名或文字)
            force_method: 强制使用的方法 ("template"/"ocr"/None)

        Returns:
            匹配结果
        """
        # 检查缓存
        cache_key = f"{target}:{self.current_scene.value}"
        if cache_key in self._result_cache:
            cached = self._result_cache[cache_key]
            if time.time() - cached['time'] < self._cache_ttl:
                return cached['result']

        # 获取场景配置
        config = self.SCENE_CONFIGS[self.current_scene]

        # 决定使用的方法
        method = force_method or self._decide_method(target, config)

        result = None

        if method == "template" and config.allow_template:
            result = self._try_template_match(frame, target)

        # 如果模板没匹配到，且允许 OCR
        if not result and config.allow_ocr:
            if method == "ocr" or (method == "template" and not result):
                result = self._try_ocr_match(frame, target)

        # 缓存结果
        if result:
            self._result_cache[cache_key] = {'result': result, 'time': time.time()}

        return result

    def _decide_method(self, target: str, config: MatcherConfig) -> str:
        """根据目标决定匹配方法"""
        # 如果配置了强制方法
        if config.preferred_method != "auto":
            return config.preferred_method

        # 根据目标类型决定
        if target in self.TARGET_RECOMMENDATIONS:
            recommended_scene = self.TARGET_RECOMMENDATIONS[target]
            if recommended_scene in [Scene.GAMING, Scene.COMPETITION]:
                return "template"

        # 检查是否是文字目标 (包含空格或中文)
        is_text_target = (' ' in target or
                         any('\u4e00' <= c <= '\u9fff' for c in target) or
                         target in ['Sign in', 'Sign out', 'Settings', 'Home'])

        if is_text_target:
            return "ocr" if self.current_scene not in [Scene.GAMING, Scene.COMPETITION] else "template"

        # 默认为模板
        return "template"

    def _try_template_match(self, frame, target) -> Optional[dict]:
        """尝试模板匹配"""
        start = time.time()
        result = self.template_matcher.match(frame, target)

        elapsed = (time.time() - start) * 1000
        logger.debug(f"模板匹配 '{target}': {elapsed:.1f}ms, found={result.found}")

        if result.found:
            return {
                'found': True,
                'method': 'template',
                'coords': (result.x, result.y),
                'norm_coords': (result.x, result.y),
                'elapsed_ms': elapsed
            }
        return None

    def _try_ocr_match(self, frame, target, roi: tuple = None) -> Optional[dict]:
        """尝试 OCR 匹配"""
        start = time.time()

        # 如果有预定义的 ROI，使用 ROI
        if roi is None:
            roi = self._get_roi_for_target(target)

        result = self.ocr_matcher.find_text(frame, target, roi=roi)

        elapsed = (time.time() - start) * 1000
        logger.debug(f"OCR 匹配 '{target}': {elapsed:.1f}ms, found={result is not None}")

        if result:
            return {
                'found': True,
                'method': 'ocr',
                'text': result['text'],
                'coords': result['center'],
                'norm_coords': result['norm_center'],
                'confidence': result['confidence'],
                'elapsed_ms': elapsed
            }
        return None

    def _get_roi_for_target(self, target: str) -> Optional[tuple]:
        """根据目标获取预定义 ROI 区域 (归一化坐标)"""
        roi_map = {
            # 按钮类 - 中心区域
            'Sign in': (0.3, 0.4, 0.7, 0.6),
            'Sign out': (0.3, 0.4, 0.7, 0.6),
            'OK': (0.3, 0.5, 0.7, 0.8),
            'Cancel': (0.3, 0.5, 0.7, 0.8),
            'Confirm': (0.3, 0.5, 0.7, 0.8),

            # 设置类 - 左侧
            'Settings': (0.0, 0.0, 0.4, 0.4),
            'Account': (0.0, 0.0, 0.4, 0.4),
            'Home': (0.0, 0.0, 0.2, 0.2),

            # 导航类 - 底部
            'Back': (0.0, 0.7, 0.3, 1.0),
            'Menu': (0.7, 0.7, 1.0, 1.0),
        }
        return roi_map.get(target)

    async def wait_for_match(self, frame_getter, target: str,
                           timeout: float = 30,
                           scene: Scene = None) -> Optional[dict]:
        """
        等待匹配成功

        Args:
            frame_getter: 获取帧的函数
            target: 目标
            timeout: 超时时间
            scene: 指定场景

        Returns:
            匹配结果
        """
        if scene:
            self.set_scene(scene)

        start = time.time()
        last_elapsed = 0

        while time.time() - start < timeout:
            frame = frame_getter()
            result = self.match(frame, target)

            if result:
                result['wait_time_ms'] = (time.time() - start) * 1000
                return result

            # 根据场景调整等待间隔
            if self.current_scene in [Scene.GAMING, Scene.COMPETITION]:
                await asyncio.sleep(0.05)  # 游戏模式 50ms
            else:
                await asyncio.sleep(0.2)  # 其他场景 200ms

        logger.warning(f"等待匹配超时: {target}, scene={self.current_scene.value}")
        return None
```

### 3.8 场景配置说明

| 场景 | 英文 | 匹配方式 | 说明 |
|------|------|---------|------|
| **COMPETITION** | 比赛 | 只用模板 | 延迟 < 20ms，禁止 OCR |
| **GAMING** | 游戏 | 只用模板 | 延迟 < 20ms，禁止 OCR |
| **LOGIN** | 登录 | 模板优先 + OCR fallback | 允许 OCR |
| **MENU** | 菜单 | 模板优先 + OCR fallback | 允许 OCR |
| **SETTINGS** | 设置 | OCR 优先 | 设置界面文字多 |
| **ACCOUNT** | 账号 | OCR 优先 | 账号界面文字多 |
| **STREAMING** | 串流 | 模板优先 + OCR fallback | 允许 OCR |
| **GENERAL** | 通用 | 模板优先 + OCR fallback | 默认配置 |

### 3.9 Xbox UI 常用文字识别目标

| Xbox UI 元素 | 英文文字 | 推荐场景 | 匹配方式 |
|-------------|---------|---------|---------|
| 主屏幕 | Home | GENERAL | 模板优先 |
| 设置 | Settings | SETTINGS | OCR 优先 |
| 我的游戏 | My games & apps | MENU | 模板优先 |
| 指南 | Guide | GENERAL | 模板优先 |
| 登录 | Sign in | LOGIN | 模板优先 |
| 登出 | Sign out | ACCOUNT | OCR 优先 |
| 账号 | Account | ACCOUNT | OCR 优先 |
| 确定 | OK | GENERAL | 模板优先 |
| 取消 | Cancel | GENERAL | 模板优先 |
| 返回 | Back | GENERAL | 模板优先 |
| 下一步 | 下一步 | LOGIN | 模板优先 |
| 取消 | 取消 | GENERAL | 模板优先 |
| 确定 | 确定 | GENERAL | 模板优先 |

### 3.10 性能对比

| 场景 | 匹配方式 | 单次延迟 | 适用场景 |
|------|---------|---------|---------|
| **COMPETITION/GAMING** | 模板匹配 | ~10ms | 比赛、游戏（要求低延迟） |
| **LOGIN/MENU** | 模板 + OCR fallback | ~10-50ms | 登录、菜单操作 |
| **SETTINGS/ACCOUNT** | OCR 优先 | ~50-100ms | 设置、账号管理 |
| **流媒体** | 模板优先 | ~10-50ms | 串流控制 |

### 3.11 匹配器使用示例

```python
# 初始化
matcher = SceneBasedMatcher(template_matcher, ocr_matcher)

# ===== 场景切换示例 =====

# 1. 游戏/比赛场景 - 只用模板匹配 (延迟最低)
matcher.set_scene(Scene.COMPETITION)
result = matcher.match(frame, 'a_button')  # 纯模板，~10ms
result = matcher.match(frame, 'Sign in')    # 也会用模板，~10ms

# 2. 登录场景 - 模板优先，OCR fallback
matcher.set_scene(Scene.LOGIN)
result = matcher.match(frame, 'login_button')  # 模板 ~10ms
result = matcher.match(frame, 'Sign in')        # 模板未找到，OCR ~100ms

# 3. 设置场景 - OCR 优先
matcher.set_scene(Scene.SETTINGS)
result = matcher.match(frame, 'Settings')   # OCR ~100ms
result = matcher.match(frame, 'Account')     # OCR ~100ms

# 4. 等待文字出现
matcher.set_scene(Scene.LOGIN)
result = await matcher.wait_for_match(
    lambda: frame_capture.capture_frame(),
    'Welcome',
    timeout=30,
    scene=Scene.LOGIN
)

# 5. 强制使用 OCR (覆盖场景配置)
result = matcher.match(frame, 'SomeText', force_method='ocr')

# 6. 组合匹配
result = matcher.match_any(frame, ['continue_btn', 'Continue', '下一步'])
```

---

## 四、窗口管理

### 4.1 Electron 窗口特性

```javascript
// 每个 StreamWindow 创建独立的 BrowserWindow
const window = new BrowserWindow({
  width: 1280,
  height: 720,
  title: `串流-${accountName}`,

  // 支持拖拽
  movable: true,

  // 支持最小化
  minimizable: true,

  // 不支持最大化（只能最小化）
  maximizable: false,

  // 支持隐藏/关闭
  closable: true,

  // 窗口可独立操作
  alwaysOnTop: false,  // 可设为 true 保持置顶
})

// 加载串流页面
window.loadURL(`http://localhost:9999/stream.html?instance=${instanceId}`)
```

### 4.2 窗口拖拽支持

```javascript
// HTML 窗口支持
<div class="stream-window" style="position: fixed; resize: both;">
  <div class="window-header" style="-webkit-app-region: drag;">
    <span>{accountName}</span>
    <div class="controls">
      <button onclick="minimize()">─</button>
      <button onclick="close()">×</button>
    </div>
  </div>
  <div id="video-container"></div>
</div>
```

### 4.3 归一化坐标点击原理

```
┌────────────────────────────────────────────────────────┐
│              BrowserWindow (1280x720)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │                                                  │  │
│  │        ┌────────────────────────┐               │  │
│  │        │                        │               │  │
│  │        │      视频画面          │ ← 可能有黑边  │  │
│  │        │                        │               │  │
│  │        │                        │               │  │
│  │        └────────────────────────┘               │  │
│  │                                                  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  模板匹配返回: norm_x=0.5, norm_y=0.8 (归一化坐标)      │
│                                                          │
│  点击计算:                                               │
│  click_x = norm_x * video_width * scale + offset_x      │
│  click_y = norm_y * video_height * scale + offset_y      │
└────────────────────────────────────────────────────────┘
```

---

## 五、与 B 端后端交互

### 5.1 Agent 启动流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Agent   │    │ Backend  │    │ Database │    │  Front  │
│ (Python) │    │  (Java)  │    │  (MySQL) │    │  (Vue)  │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │                │                │                │
     │  启动时注册     │                │                │
     │───────────────>│                │                │
     │                │  INSERT agent │                │
     │                │───────────────>│                │
     │                │                │                │
     │  心跳 (30s)    │                │                │
     │───────────────>│  UPDATE        │                │
     │                │───────────────>│                │
     │                │                │                │
     │  接收启动任务   │                │                │
     │<───────────────│                │                │
     │                │  INSERT task   │                │
     │                │───────────────>│                │
     │  执行自动化     │                │                │
     │  状态变更推送   │                │                │
     │───────────────>│  UPDATE task   │  推送状态       │
     │                │───────────────>│───────────────>│
     │                │                │                │
```

### 5.2 启动多账号自动化

```python
# Agent 接收后端任务
async def handle_start_automation_task(task_data: dict):
    """
    task_data = {
        "taskId": "123",
        "streamingAccount": {
            "id": 1,
            "name": "账号1",
            "email": "user@outlook.com",
            "password": "encrypted_xxx",
            "authCode": "xxx"
        },
        "gameAccounts": [
            {"id": 1, "name": "主账号", "xboxGamertag": "Player1"},
            {"id": 2, "name": "副账号", "xboxGamertag": "Player2"}
        ]
    }
    """

    # 启动独立窗口
    instance_id = await central_manager.start_streaming_account(
        account_config=task_data['streamingAccount'],
        game_accounts=task_data['gameAccounts']
    )

    # 更新任务状态
    await ApiClient.update_task_status(
        task_id=task_data['taskId'],
        status='running',
        instance_id=instance_id
    )
```

### 5.3 状态推送

```python
class StatusReporter:
    def __init__(self, backend_url: str, agent_id: str):
        self.backend_url = backend_url
        self.agent_id = agent_id
        self.websocket = None

    async def connect_websocket(self):
        """建立 WebSocket 连接"""
        self.websocket = await websockets.connect(
            f"ws://{self.backend_url}/ws/agent/{self.agent_id}"
        )

    async def report_instance_status(self, instance_id: str, state: dict):
        """上报实例状态"""
        await self.websocket.send(json.dumps({
            "type": "instance_status",
            "instanceId": instance_id,
            "state": state
        }))

    async def report_task_result(self, task_id: str, result: dict):
        """上报任务结果"""
        await self.websocket.send(json.dumps({
            "type": "task_result",
            "taskId": task_id,
            "result": result
        }))
```

---

## 六、数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│                         启动一个账号的自动化                           │
└─────────────────────────────────────────────────────────────────────┘

1. B端前端点击「启动」
         │
         ▼
2. POST /api/streaming/{id}/start
         │
         ▼
3. Java Backend 创建 Task 记录
         │
         ▼
4. 通过 WebSocket 通知对应 Agent
         │
         ▼
5. Agent 的 CentralManager 收到任务
         │
         ▼
6. 创建新的 StreamWindow 实例
         │
         ├── 创建独立 BrowserWindow
         ├── 加载 xStreamingPlayer
         ├── 启动串流
         └── 开始自动化循环
         │
         ▼
7. 实例状态通过 WebSocket 上报
         │
         ▼
8. B端前端显示「运行中」
         │
         ▼
9. 用户可拖拽/最小化该窗口
         │
         ▼
10. 自动化持续执行（模板匹配+输入）
         │
         ▼
11. 任务完成后状态更新
```

---

## 七、项目结构

```
xstreaming-multiagent/
│
├── backend/                          # Java Spring Boot 后端
│   ├── src/main/java/
│   │   └── com/xstreaming/manager/
│   │       ├── controller/
│   │       ├── service/
│   │       ├── entity/
│   │       ├── repository/
│   │       └── websocket/
│   └── pom.xml
│
├── frontend/                         # Vue 3 前端
│   └── src/
│       ├── views/
│       ├── components/
│       └── api/
│
├── agent/                            # Python Agent
│   ├── main.py                      # Agent 入口
│   ├── central_manager.py          # 中央管理器
│   ├── stream_window.py            # 串流窗口
│   ├── video_capture.py            # 视频帧捕获
│   ├── template_matcher.py         # 模板匹配
│   ├── input_controller.py          # 输入控制
│   └── api/
│       └── client.py               # 与后端通信
│
├── renderer/                        # Electron 渲染页面
│   ├── stream.html
│   ├── stream.js
│   └── styles.css
│
└── templates/                      # 模板图片
    ├── login/
    ├── stream/
    └── game/
```

---

## 八、关键特性总结

| 特性 | 实现 |
|------|------|
| **多账号并行** | CentralManager 管理多个 StreamWindow |
| **独立窗口** | 每个账号创建独立 BrowserWindow |
| **窗口拖拽** | Electron movable 属性 + CSS |
| **窗口最小化** | BrowserWindow.minimize() |
| **归一化坐标** | 模板匹配使用 0-1 坐标，不受窗口位置影响 |
| **实时状态** | WebSocket 推送 |
| **任务下发** | REST API + WebSocket 触发 |
| **资源隔离** | 每个窗口独立进程/端口 |

---

## 九、状态机

### 9.1 StreamWindow 状态

```
INITIALIZING → READY → CONNECTING → CONNECTED → AUTOMATING
                                           ↘
                                            ERROR → CLOSED
```

### 9.2 串流账号状态 (数据库)

```
idle → ready → running ⇄ paused → error → idle
                  ↓
               stopped
```

### 9.3 暂停/恢复功能

**两种暂停模式：**

| 模式 | 触发条件 | 行为 |
|------|---------|------|
| **比赛中暂停** | 用户点击暂停 / 管理平台触发 | 模拟手柄触发 Xbox 暂停菜单，暂停手柄循环，等待继续事件 |
| **非比赛暂停** | 管理平台设置暂停 / 账号切换间隙 | 直接暂停手柄循环，等待继续事件 |

**状态转换：**

```
running ──────────────────────► paused(比赛中)
   │                                   │
   │                          (收到继续事件)
   │                                   │
   │◄──────────────────────────────────┘
   │
   │◄───────────────────── paused(非比赛)
   │                          (收到继续事件)
   │
   ▼
running
```

**Python 实现：**

```python
class StreamWindow:
    """串流窗口管理"""

    def __init__(self):
        self.state = "idle"
        self.is_paused = False
        self.pause_type = None  # 'match' 或 'idle'
        self.pause_event = asyncio.Event()
        self.gamepad_loop_task = None

    async def pause(self, pause_type: str):
        """
        暂停自动化

        Args:
            pause_type: 'match' (比赛中暂停) 或 'idle' (非比赛暂停)
        """
        if self.is_paused:
            return

        logger.info(f"暂停自动化: {pause_type}")
        self.is_paused = True
        self.pause_type = pause_type

        if pause_type == 'match':
            # 比赛中暂停：模拟手柄按下 Xbox 按钮触发暂停菜单
            self.xplayer.pressButton('Xbox')
            await asyncio.sleep(0.5)
            self.xplayer.pressButton('A')  # 确认暂停
        else:
            # 非比赛暂停：直接暂停手柄循环
            pass

        # 设置暂停事件，阻塞手柄循环
        self.pause_event.set()

    async def resume(self):
        """
        恢复自动化

        条件：管理平台点击"继续"按钮后，自动化任务监听到继续事件
        """
        if not self.is_paused:
            return

        logger.info("恢复自动化")

        if self.pause_type == 'match':
            # 比赛中恢复：按下 A 继续游戏
            self.xplayer.pressButton('A')
        else:
            # 非比赛恢复：无特殊操作
            pass

        # 清除暂停事件，恢复手柄循环
        self.is_paused = False
        self.pause_type = None
        self.pause_event.clear()

    async def gamepad_loop(self):
        """
        手柄控制循环
        """
        while True:
            # 检查是否暂停
            if self.is_paused:
                logger.info("手柄循环暂停中，等待继续...")
                await self.pause_event.wait()
                logger.info("手柄循环恢复")

            # 执行手柄操作
            await self._execute_gamepad_commands()
            await asyncio.sleep(0.1)

    async def _execute_gamepad_commands(self):
        """执行手柄命令"""
        # 根据当前游戏状态执行对应操作
        pass
```

**管理平台触发接口：**

```java
// POST /api/streaming/{id}/pause
// Body: {"type": "match" | "idle"}

// POST /api/streaming/{id}/resume
```

**Agent 接收消息：**

```json
// WebSocket 消息
{
  "type": "task.pause",
  "data": {
    "streamingAccountId": 1,
    "pauseType": "match"
  }
}

{
  "type": "task.resume",
  "data": {
    "streamingAccountId": 1
  }
}
```

**注意事项：**
- 暂停期间 Xbox 连接保持不断开
- 暂停期间游戏账号的每日比赛次数不增加
- 恢复后从当前比赛继续，不重新开始

**暂停状态持久化：**

```python
class StreamWindow:
    """串流窗口管理"""

    def __init__(self):
        self.state = "idle"
        self.is_paused = False
        self.pause_type = None
        self.pause_event = asyncio.Event()
        self.gamepad_loop_task = None
        self.backend_client = None  # 后端 API 客户端

    async def pause(self, pause_type: str, persist: bool = True):
        """
        暂停自动化

        Args:
            pause_type: 'match' (比赛中暂停) 或 'idle' (非比赛暂停)
            persist: 是否持久化到数据库
        """
        if self.is_paused:
            return

        logger.info(f"暂停自动化: {pause_type}")
        self.is_paused = True
        self.pause_type = pause_type

        if pause_type == 'match':
            self.xplayer.pressButton('Xbox')
            await asyncio.sleep(0.5)
            self.xplayer.pressButton('A')
        else:
            pass

        self.pause_event.set()

        # 持久化到数据库
        if persist and self.backend_client:
            await self.backend_client.update_streaming_status(
                streaming_account_id=self.account_id,
                status='paused',
                pause_type=pause_type
            )

    async def resume(self, persist: bool = True):
        """恢复自动化"""
        if not self.is_paused:
            return

        logger.info("恢复自动化")

        if self.pause_type == 'match':
            self.xplayer.pressButton('A')
        else:
            pass

        self.is_paused = False
        self.pause_type = None
        self.pause_event.clear()

        # 持久化到数据库
        if persist and self.backend_client:
            await self.backend_client.update_streaming_status(
                streaming_account_id=self.account_id,
                status='running'
            )

    async def handle_agent_restart(self):
        """
        处理 Agent 重启

        重启后检查数据库中的状态，如果之前是暂停状态，
        改为空闲状态，让用户重新启动
        """
        if self.is_paused:
            logger.warning("Agent 重启，暂停状态将被重置为空闲")
            self.is_paused = False
            self.pause_type = None
            self.pause_event.clear()

            # 更新数据库状态为空闲
            if self.backend_client:
                await self.backend_client.update_streaming_status(
                    streaming_account_id=self.account_id,
                    status='idle'
                )
```

---

## 十、多实例与游戏账号切换

### 10.1 xStreamingPlayer 多实例支持

**结论：支持多实例**

每个 Electron 窗口对应一个独立的串流连接实例。架构如下：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Electron Main Process                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │ StreamWin 1 │   │ StreamWin 2 │   │ StreamWin N │           │
│  │ (BrowserWin)│   │ (BrowserWin)│   │ (BrowserWin)│           │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘           │
│         │                  │                  │                  │
│         │  WebRTC          │  WebRTC          │  WebRTC         │
│         │  Connection      │  Connection      │  Connection     │
│         ▼                  ▼                  ▼                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Xbox Console 1 (或 多台 Xbox)                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**实现要点：**

1. **独立渲染进程**：每个 BrowserWindow 有独立的渲染进程
2. **独立 WebRTC 连接**：每个窗口与 Xbox 建立独立的 WebRTC 会话
3. **独立视频捕获**：每个窗口的 VideoFrameCapture 只捕获自己的视频流
4. **独立自动化状态**：每个窗口的 LoginService/StreamService 独立运行

```javascript
// 在 background.js 中管理多个窗口
class WindowManager {
  constructor() {
    this.windows = new Map();  // instanceId -> BrowserWindow
  }

  createStreamWindow(instanceId, accountName) {
    const window = new BrowserWindow({
      width: 1280,
      height: 720,
      title: `串流-${accountName}`,
      movable: true,
      minimizable: true,
      maximizable: false,
      closable: true,
    });

    // 加载串流页面，传递 instanceId
    window.loadURL(`http://localhost:9999/stream.html?instance=${instanceId}`);

    this.windows.set(instanceId, window);
    return window;
  }

  closeStreamWindow(instanceId) {
    const window = this.windows.get(instanceId);
    if (window) {
      window.close();
      this.windows.delete(instanceId);
    }
  }

  getWindow(instanceId) {
    return this.windows.get(instanceId);
  }
}
```

### 10.2 游戏账号循环切换与比赛次数限制

**需求**：串流账号登录后，根据配置的游戏账号进行循环切换，当某个游戏账号完成当日/总比赛次数后自动跳过。

**核心逻辑：**

```
┌─────────────────────────────────────────────────────────────────┐
│                     串流账号自动化主循环                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 登录微软账号 → 串流连接 Xbox                                   │
│         ↓                                                         │
│  2. 获取游戏账号列表（按优先级排序）                                │
│         ↓                                                         │
│  ┌─────────────────────────────────────┐                          │
│  │        游戏账号轮询循环              │                          │
│  │                                     │                          │
│  │  ┌─────────────────────────────┐   │                          │
│  │  │ 游戏账号 A (今日 0/3)       │   │                          │
│  │  │ ✅ 可用 → 开始比赛           │   │                          │
│  │  └─────────────────────────────┘   │                          │
│  │         ↓                           │                          │
│  │  ┌─────────────────────────────┐   │                          │
│  │  │ 游戏账号 B (今日 3/3)       │   │                          │
│  │  │ ❌ 今日已达上限 → 跳过       │   │                          │
│  │  └─────────────────────────────┘   │                          │
│  │         ↓                           │                          │
│  │  ┌─────────────────────────────┐   │                          │
│  │  │ 游戏账号 C (今日 2/3)       │   │                          │
│  │  │ ✅ 可用 → 开始比赛           │   │                          │
│  │  └─────────────────────────────┘   │                          │
│  │         ↓                           │                          │
│  │  ┌─────────────────────────────┐   │                          │
│  │  │ 所有账号都已用完？           │   │                          │
│  │  └────────────┬────────────────┘   │                          │
│  │       Yes     │     No              │                          │
│  │       ┌───────┴───────┐             │                          │
│  │       ↓               ↓             │                          │
│  │  ┌─────────┐    返回轮询             │                          │
│  │  │ 自动化   │←──────────────────────┘                          │
│  │  │ 正常停止 │                                                │
│  │  └─────────┘                                                │
│  │                                                             │
│  └─────────────────────────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Python 实现：**

```python
class GameAccountRotationService:
    """游戏账号轮询服务"""

    def __init__(self, stream_service, backend_client):
        self.stream_service = stream_service
        self.backend_client = backend_client
        self.current_account = None
        self.match_records = {}  # game_account_id -> MatchSession

    async def run_rotation(self, streaming_account_id: int):
        """
        执行游戏账号轮询

        Args:
            streaming_account_id: 串流账号 ID
        """
        logger.info(f"开始游戏账号轮询: 串流账号 {streaming_account_id}")

        # 获取游戏账号列表
        accounts = await self.backend_client.get_game_accounts(
            streaming_account_id
        )

        # 过滤可用账号（未达上限）
        available_accounts = self._filter_available(accounts)

        if not available_accounts:
            logger.warning("没有可用的游戏账号，全部已达上限")
            await self._stop_automation(streaming_account_id)
            return

        while True:
            # 选择下一个可用账号
            next_account = self._select_next(available_accounts)

            if next_account is None:
                # 所有账号都用完了
                logger.info("所有游戏账号已完成当日/总比赛次数限制")
                await self._stop_automation(streaming_account_id)
                break

            # 执行比赛
            await self._play_match(streaming_account_id, next_account)

            # 更新计数
            await self._update_match_count(next_account)

            # 检查是否需要停止
            if await self._should_stop(streaming_account_id, available_accounts):
                break

            # 短暂休息后继续
            await asyncio.sleep(5)

    def _filter_available(self, accounts: List[dict]) -> List[dict]:
        """过滤可用账号"""
        available = []
        for acc in accounts:
            if not acc.get('is_active'):
                continue

            daily_limit = acc.get('daily_match_limit', 3)
            today_count = acc.get('today_match_count', 0)

            # 检查每日限制
            if today_count >= daily_limit:
                logger.info(f"账号 {acc['name']} 今日已达上限 ({today_count}/{daily_limit})")
                continue

            available.append(acc)

        return available

    def _select_next(self, accounts: List[dict]) -> Optional[dict]:
        """
        选择下一个账号

        排序规则：
        1. 有设置优先级的账号，按优先级数字升序（数字越小越优先）
        2. 未设置优先级的账号（priority=0），按传入顺序（即列表下标）
        """
        if not accounts:
            return None

        # 按优先级排序：有设置的排前面，同优先级的保持原顺序
        sorted_accounts = sorted(
            accounts,
            key=lambda a: (
                a.get('priority', 0) == 0,  # 有设置的排前面
                a.get('priority', 0),
                accounts.index(a)  # 同优先级按原顺序
            )
        )

        # 选择第一个
        return sorted_accounts[0]

    async def _play_match(self, streaming_id: int, game_account: dict):
        """执行一场比赛"""
        logger.info(f"开始比赛: 游戏账号 {game_account['name']}")

        # 创建比赛记录
        match_record = await self.backend_client.create_match_record({
            'streaming_account_id': streaming_id,
            'game_account_id': game_account['id'],
            'status': 'playing'
        })

        # 切换到游戏账号
        await self.stream_service.switch_to_account(game_account)

        # 等待比赛开始检测
        await self._wait_for_match_start()

        # 更新状态为比赛中
        await self.backend_client.update_match_record(
            match_record['id'],
            {'status': 'playing'}
        )

        # 监控比赛状态（循环检测是否结束）
        result = await self._monitor_match()

        # 比赛结束，记录结果
        await self.backend_client.update_match_record(
            match_record['id'],
            {
                'status': 'completed',
                'result': result,  # win/lose/draw
                'finished_at': datetime.now().isoformat()
            }
        )

        logger.info(f"比赛完成: {game_account['name']}, 结果: {result}")

    async def _monitor_match(self) -> str:
        """监控比赛直到结束"""
        while True:
            frame = self.stream_service.capture_frame()

            # 检测比赛结束标志
            if self._detect_match_end(frame):
                return self._determine_match_result(frame)

            # 检测异常中断
            if self._detect_match_interrupted(frame):
                return 'interrupted'

            await asyncio.sleep(5)

    async def _update_match_count(self, game_account: dict):
        """更新游戏账号的比赛计数"""
        await self.backend_client.increment_match_count(game_account['id'])

    async def _should_stop(self, streaming_id: int, accounts: List[dict]) -> bool:
        """检查是否应该停止自动化"""
        # 获取最新账号状态
        latest_accounts = await self.backend_client.get_game_accounts(streaming_id)
        available = self._filter_available(latest_accounts)

        if not available:
            logger.info("所有游戏账号已达上限，停止自动化")
            return True

        return False

    async def _stop_automation(self, streaming_account_id: int):
        """停止自动化"""
        await self.backend_client.stop_streaming(streaming_account_id)
        logger.info(f"自动化已停止: 串流账号 {streaming_account_id}")

### 10.3 Xbox 游戏账号登出/登录详细步骤

**登出当前账号流程：**

```
┌──────────────────┐
│ 确保在 Xbox 主界面 │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 按 Xbox 按钮     │ → 打开 Guide
│ (打开 Guide)     │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 按 A 确认         │ → 进入 Profile & system
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 选择 Settings     │ → 模板匹配: settings_icon
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 选择 Account     │ → 模板匹配: account_icon
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 选择 Remove account│ → 模板匹配: remove_account_icon
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 选择要登出的账号   │ → 模板匹配: gamertag_avatar
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 按 A 确认登出     │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 等待登出完成      │ → 检测登出成功标志
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 登出完成         │
└──────────────────┘
```

**登录新账号流程：**

```
┌──────────────────┐
│ 登出完成后自动    │ → 等待账号选择界面
│ 进入账号选择界面   │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 选择 Add new      │ → 模板匹配: add_new_account_icon
│ (添加新账号)      │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 输入邮箱          │ → 通过 Electron Bridge 输入
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 按 Enter 继续     │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 输入密码          │ → 通过 Electron Bridge 输入
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 勾选记住我        │ → 模板匹配: remember_me_checkbox
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 按 Enter 登录     │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 等待登录成功      │ → 检测登录成功标志
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 登录成功         │
└──────────────────┘
```

**Xbox UI 模板图片要求（templates 文件夹）：**

| 模板名 | 说明 | 要求 |
|--------|------|------|
| `guide_icon` | Guide 按钮图标 | 48x48 PNG |
| `settings_icon` | 设置图标 | 48x48 PNG |
| `account_icon` | 账号图标 | 48x48 PNG |
| `remove_account_icon` | 移除账号图标 | 48x48 PNG |
| `add_new_account_icon` | 添加新账号图标 | 48x48 PNG |
| `remember_me_checkbox` | 记住我复选框 | 48x48 PNG |
| `sign_in_button` | 登录按钮 | 48x48 PNG |
| `match_start` | 比赛开始标志 | 128x128 PNG |
| `match_end` | 比赛结束标志 | 128x128 PNG |
| `match_win` | 胜利标志 | 128x128 PNG |
| `match_lose` | 失败标志 | 128x128 PNG |

**Python 实现（Xbox 账号切换服务）：**

```python
class XboxAccountSwitchService:
    """Xbox 游戏账号切换服务"""

    # 模板路径
    TEMPLATE_DIR = "./templates/xbox/"

    def __init__(self, stream_service, matcher: SceneBasedMatcher):
        self.stream_service = stream_service
        self.matcher = matcher

    async def switch_to_account(self, target_account: dict):
        """
        切换到目标游戏账号

        Args:
            target_account: {
                'xbox_live_email': 'xxx@live.com',
                'xbox_live_password': 'password' (明文，由后端解密后传递)
            }
        """
        logger.info(f"开始切换账号: {target_account['xbox_live_email']}")

        # 1. 登出当前账号
        await self._sign_out_current()

        # 2. 进入添加账号界面
        await self._navigate_to_add_account()

        # 3. 输入邮箱
        await self._input_email(target_account['xbox_live_email'])

        # 4. 输入密码
        await self._input_password(target_account['xbox_live_password'])

        # 5. 确认登录
        await self._confirm_login()

        # 6. 验证登录成功
        if not await self._verify_login():
            raise AutomationError("账号切换验证失败")

        logger.info(f"账号切换成功: {target_account['xbox_live_email']}")

    async def _sign_out_current(self):
        """登出当前账号"""
        # 确保在主界面
        await self._ensure_home_screen()

        # 按 Xbox 按钮打开 Guide
        self.stream_service.xplayer.pressButton('Xbox')
        await asyncio.sleep(1)

        # 进入 Settings
        await self._navigate_to_settings()

        # 进入 Account
        await self._navigate_to_account()

        # 选择 Remove account
        await self._select_remove_account()

        # 选择要登出的账号（第一个）
        await self._select_first_account()

        # 确认登出
        self.stream_service.xplayer.pressButton('A')
        await asyncio.sleep(2)

        logger.info("已登出当前账号")

    async def _ensure_home_screen(self):
        """确保在 Xbox 主界面"""
        for _ in range(10):
            frame = self.stream_service.capture_frame()
            result = self.matcher.match(frame, 'home_icon')
            if result:
                return
            self.stream_service.xplayer.pressButton('B')
            await asyncio.sleep(0.5)

    async def _navigate_to_settings(self):
        """导航到设置"""
        await self._wait_and_click('settings_icon')

    async def _navigate_to_account(self):
        """导航到账号管理"""
        await self._wait_and_click('account_icon')

    async def _select_remove_account(self):
        """选择移除账号"""
        await self._wait_and_click('remove_account_icon')

    async def _select_first_account(self):
        """选择第一个账号（通常是当前登录的）"""
        await asyncio.sleep(0.5)
        self.stream_service.xplayer.pressButton('A')
        await asyncio.sleep(0.5)

    async def _navigate_to_add_account(self):
        """导航到添加账号界面"""
        # 登出后会回到账号选择界面
        await self._wait_and_click('add_new_account_icon', timeout=10)

    async def _input_email(self, email: str):
        """输入邮箱"""
        # 使用剪贴板输入
        await self._input_text(email)
        self.stream_service.xplayer.pressButton('A')  # 确认
        await asyncio.sleep(1)

    async def _input_password(self, password: str):
        """输入密码"""
        await self._input_text(password)
        # 勾选记住我
        await self._try_click('remember_me_checkbox')
        # 确认
        self.stream_service.xplayer.pressButton('A')
        await asyncio.sleep(2)

    async def _confirm_login(self):
        """确认登录"""
        # 可能需要多次按 A 确认
        for _ in range(3):
            self.stream_service.xplayer.pressButton('A')
            await asyncio.sleep(1)

    async def _verify_login(self) -> bool:
        """验证登录成功"""
        # 检测用户头像或玩家名出现
        for _ in range(30):
            frame = self.stream_service.capture_frame()
            result = self.matcher.match(frame, 'user_avatar')
            if result:
                return True
            await asyncio.sleep(1)
        return False

    async def _wait_and_click(self, template: str, timeout: float = 30):
        """等待模板出现并点击"""
        result = await self.matcher.wait_for_match(
            lambda: self.stream_service.capture_frame(),
            template,
            timeout=timeout
        )
        if result:
            await self._click_at(result['norm_coords'])
        else:
            raise AutomationError(f"等待模板超时: {template}")

    async def _try_click(self, template: str):
        """尝试点击模板（不等待）"""
        frame = self.stream_service.capture_frame()
        result = self.matcher.match(frame, template)
        if result:
            await self._click_at(result['norm_coords'])

    async def _click_at(self, norm_coords):
        """在归一化坐标处点击"""
        x, y = norm_coords
        self.stream_service.click_at_normalized(x, y)

    async def _input_text(self, text: str):
        """通过剪贴板输入文本"""
        # 设置剪贴板
        self.stream_service.set_clipboard(text)
        # 模拟 Ctrl+V 粘贴
        self.stream_service.xplayer.pressShortcut('ctrl', 'v')
        await asyncio.sleep(0.5)
```

**注意事项：**
- 所有坐标使用归一化坐标 (0-1)，不受窗口位置影响
- 每次操作后适当等待，让 Xbox UI 响应
- 错误处理：超时后重试最多 3 次

---

**B-End 后端比赛次数校验 API：**

```java
// GET /api/streaming/{id}/game-accounts/available
// 返回当前可用的游戏账号列表

@Service
public class GameAccountService {

    public List<GameAccount> getAvailableAccounts(Long streamingAccountId) {
        List<GameAccount> accounts = gameAccountRepo.findByStreamingAccountId(streamingAccountId);
        List<GameAccount> available = new ArrayList<>();

        LocalDate today = LocalDate.now();

        for (GameAccount acc : accounts) {
            if (!acc.getIsActive()) continue;

            // 检查每日限制
            long todayCount = matchRecordRepo.countByGameAccountIdAndDate(
                acc.getId(), today, "completed");
            if (todayCount >= acc.getDailyMatchLimit()) {
                continue;
            }

            available.add(acc);
        }

        return available;
    }

    @Transactional
    public void incrementMatchCount(Long gameAccountId) {
        GameAccount acc = gameAccountRepo.findById(gameAccountId);
        acc.setTodayMatchCount(acc.getTodayMatchCount() + 1);
        acc.setTotalMatchCount(acc.getTotalMatchCount() + 1);
        acc.setLastUsedAt(new Date());
        gameAccountRepo.save(acc);
    }
}
```

**每日重置逻辑（定时任务，支持时区）：**

```java
// 每小时执行一次，检查各商户时区的"今天"是否需要重置
@Scheduled(cron = "0 0 * * * ?")
public void resetDailyMatchCount() {
    List<Merchant> merchants = merchantRepo.findAll();
    ZoneId serverZone = ZoneId.systemDefault();

    for (Merchant merchant : merchants) {
        // 获取商户当地的"今天"
        ZoneId merchantZone = ZoneId.of(merchant.getTimezone());
        LocalDate merchantToday = LocalDate.now(merchantZone);

        // 获取上次重置的日期
        LocalDate lastResetDate = getLastResetDate(merchant.getId());

        // 如果商户的"今天"大于上次重置日期，需要重置
        if (merchantToday.isAfter(lastResetDate)) {
            List<GameAccount> accounts = gameAccountRepo.findByMerchantId(merchant.getId());
            for (GameAccount acc : accounts) {
                acc.setTodayMatchCount(0);
            }
            gameAccountRepo.saveAll(accounts);

            // 更新最后重置日期
            setLastResetDate(merchant.getId(), merchantToday);

            logger.info("商户 {} (时区 {}) 已重置今日比赛计数", merchant.getName(), merchant.getTimezone());
        }
    }
}

// 每个商户独立的重置日期存储（使用 Redis）
private void setLastResetDate(Long merchantId, LocalDate date) {
    redis.setex("merchant:reset_date:" + merchantId, 86400, date.toString());
}

private LocalDate getLastResetDate(Long merchantId) {
    String dateStr = redis.get("merchant:reset_date:" + merchantId);
    return dateStr != null ? LocalDate.parse(dateStr) : LocalDate.now().minusDays(1);
}
```

**比赛次数限制规则汇总：**

| 限制类型 | 字段 | 说明 |
|---------|------|------|
| **每日限制** | `daily_match_limit` | 每天最多比赛场次，默认 3 |
| **今日计数** | `today_match_count` | 今日已完成场次 |
| **总计数** | `total_match_count` | 历史总场次（仅记录） |
| **启用状态** | `is_active` | 禁用后不参与轮询 |

**停止自动化条件：**

1. 所有游戏账号今日比赛次数已达上限
2. 用户手动停止
3. 异常中断（Xbox 断开等）

---

## 十一、待讨论问题

~~1. **xStreamingPlayer 多实例** - 是否支持同一个页面创建多个实例？~~ ✅ 已解决：支持，每个窗口独立实例

~~2. **Agent 横向扩展**~~ ✅ 已解决（见下方说明）

~~3. **异常恢复**~~ ✅ 已解决：自动重启实例

~~4. **账号凭据安全**~~ ✅ 已解决：AES 加密存储，自动化调用时解密

---

## 十二、Agent 横向扩展设计

### 12.1 扩展模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **单机多开** | 一台电脑运行多个 Electron 窗口 | 小规模部署（1-8个窗口） |
| **多机分布式** | 多台电脑，每台运行 Agent 进程 | 大规模部署（8+ 窗口） |

### 12.2 分布式架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      云服务器 (B-End 平台)                        │
│                        (Vue + Java + MySQL)                      │
│                                                                  │
│   • 账号管理、任务下发、状态监控                                   │
│   • Agent 注册、心跳、任务分配                                     │
│   • WebSocket 实时推送                                            │
│                                                                  │
│   📍 部署位置：云服务器（阿里云/腾讯云等）                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP / WebSocket (公网)
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │  Agent 1  │        │  Agent 2  │        │  Agent N  │
   │           │        │           │        │           │
   │ 📍 地点 A │        │ 📍 地点 B │        │ 📍 地点 N │
   │ 家庭宽带  │        │ 办公室    │        │ 机房      │
   │           │        │           │        │           │
   │ • 注册    │        │ • 注册    │        │ • 注册    │
   │ • 心跳    │        │ • 心跳    │        │ • 心跳    │
   │ • 接收任务│        │ • 接收任务│        │ • 接收任务│
   │ • 上报状态│        │ • 上报状态│        │ • 上报状态│
   │           │        │           │        │           │
   │ 窗口 1~4  │        │ 窗口 5~8  │        │ 窗口 N~M  │
   └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
         │                    │                    │
    ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
    │Xbox群组1│          │Xbox群组2│          │Xbox群组N│
    │ (同一网络)│        │ (同一网络)│        │ (同一网络)│
    └─────────┘          └─────────┘          └─────────┘
```

### 12.2.1 网络架构详解

| 组件 | 部署位置 | 网络要求 | 说明 |
|------|---------|---------|------|
| **B-End 平台** | 云服务器 | 公网可访问 | 服务器需要有公网 IP 或域名 |
| **Agent** | 各地点电脑 | 能访问公网 + 本地网络 | 需要同时连接服务器和 Xbox |
| **Xbox** | 与 Agent 同网络 | 内网可达 | Xbox 和运行 Agent 的电脑需在同一局域网 |

**通信机制：**

```
┌─────────────────────────────────────────────────────────────────┐
│                     B-End 服务器 (公网)                          │
│                         :443 HTTPS                               │
│                         :8080 HTTP                              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
         ┌─────────┐     ┌─────────┐     ┌─────────┐
         │ Agent 1 │     │ Agent 2 │     │ Agent N │
         │ (地点A) │     │ (地点B) │     │ (地点N) │
         └────┬────┘     └────┬────┘     └────┬────┘
              │               │               │
              │   ┌───────────┘               │
              │   │  Xbox 必须在              │
              │   │  Agent 同一局域网         │
              │   │                            │
              ▼   ▼                            ▼
         ┌─────────┐     ┌─────────┐     ┌─────────┐
         │ Xbox 1  │     │ Xbox 5  │     │ Xbox 9  │
         │ (内网)  │     │ (内网)  │     │ (内网)  │
         └─────────┘     └─────────┘     └─────────┘
```

### 12.2.2 Agent 穿透方案

由于 Agent 部署在不同地点的私网中，无法被服务器直接连接，采用 **长连接反弹** 方案：

```python
class AgentClient:
    """Agent 客户端 - 反弹连接模式"""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self.agent_id = self._generate_agent_id()
        self.ws = None
        self.reconnect_delay = 5  # 重连延迟秒

    def start(self):
        """启动 Agent，保持 WebSocket 长连接"""
        while True:
            try:
                # 主动连接到服务器（服务器防火墙允许入站）
                self.ws = websocket.create_connection(
                    f"wss://{self.backend_url}/ws/agent",
                    sslopt={"cert_reqs": ssl.CERT_NONE}
                )

                # 注册
                self.ws.send(json.dumps({
                    "type": "register",
                    "agent_id": self.agent_id,
                    "capacity": self.capacity
                }))

                # 心跳保活
                self._heartbeat_loop()

            except Exception as e:
                logger.error(f"连接断开: {e}, {self.reconnect_delay}秒后重连")
                time.sleep(self.reconnect_delay)

    def _heartbeat_loop(self):
        """心跳循环"""
        while True:
            try:
                self.ws.send(json.dumps({
                    "type": "heartbeat",
                    "agent_id": self.agent_id,
                    "status": "online",
                    "window_count": len(self.windows)
                }))
                time.sleep(30)  # 30秒心跳
            except:
                break
```

### 12.2.3 任务下发流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        B-End 服务器                              │
│                                                                  │
│  1. 管理员在 Web 界面创建任务                                     │
│  2. 系统选择合适的 Agent (负载均衡)                               │
│  3. 通过 WebSocket 下发任务到 Agent                               │
│                                                                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              │ WebSocket 推送 (服务器 → Agent)
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │  Agent 1  │        │  Agent 2  │        │  Agent N  │
   │ 收到任务: │        │ 收到任务: │        │ 收到任务: │
   │ {        │        │ {         │        │ {         │
   │   action: │        │   action: │        │   action: │ ← 不执行
   │   stream  │        │   stream  │        │   stream  │   (负载已满)
   │  }        │        │  }        │        │  }        │
   └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │ 执行自动化│        │ 执行自动化│        │ 返回忙碌  │
   │ 连接Xbox │        │ 连接Xbox │        │ 等待重试  │
   │ 开始串流  │        │ 开始串流  │        │           │
   └─────┬─────┘        └─────┬─────┘        └───────────┘
         │                    │
         └──────────┬──────────┘
                    │
                    │ WebSocket 上报 (Agent → 服务器)
                    ▼
         ┌─────────────────────┐
         │  B-End 更新状态    │
         │  • streaming: running│
         │  • 实时日志推送     │
         │  • Web 界面展示     │
         └─────────────────────┘
```

### 12.3 Agent 注册与心跳

```python
class AgentClient:
    """Agent 客户端"""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self.agent_id = self._generate_agent_id()
        self.capacity = self._detect_capacity()  # 可运行窗口数
        self.windows = {}  # instance_id -> StreamWindow

    def register(self):
        """注册到后端"""
        response = requests.post(f"{self.backend_url}/api/agent/register", {
            "agent_id": self.agent_id,
            "host": socket.gethostname(),
            "port": self.api_port,
            "capacity": self.capacity,
            "status": "online"
        })
        return response.json()

    def heartbeat(self):
        """心跳保活"""
        response = requests.post(f"{self.backend_url}/api/agent/heartbeat", {
            "agent_id": self.agent_id,
            "status": "online",
            "window_count": len(self.windows),
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent
        })

    def receive_task(self, task: dict):
        """接收任务"""
        # 任务包含：streaming_account_id, game_account_id, action 等
        pass

    def report_status(self, instance_id: str, status: dict):
        """上报实例状态"""
        requests.post(f"{self.backend_url}/api/agent/status", {
            "agent_id": self.agent_id,
            "instance_id": instance_id,
            "status": status
        })
```

### 12.4 任务分配策略

```python
def assign_task(backend_url: str, task: dict) -> Optional[str]:
    """
    任务分配：从在线 Agent 中选择最合适的

    策略：
    1. 筛选状态为 online 的 Agent
    2. 排除当前忙碌的 Agent
    3. 选择窗口数最少的 Agent（负载均衡）
    """
    response = requests.get(f"{backend_url}/api/agent/available")
    agents = response.json()

    if not agents:
        return None  # 没有可用 Agent

    # 负载均衡：选择负载最低的
    best_agent = min(agents, key=lambda a: a["window_count"])

    # 下发任务
    requests.post(f"{backend_url}/api/agent/{best_agent['agent_id']}/task", {
        "task": task
    })

    return best_agent["agent_id"]
```

### 12.5 单机 vs 多机对比

| 维度 | 单机多开 | 多机分布式 |
|------|---------|------------|
| **硬件要求** | 高（CPU/内存） | 较低（可分散） |
| **网络要求** | 低（内网） | 需要外网访问 Xbox |
| **延迟** | 低 | 可能较高 |
| **扩展性** | 受限于单机硬件 | 线性扩展 |
| **复杂度** | 低 | 高（需网络通信） |

**推荐：**
- **初期**：单机多开（1-4个窗口）
- **中期**：2-3台电脑分布式
- **大规模**：按 Xbox 群组分配到不同电脑

---

## 十三、异常恢复机制

### 13.1 异常类型与恢复策略

| 异常类型 | 检测方法 | 恢复策略 |
|---------|---------|---------|
| **窗口崩溃** | 进程退出、窗口句柄丢失 | 自动重启窗口实例 |
| **Xbox 断开** | WebRTC 连接断开、心跳超时 | 重连串流会话 |
| **账号掉线** | 模板匹配检测登出界面 | 重新登录 |
| **游戏崩溃** | 检测游戏退出、回到主界面 | 重启游戏或返回主界面 |
| **网络波动** | 心跳超时 | 等待恢复后重连 |

### 13.2 自动重启实例实现

```python
class StreamWindow:
    """串流窗口管理"""

    def __init__(self, instance_id: str, account_id: str):
        self.instance_id = instance_id
        self.account_id = account_id
        self.state = "idle"
        self.restart_count = 0
        self.max_restart = 3

    def monitor_and_recover(self):
        """监控并恢复异常"""
        while True:
            try:
                # 检查窗口状态
                if not self._is_window_alive():
                    self._handle_window_crash()

                # 检查串流状态
                if not self._is_streaming_alive():
                    self._handle_stream_disconnect()

                # 检查登录状态
                if not self._is_logged_in():
                    self._handle_logout()

                # 每秒检测一次
                time.sleep(1)

            except Exception as e:
                logger.error(f"监控异常: {e}")
                time.sleep(5)

    def _is_window_alive(self) -> bool:
        """检测窗口是否存活"""
        try:
            # 检查进程
            if self.process and not self.process.is_alive():
                return False
            # 检查窗口句柄
            return self._window and not self._window.isDestroyed()
        except:
            return False

    def _handle_window_crash(self):
        """处理窗口崩溃"""
        self.restart_count += 1

        if self.restart_count > self.max_restart:
            logger.error(f"实例 {self.instance_id} 重启次数超限，标记为失败")
            self.state = "failed"
            self._report_to_backend()
            return

        logger.warning(f"实例 {self.instance_id} 崩溃，第 {self.restart_count} 次重启")
        self._close_window()
        time.sleep(3)
        self._create_window()
        self._reconnect_stream()
        self._restore_login_state()

    def _close_window(self):
        """关闭窗口"""
        try:
            if self._window and not self._window.isDestroyed():
                self._window.close()
        except:
            pass

    def _create_window(self):
        """创建新窗口"""
        # 重新创建 BrowserWindow
        pass

    def _reconnect_stream(self):
        """重连串流"""
        self.stream_service.reconnect()

    def _restore_login_state(self):
        """恢复登录状态"""
        # 读取本地保存的登录态
        pass
```

### 13.3 崩溃恢复流程

```
┌─────────────────┐
│  窗口/实例崩溃   │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 记录崩溃日志    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ restart_count++ │
└────────┬────────┘
         ▼
    ┌────┴────┐
    │超过最大?│
    └────┬────┘
     Yes │ No
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌─────────────────┐
│ 标记   │ │ 关闭原窗口      │
│ 失败   │ └────────┬────────┘
└───┬────┘          ▼
    │    ┌─────────────────┐
    │    │ 重新创建窗口    │
    │    └────────┬────────┘
    │             ▼
    │    ┌─────────────────┐
    │    │ 重连串流会话    │
    │    └────────┬────────┘
    │             ▼
    │    ┌─────────────────┐
    │    │ 恢复登录状态    │
    │    └────────┬────────┘
    │             ▼
    │    ┌─────────────────┐
    └───►│ 继续监控        │
         └─────────────────┘
```

### 13.4 心跳超时检测

```python
class CentralManager:
    """中心管理器"""

    def __init__(self):
        self.last_heartbeat = {}

    def check_heartbeat(self, instance_id: str, timeout: int = 60):
        """检查实例心跳超时"""
        last = self.last_heartbeat.get(instance_id)

        if last is None:
            return True  # 从未收到心跳

        if time.time() - last > timeout:
            logger.warning(f"实例 {instance_id} 心跳超时")
            self._trigger_recovery(instance_id)
            return False

        return True

    def _trigger_recovery(self, instance_id: str):
        """触发恢复流程"""
        window = self.windows.get(instance_id)
        if window:
            window._handle_window_crash()
```

---

## 十四、账号凭据安全存储

### 14.1 加密方案

| 项目 | 说明 |
|------|------|
| **加密算法** | AES-256-GCM |
| **密钥管理** | 主密钥存储在配置文件（环境变量） |
| **密钥轮换** | 定期更换主密钥（可选） |

### 14.2 加密实现

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os

class CredentialManager:
    """凭据加密管理"""

    def __init__(self, master_key: bytes = None):
        # 从环境变量或配置文件获取主密钥
        self.master_key = master_key or os.environ.get('CREDENTIAL_MASTER_KEY')
        if not self.master_key:
            raise ValueError("缺少主密钥")
        self.aesgcm = AESGCM(self.master_key)

    def encrypt(self, plaintext: str) -> str:
        """加密凭据"""
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        # 返回 base64(nonce + ciphertext)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted: str) -> str:
        """解密凭据"""
        data = base64.b64decode(encrypted)
        nonce = data[:12]
        ciphertext = data[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None).decode()

    def decrypt_for_automation(self, encrypted_password: str) -> str:
        """自动化时解密密码"""
        return self.decrypt(encrypted_password)
```

### 14.3 密码加密存储流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        B-End 管理平台                            │
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐                    │
│  │ 管理员输入密码   │───►│  AES 加密        │                    │
│  │ 123456          │    │  → 加密字符串    │                    │
│  └──────────────────┘    └────────┬─────────┘                    │
│                                   │                               │
│                                   ▼                               │
│                          ┌──────────────────┐                    │
│                          │  存储到数据库    │                    │
│                          │  (MySQL)        │                    │
│                          └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │              Agent 自动化时                  │
                    │                                             │
                    │  ┌──────────────────┐    ┌──────────────┐  │
                    │  │ 从数据库读取     │───►│  AES 解密   │  │
                    │  │ 加密密码         │    │  → 明文密码  │  │
                    │  └──────────────────┘    └──────┬───────┘  │
                    │                                 │          │
                    │                                 ▼          │
                    │                        ┌──────────────┐    │
                    │                        │  自动化登录  │    │
                    │                        └──────────────┘    │
                    └─────────────────────────────────────────────┘
```

### 14.4 数据库存储

```sql
-- 游戏账号表（包含加密密码）
CREATE TABLE game_account (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    streaming_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    xbox_live_email VARCHAR(255) NOT NULL,
    xbox_live_password_encrypted VARCHAR(512) NOT NULL,  -- AES 加密后的密码
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (streaming_id) REFERENCES streaming_account(id)
);

-- Agent 表（存储 Agent 主密钥）
CREATE TABLE agent_instance (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id VARCHAR(64) NOT NULL UNIQUE,
    encryption_key_encrypted VARCHAR(512),  -- 用主密钥加密的 Agent 密钥
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 14.5 安全建议

1. **传输安全**：所有 API 通信使用 HTTPS
2. **密钥管理**：主密钥存储在环境变量或密钥管理服务（KMS）
3. **访问控制**：只有 Agent 才能解密自己的密码
4. **日志脱敏**：日志中禁止记录明文密码
5. **定期轮换**：建议定期更换主密钥

---

## 十五、项目实施计划

### 15.1 开发阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Phase 1** | B-End 平台基础搭建（账号管理、Agent 注册） | P0 |
| **Phase 2** | Agent 核心功能（登录、串流、状态上报） | P0 |
| **Phase 3** | WebSocket 实时通信 | P0 |
| **Phase 4** | 前端监控面板 | P1 |
| **Phase 5** | 异常恢复机制 | P1 |
| **Phase 6** | 游戏账号切换 | P2 |
| **Phase 7** | 统计报表 | P2 |

### 15.2 技术栈总结

| 组件 | 技术 |
|------|------|
| **B-End 前端** | Vue 3 + Element Plus + Pinia |
| **B-End 后端** | Java 17 + Spring Boot 3 |
| **数据库** | MySQL 8.0 |
| **实时通信** | WebSocket |
| **Agent 运行时** | Python 3.10+ |
| **自动化框架** | Electron + Selenium-like APIs |
| **视频捕获** | VideoFrameCapture (WebRTC) |
| **模板匹配** | OpenCV + 归一化坐标 |

### 15.3 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        云服务器 (必选)                            │
│                  B-End 平台 + MySQL                             │
│                  (阿里云/腾讯云/等)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 互联网
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │  Agent 1  │        │  Agent 2  │        │  Agent N  │
   │ (地点 A)  │        │ (地点 B)  │        │ (地点 N)  │
   └───────────┘        └───────────┘        └───────────┘
```

---

## 十六、设计文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 多窗口自动化设计 | `.trae/documents/multi_window_automation_complete_design.md` | Python Agent、多窗口、分布式部署 |
| B-End 平台设计 | `.trae/documents/bend_platform_design.md` | Vue + Java + MySQL 完整方案 |

**相关设计文档：**
- [login_auth_fix_plan.md](.trae/documents/login_auth_fix_plan.md) - 登录认证修复
- [ttt_reference_analysis.md](.trae/documents/ttt_reference_analysis.md) - TTT 参考分析
- [bend_platform_design.md](.trae/documents/bend_platform_design.md) - B 端平台设计
