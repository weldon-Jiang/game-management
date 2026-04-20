# XStreaming 串流技术分析

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    XStreaming 串流架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Electron 渲染进程 (Next.js + React)                           │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  stream.tsx                                              │  │
│  │    ↓ 创建 xStreamingPlayer                              │  │
│  │    ↓ WebRTC RTCPeerConnection                           │  │
│  │    ↓ 获取 SDP Offer/Answer                              │  │
│  │    ↓ 通过 IPC 与主进程通信                               │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↕ IPC                             │
│  Electron 主进程 (Node.js)                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  application.ts - StreamingManager                      │  │
│  │    ↓ startStream() - 启动 Xbox 串流                     │  │
│  │    ↓ sendSdp() / sendIce() - 信令交换                   │  │
│  │    ↓ getPlayerState() - 获取状态                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↕                                  │
│  本地服务                                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Xbox 串流服务 (Xbox Streaming Service)                  │  │
│  │    - XboxConsole 类                                      │  │
│  │    - StreamManager 类                                    │  │
│  │    - XcloudApi 类                                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              ↕                                  │
│  Xbox 主机 (远程)                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Xbox Console                                            │  │
│  │    - 视频编码 (H264)                                     │  │
│  │    - 手柄状态接收                                        │  │
│  │    - 音频编码                                            │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、WebRTC 串流流程

### 2.1 核心组件：xStreamingPlayer

```typescript
// renderer/pages/[locale]/stream.tsx
import xStreamingPlayer from "xstreaming-player";

// 创建播放器实例
const xPlayer = new xStreamingPlayer("videoHolder", {
  input_touch: false,
  ui_touchenabled: false,
  input_mousekeyboard: settings.enable_native_mouse_keyboard,
  input_legacykeyboard: true,
});

// 配置
xPlayer.setVideoFormat(settings.video_format || "");
xPlayer.setGamepadKernal("Web");
xPlayer.setGamepadIndex(settings.gamepad_index);
xPlayer.setVibration(settings.vibration);
```

### 2.2 WebRTC 信令流程

```
┌──────────────┐                           ┌──────────────┐
│  xStreaming  │                           │    Xbox      │
│   Player     │                           │   Console    │
└──────┬───────┘                           └──────┬───────┘
       │                                         │
       │  createOffer()                           │
       │───────────────── SDP Offer ─────────────>│
       │                                         │
       │  setRemoteOffer()                        │
       │<──────────────── SDP Answer ────────────│
       │                                         │
       │  getIceCandidates()                      │
       │───────────────── ICE Candidates ─────────>│
       │                                         │
       │  setIceCandidates()                      │
       │<─────────────────────────────────────────│
       │                                         │
       │  [WebRTC 视频流建立]                      │
       │<══════════════════ 视频流 ════════════════│
       │                                         │
```

### 2.3 IPC 通信

```typescript
// 通过 IPC 与主进程通信
Ipc.send("streaming", "startStream", {
  type: streamType,  // "home" 或 "cloud"
  target: serverId,   // Xbox console ID
})
  .then((sessionId) => {
    // sessionId 用于后续通信
  });

// 获取播放状态
Ipc.send("streaming", "getPlayerState", { sessionId });

// SDP 交换
Ipc.send("streaming", "sendSdp", { sessionId, sdp: offer.sdp });

// ICE 交换
Ipc.send("streaming", "sendIce", { sessionId, ice: candidates });
```

---

## 三、主进程串流管理

### 3.1 StreamingManager

```typescript
// main/application.ts
class StreamingManager {
  async startStream(type: string, target: string): Promise<string> {
    // 启动串流会话，返回 sessionId
  }

  async sendSdp(sessionId: string, sdp: string): Promise<string> {
    // 发送 SDP 到 Xbox，获取远程 SDP
  }

  async sendIce(sessionId: string, ice: any[]): Promise<any[]> {
    // 转发 ICE candidate 到 Xbox
  }

  async getPlayerState(sessionId: string): Promise<PlayerState> {
    // 获取当前串流状态
  }

  async stopStream(sessionId: string): Promise<void> {
    // 停止串流
  }
}
```

### 3.2 XboxConsole 类

```typescript
// main/helpers/xboxConsole.ts
class XboxConsole {
  private _xbox: Xbox;

  async pair(): Promise<void> {
    // 与 Xbox 配对
  }

  async connect(): Promise<void> {
    // 连接 Xbox
  }

  async getConnectionToken(): Promise<string> {
    // 获取连接令牌
  }
}
```

---

## 四、xStreamingPlayer 内部机制

### 4.1 视频解码和渲染

```typescript
// 使用 HTML5 Video + Canvas 渲染
<div id="videoHolder">
  {/* video 元素由 xStreamingPlayer 创建 */}
</div>

<div id="canvas-container">
  <canvas id="canvas"></canvas>
  {/* 用于 FSR (FidelityFX Super Resolution) */}
</div>
```

### 4.2 手柄输入

```typescript
// 设置手柄
xPlayer.setGamepadKernal("Web");  // 使用 Web Gamepad API
xPlayer.setGamepadIndex(settings.gamepad_index);
xPlayer.setGamepadDeadZone(settings.dead_zone);

// 发送手柄输入
xPlayer.getChannelProcessor("input").pressButtonStart("Nexus");
xPlayer.getChannelProcessor("input").pressButtonEnd("Nexus");
```

### 4.3 控制命令

```typescript
// 发送文本到 Xbox
Ipc.send("consoles", "sendText", { consoleId, text });

// 关机
Ipc.send("consoles", "powerOff", consoleId);
```

---

## 五、连接和控制的完整流程

```
1. 用户选择 Xbox 主机
   ↓
2. IPC: streaming.startStream(type, target)
   ↓
3. 主进程启动 Xbox 串流服务
   ↓
4. 返回 sessionId
   ↓
5. 创建 xStreamingPlayer 实例
   ↓
6. xPlayer.createOffer() → 获取本地 SDP
   ↓
7. IPC: streaming.sendSdp(sessionId, sdp)
   ↓
8. 主进程转发 SDP 到 Xbox
   ↓
9. Xbox 返回远程 SDP
   ↓
10. xPlayer.setRemoteOffer(sdp)
    ↓
11. 交换 ICE Candidates
    ↓
12. WebRTC 视频流建立
    ↓
13. video 元素开始播放视频
```

---

## 六、关键技术点

### 6.1 视频格式

```typescript
xPlayer.setVideoFormat(settings.video_format || "");
// 支持: H264-High, H264-Medium, H264-Low
```

### 6.2 TURN 服务器

```typescript
xPlayer.bind({
  turnServer: {
    url: server_url,
    username: server_username,
    credential: server_credential
  }
});
```

### 6.3 FSR (FidelityFX Super Resolution)

```typescript
// 在连接成功后启用
if (settings.fsr) {
  xPlayer.startFSR(() => {
    // FSR 启动成功
  });
}
```

---

## 七、对自动化项目的启示

### 7.1 当前项目 vs XStreaming

| 功能 | XStreaming | 自动化项目 |
|------|------------|-----------|
| 视频流 | WebRTC (xStreamingPlayer) | Electron capturePage |
| 手柄控制 | WebRTC DataChannel | JS 注入 / 虚拟手柄 |
| 画面渲染 | HTML5 Video 元素 | Electron capturePage |
| 连接建立 | SDP/ICE 信令 | OAuth |

### 7.2 自动化可以借鉴的

1. **WebRTC 信令机制** - 如果要实现更底层的串流控制
2. **xStreamingPlayer 的手柄映射** - Web Gamepad API 的使用
3. **IPC 通信模式** - 主进程和渲染进程的分离

### 7.3 当前自动化方案的局限性

- `capturePage()` 是**静态截图**，不是实时视频流
- 无法获取 Xbox 的实时视频帧进行图像识别
- 只能通过模板匹配检测 UI 元素

### 7.4 改进方向

如果需要更强大的自动化能力（如检测游戏画面、实时响应）：
1. 集成 xStreamingPlayer 获取实时视频流
2. 在 Canvas 上进行实时图像识别
3. 通过 WebRTC DataChannel 发送手柄指令
