# 多窗口自动化串流系统设计方案

## 一、设计目标

| 目标 | 说明 |
|------|------|
| **独立窗口** | 不依赖 XStreaming 主窗口，自定义渲染窗口 |
| **实时视频流** | 获取 Xbox 实时视频帧用于图像识别 |
| **窗口自由操作** | 支持拖拽、最小化，不影响截图匹配 |
| **多开支持** | 同时运行多个自动化实例（多账号、多 Xbox） |
| **模板匹配** | 基于视频帧的实时模板匹配 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          多窗口自动化串流系统                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      CentralManager (中央管理器)                       │   │
│  │  - 管理多个 StreamWindow 实例                                        │   │
│  │  - 分配端口、session、资源                                             │   │
│  │  - 监控各窗口状态                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│          ┌─────────────────────────┼─────────────────────────┐             │
│          │                         │                         │             │
│          ▼                         ▼                         ▼             │
│  ┌───────────────┐        ┌───────────────┐        ┌───────────────┐    │
│  │ StreamWindow  │        │ StreamWindow  │        │ StreamWindow  │    │
│  │   实例 1      │        │   实例 2      │        │   实例 N      │    │
│  │               │        │               │        │               │    │
│  │ ┌───────────┐ │        │ ┌───────────┐ │        │ ┌───────────┐ │    │
│  │ │ VideoFrame│ │        │ │ VideoFrame│ │        │ │ VideoFrame│ │    │
│  │ │ Capture  │ │        │ │ Capture  │ │        │ │ Capture  │ │    │
│  │ └───────────┘ │        │ └───────────┘ │        │ └───────────┘ │    │
│  │       │       │        │       │       │        │       │       │    │
│  │       ▼       │        │       ▼       │        │       ▼       │    │
│  │ ┌───────────┐ │        │ ┌───────────┐ │        │ ┌───────────┐ │    │
│  │ │  Template │ │        │ │  Template │ │        │ │  Template │ │    │
│  │ │ Matching  │ │        │ │ Matching  │ │        │ │ Matching  │ │    │
│  │ └───────────┘ │        │ └───────────┘ │        │ └───────────┘ │    │
│  │       │       │        │       │       │        │       │       │    │
│  │       ▼       │        │       ▼       │        │       ▼       │    │
│  │ ┌───────────┐ │        │ ┌───────────┐ │        │ ┌───────────┐ │    │
│  │ │  Input    │ │        │ │  Input    │ │        │ │  Input    │ │    │
│  │ │ Controller│ │        │ │ Controller│ │        │ │ Controller│ │    │
│  │ └───────────┘ │        │ └───────────┘ │        │ └───────────┘ │    │
│  └───────────────┘        └───────────────┘        └───────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件设计

### 3.1 VideoFrameCapture (视频帧捕获器)

**职责**：从 xStreamingPlayer 的视频流中捕获帧，用于图像识别

```typescript
class VideoFrameCapture {
  private video: HTMLVideoElement;
  private canvas: OffscreenCanvas;
  private ctx: OffscreenCanvasRenderingContext2D;

  constructor(videoElement: HTMLVideoElement) {
    this.canvas = new OffscreenCanvas(videoElement.videoWidth, videoElement.videoHeight);
    this.ctx = this.canvas.getContext('2d');
  }

  /**
   * 捕获当前视频帧
   * 返回归一化坐标 (0-1) 的图像数据，适配任意窗口大小
   */
  captureFrame(): ImageData {
    // 绘制当前帧到 canvas
    this.ctx.drawImage(this.video, 0, 0);

    // 获取图像数据 - 归一化坐标
    return this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
  }

  /**
   * 获取缩放后的帧（用于显示）
   */
  captureScaledFrame(width: number, height: number): ImageData {
    const tempCanvas = new OffscreenCanvas(width, height);
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(this.video, 0, 0, width, height);
    return tempCtx.getImageData(0, 0, width, height);
  }

  /**
   * 获取视频坐标到显示坐标的变换矩阵
   * 用于处理 letterbox/pillarbox 留黑边情况
   */
  getCoordinateTransform(): CoordinateTransform {
    const videoAspect = this.video.videoWidth / this.video.videoHeight;
    const displayAspect = this.video.clientWidth / this.video.clientHeight;

    let offsetX = 0, offsetY = 0, scale = 1;

    if (videoAspect > displayAspect) {
      // 视频更宽，按宽度填充，顶部底部留黑
      scale = this.video.clientWidth / this.video.videoWidth;
      offsetY = (this.video.clientHeight - this.video.videoHeight * scale) / 2;
    } else {
      // 视频更高，按高度填充，左侧右侧留黑
      scale = this.video.clientHeight / this.video.videoHeight;
      offsetX = (this.video.clientWidth - this.video.videoWidth * scale) / 2;
    }

    return { offsetX, offsetY, scale };
  }
}
```

### 3.2 TemplateMatcher (模板匹配器)

**职责**：在视频帧中查找模板，返回归一化坐标

```typescript
interface MatchResult {
  found: boolean;
  x: number;      // 归一化坐标 (0-1)
  y: number;      // 归一化坐标 (0-1)
  width: number;  // 归一化尺寸
  height: number;
  confidence: number;
}

class TemplateMatcher {
  private templates: Map<string, ImageData> = new Map();

  /**
   * 加载模板
   * @param name 模板名称
   * @param imagePath 模板图片路径
   */
  async loadTemplate(name: string, imagePath: string): Promise<void> {
    const img = await loadImage(imagePath);
    const canvas = new OffscreenCanvas(img.width, img.height);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    this.templates.set(name, ctx.getImageData(0, 0, canvas.width, canvas.height));
  }

  /**
   * 在帧中查找模板
   * @param frame 视频帧
   * @param templateName 模板名称
   * @param threshold 匹配阈值
   */
  match(frame: ImageData, templateName: string, threshold = 0.8): MatchResult {
    const template = this.templates.get(templateName);
    if (!template) {
      return { found: false, x: 0, y: 0, width: 0, height: 0, confidence: 0 };
    }

    // 使用 OpenCV 或 TF.js 进行模板匹配
    const result = cv.matchTemplate(frame, template, cv.TM_CCOEFF_NORMED);

    // 找最大值位置
    const { maxVal, maxLoc } = cv.minMaxLoc(result);

    if (maxVal >= threshold) {
      return {
        found: true,
        x: maxLoc.x / frame.width,          // 归一化
        y: maxLoc.y / frame.height,         // 归一化
        width: template.width / frame.width, // 归一化
        height: template.height / frame.height,
        confidence: maxVal
      };
    }

    return { found: false, x: 0, y: 0, width: 0, height: 0, confidence: 0 };
  }
}
```

### 3.3 InputController (输入控制器)

**职责**：发送手柄/键盘输入到 Xbox

```typescript
interface GamepadState {
  buttons: {
    A: boolean;
    B: boolean;
    X: boolean;
    Y: boolean;
    Up: boolean;
    Down: boolean;
    Left: boolean;
    Right: boolean;
    LeftShoulder: boolean;
    RightShoulder: boolean;
    LeftStick: boolean;
    RightStick: boolean;
    Start: boolean;
    Back: boolean;
  };
  leftTrigger: number;  // 0-1
  rightTrigger: number; // 0-1
  leftStickX: number;   // -1 to 1
  leftStickY: number;
  rightStickX: number;
  rightStickY: number;
}

class InputController {
  private xPlayer: xStreamingPlayer;

  constructor(xPlayer: xStreamingPlayer) {
    this.xPlayer = xPlayer;
  }

  /**
   * 按下并释放按钮
   */
  async clickButton(button: keyof GamepadState['buttons']): Promise<void> {
    const processor = this.xPlayer.getChannelProcessor("input");
    processor.pressButtonStart(button);
    await delay(100);
    processor.pressButtonEnd(button);
  }

  /**
   * 移动摇杆到指定归一化位置
   */
  moveLeftStick(normalizedX: number, normalizedY: number): void {
    // 归一化坐标 (-1 to 1) 转换
    const processor = this.xPlayer.getChannelProcessor("input");
    processor.setLeftStick(normalizedX * 32767, normalizedY * 32767);
  }

  /**
   * 点击归一化坐标位置（通过移动光标+确认）
   */
  async clickAt(frame: ImageData, normalizedX: number, normalizedY: number): Promise<void> {
    // 1. 移动左摇杆到目标位置
    this.moveLeftStick(normalizedX * 2 - 1, normalizedY * 2 - 1);
    await delay(500);

    // 2. 点击 A 确认
    await this.clickButton('A');
  }
}
```

### 3.4 StreamWindow (串流窗口)

**职责**：管理单个串流实例的窗口、播放器、自动化

```typescript
interface StreamWindowConfig {
  instanceId: string;
  container: HTMLElement;        // 窗口容器 DOM
  serverId: string;              // Xbox Server ID
  account: AccountConfig;        // 账号配置
  templates: string[];          // 需要加载的模板列表
  onStateChange: (state: WindowState) => void;
}

enum WindowState {
  INITIALIZING = 'initializing',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  STREAMING = 'streaming',
  AUTOMATING = 'automating',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

class StreamWindow {
  private config: StreamWindowConfig;
  private xPlayer: xStreamingPlayer;
  private frameCapture: VideoFrameCapture;
  private templateMatcher: TemplateMatcher;
  private inputController: InputController;
  private state: WindowState;
  private sessionId: string;

  constructor(config: StreamWindowConfig) {
    this.config = config;
    this.state = WindowState.INITIALIZING;
  }

  /**
   * 初始化窗口
   */
  async init(): Promise<void> {
    // 1. 创建视频播放器
    const playerContainer = document.createElement('div');
    playerContainer.id = `video-${this.config.instanceId}`;
    this.config.container.appendChild(playerContainer);

    this.xPlayer = new xStreamingPlayer(playerContainer.id, {
      input_touch: false,
      input_mousekeyboard: true,
    });

    // 2. 初始化帧捕获器
    const videoElement = playerContainer.querySelector('video');
    this.frameCapture = new VideoFrameCapture(videoElement);

    // 3. 初始化模板匹配器
    this.templateMatcher = new TemplateMatcher();
    for (const t of this.config.templates) {
      await this.templateMatcher.loadTemplate(t.name, t.path);
    }

    // 4. 初始化输入控制器
    this.inputController = new InputController(this.xPlayer);

    // 5. 绑定播放器事件
    this.bindPlayerEvents();

    this.updateState(WindowState.CONNECTING);
  }

  /**
   * 开始串流
   */
  async startStream(): Promise<void> {
    // 通过 IPC 启动串流
    const sessionId = await Ipc.send("streaming", "startStream", {
      type: 'home',
      target: this.config.serverId
    });
    this.sessionId = sessionId;
    this.updateState(WindowState.CONNECTED);
  }

  /**
   * 执行自动化
   */
  async runAutomation(): Promise<void> {
    this.updateState(WindowState.AUTOMATING);

    while (this.state === WindowState.AUTOMATING) {
      // 1. 捕获当前帧
      const frame = this.frameCapture.captureFrame();

      // 2. 尝试匹配模板
      const loginBtn = this.templateMatcher.match(frame, 'login_button', 0.8);
      if (loginBtn.found) {
        console.log(`[实例${this.config.instanceId}] 检测到登录按钮`);
        await this.inputController.clickAt(frame, loginBtn.x, loginBtn.y);
        await delay(500);
        continue;
      }

      // ... 其他模板匹配

      // 3. 小延迟避免 CPU 过高
      await delay(100);
    }
  }

  /**
   * 获取归一化坐标的点击位置
   * 窗口拖拽/缩放不影响，因为使用的是视频帧坐标
   */
  private getClickPosition(normalizedX: number, normalizedY: number): { x: number, y: number } {
    const transform = this.frameCapture.getCoordinateTransform();

    // 视频坐标 -> 显示坐标
    return {
      x: normalizedX * transform.scale + transform.offsetX,
      y: normalizedY * transform.scale + transform.offsetY
    };
  }

  private updateState(newState: WindowState): void {
    this.state = newState;
    this.config.onStateChange?.(newState);
  }
}
```

### 3.5 CentralManager (中央管理器)

**职责**：管理多个 StreamWindow 实例

```typescript
interface MultiWindowConfig {
  maxInstances: number;  // 最大实例数
  basePort: number;      // 基础端口
}

class CentralManager {
  private instances: Map<string, StreamWindow> = new Map();
  private config: MultiWindowConfig;

  constructor(config: MultiWindowConfig) {
    this.config = config;
  }

  /**
   * 创建新实例
   */
  async createInstance(config: {
    serverId: string;
    account: AccountConfig;
    templates: TemplateConfig[];
  }): Promise<string> {
    if (this.instances.size >= this.config.maxInstances) {
      throw new Error(`已达最大实例数: ${this.config.maxInstances}`);
    }

    const instanceId = `instance_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // 1. 创建窗口容器
    const container = this.createWindowContainer(instanceId);

    // 2. 创建 StreamWindow 实例
    const streamWindow = new StreamWindow({
      instanceId,
      container,
      serverId: config.serverId,
      account: config.account,
      templates: config.templates,
      onStateChange: (state) => this.onInstanceStateChange(instanceId, state)
    });

    await streamWindow.init();
    await streamWindow.startStream();

    this.instances.set(instanceId, streamWindow);
    return instanceId;
  }

  /**
   * 创建窗口容器
   * 每个实例独立的可拖拽、最小化窗口
   */
  private createWindowContainer(instanceId: string): HTMLElement {
    const container = document.createElement('div');
    container.id = `window-${instanceId}`;
    container.className = 'stream-window';
    container.style.cssText = `
      position: fixed;
      width: 1280px;
      height: 720px;
      border: 2px solid #333;
      border-radius: 8px;
      overflow: hidden;
      resize: both;
      draggable: true;
    `;

    // 拖拽支持
    this.makeDraggable(container);

    // 最小化支持
    this.addMinimizeSupport(container);

    document.body.appendChild(container);
    return container;
  }

  private makeDraggable(element: HTMLElement): void {
    let isDragging = false;
    let startX, startY, initialX, initialY;

    element.addEventListener('mousedown', (e) => {
      if ((e.target as HTMLElement).closest('.window-controls')) return;
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = element.getBoundingClientRect();
      initialX = rect.left;
      initialY = rect.top;
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      element.style.left = `${initialX + dx}px`;
      element.style.top = `${initialY + dy}px`;
    });

    document.addEventListener('mouseup', () => {
      isDragging = false;
    });
  }

  private addMinimizeSupport(container: HTMLElement): void {
    const header = document.createElement('div');
    header.className = 'window-header';
    header.innerHTML = `
      <span class="window-title">串流实例</span>
      <div class="window-controls">
        <button class="minimize-btn">─</button>
        <button class="close-btn">×</button>
      </div>
    `;

    container.insertBefore(header, container.firstChild);

    header.querySelector('.minimize-btn')?.addEventListener('click', () => {
      container.classList.toggle('minimized');
    });

    header.querySelector('.close-btn')?.addEventListener('click', () => {
      this.closeInstance(container.id.replace('window-', ''));
    });
  }

  private onInstanceStateChange(instanceId: string, state: WindowState): void {
    console.log(`[CentralManager] 实例 ${instanceId} 状态变更: ${state}`);
  }

  async closeInstance(instanceId: string): Promise<void> {
    const instance = this.instances.get(instanceId);
    if (instance) {
      await instance.close();
      this.instances.delete(instanceId);
    }
  }
}
```

---

## 四、坐标系统设计

### 4.1 核心思想

**使用视频帧的归一化坐标 (0-1)**，不受窗口位置、大小、最小化影响

```
┌─────────────────────────────────────┐
│           Electron 窗口              │
│  ┌───────────────────────────────┐ │
│  │                               │ │
│  │    ┌─────────────────────┐    │ │  ← 可能有黑边 (letterbox)
│  │    │                     │    │ │
│  │    │    视频画面         │    │ │
│  │    │                     │    │ │
│  │    └─────────────────────┘    │ │
│  │                               │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
```

### 4.2 坐标转换

```typescript
// 模板匹配返回的是归一化坐标 (0-1)
const match = templateMatcher.match(frame, 'login_button');
// match.x = 0.5, match.y = 0.8 (屏幕中心偏下)

// 点击时，需要考虑 letterbox 偏移
const transform = frameCapture.getCoordinateTransform();
// transform = { offsetX: 0, offsetY: 50, scale: 1.5 }

// 计算实际点击位置
const clickX = match.x * videoWidth * transform.scale + transform.offsetX;
const clickY = match.y * videoHeight * transform.scale + transform.offsetY;

// 使用 xPlayer 发送输入（已处理内部坐标）
inputController.clickAt(frame, match.x, match.y);
```

### 4.3 最小化/拖拽处理

```typescript
// 当窗口最小化时，视频仍然在播放（只是不可见）
// xStreamingPlayer 仍然在解码帧

// 帧捕获器仍然可以工作
const frame = frameCapture.captureFrame(); // 仍然返回当前帧

// 模板匹配仍然准确（基于视频内容）
const match = templateMatcher.match(frame, 'login_button');

// 窗口恢复后，显示会重新同步
```

---

## 五、多窗口同步机制

### 5.1 中央状态同步

```typescript
interface SystemState {
  instances: {
    [instanceId: string]: {
      state: WindowState;
      sessionId: string;
      lastHeartbeat: number;
    }
  };
}

class CentralManager {
  private state: SystemState;
  private heartbeatInterval: number = 5000;

  startHeartbeat(): void {
    setInterval(() => {
      for (const [id, instance] of this.instances) {
        const isAlive = instance.isHealthy();
        if (!isAlive) {
          this.handleInstanceDead(id);
        }
      }
    }, this.heartbeatInterval);
  }
}
```

### 5.2 资源隔离

| 资源 | 隔离方式 |
|------|----------|
| 内存 | 每个 StreamWindow 独立实例 |
| 端口 | 每个实例独立端口 (basePort + index) |
| session | 每个实例独立 sessionId |
| 窗口 | DOM 容器隔离 |

---

## 六、文件结构

```
automation/
├── main.py                      # 主入口
├── config.json                   # 配置文件
│
├── services/                     # 服务层
│   ├── __init__.py
│   ├── login_service.py         # 登录服务
│   └── stream_service.py        # 串流服务
│
├── core/                         # 核心组件
│   ├── __init__.py
│   ├── electron_bridge.py        # Electron 通信
│   ├── window_controller.py      # 窗口控制
│   └── ui_detector.py            # UI 检测
│
├── automation.py                # 自动化整合器
│
├── renderer/                     # 前端渲染 (Electron HTML)
│   ├── index.html               # 主页面
│   ├── stream_window.js          # 串流窗口逻辑
│   ├── video_capture.js         # 视频帧捕获
│   ├── template_matcher.js       # 模板匹配
│   └── styles.css               # 样式
│
└── templates/                   # 模板图片
    ├── login/
    │   ├── login_button.png
    │   ├── email_input.png
    │   └── password_input.png
    └── stream/
        ├── console_card.png
        └── stream_button.png
```

---

## 七、工作流程

### 7.1 启动流程

```
┌──────────────────────────────────────────────────────────────┐
│                        启动主进程                             │
│                         main.py                              │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    创建 Electron 窗口                        │
│                    (renderer/index.html)                      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    加载 CentralManager                      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    等待用户操作                              │
│              (创建实例 / 关闭 / 配置)                        │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 创建实例流程

```
用户点击"创建实例"
    │
    ▼
分配 instanceId 和端口
    │
    ▼
创建 DOM 容器 (可拖拽/最小化)
    │
    ▼
初始化 StreamWindow
    │
    ├── 创建 xStreamingPlayer
    ├── 加载模板
    └── 初始化帧捕获器
    │
    ▼
启动串流 (IPC -> startStream)
    │
    ▼
WebRTC 连接建立
    │
    ▼
开始自动化循环
    │
    ├── 捕获视频帧
    ├── 模板匹配
    └── 发送输入
```

---

## 八、关键优势

| 特性 | 实现方式 |
|------|----------|
| **窗口自由拖拽** | CSS `position: fixed` + 鼠标事件 |
| **最小化不影响** | 使用视频帧坐标，不依赖窗口坐标 |
| **多开支持** | 每个实例独立 StreamWindow 实例 |
| **实时匹配** | OffscreenCanvas 捕获视频帧 |
| **精确点击** | 归一化坐标 + 坐标变换 |

---

## 九、待解决问题

1. **视频帧捕获性能** - 需要测试 30fps/60fps 捕获是否流畅
2. **模板匹配速度** - 大图匹配可能较慢，考虑使用 SIFT/ORB
3. **WebRTC 依赖** - 需要 xStreamingPlayer 支持独立实例
4. **IPC 通信** - 多实例的 session 管理

---

## 十、实施建议

### 阶段一：基础框架
1. 创建 Electron 窗口
2. 实现视频帧捕获
3. 基本模板匹配

### 阶段二：多窗口支持
1. CentralManager
2. 窗口拖拽/最小化
3. 实例隔离

### 阶段三：自动化集成
1. 登录服务
2. 串流服务
3. 输入控制器
