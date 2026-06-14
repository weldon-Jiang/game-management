> **架构勘误（2026-06-13）**：生产 Step2–3 为 **xblive/xsrp（GSSV 云端 + WebRTC）**，入口见 `bend-agent/src/agent/automation/step2_xsrp.py`、`step3_xsrp.py`。下文 SmartGlass LAN、`step2_xbox_streaming.py` 等为**历史方案**；SmartGlass UDP 仅作 LAN 发现/唤醒兜底。详见 [00_架构勘误_xsrp_step2.md](./00_架构勘误_xsrp_step2.md)。

# bend-agent 与 streaming 技术对比分析

**版本**: 4.0
**日期**: 2026-05-30
**状态**: 待执行

***

## 背景说明

* **streaming项目**：生产可用，单机模式，成熟稳定

* **bend-agent系统**：重构版本，线上化管理，需借鉴streaming的成熟技术

***

## 执行计划总览

### 步骤执行状态

| 步骤  | 名称         | 状态    | 开始时间 | 完成时间       | 备注                  |
| --- | ---------- | ----- | ---- | ---------- | ------------------- |
| 步骤一 | 串流账号登录认证   | ✅ 已完成 | -    | 2026-05-30 | 功能已优于streaming，无需开发 |
| 步骤二 | Xbox串流连接   | ✅ 已完成 | 2026-05-30 | 2026-05-30 | 已补充PlaySession和SDP握手 |
| 步骤三 | 串流前期准备     | ✅ 已完成 | 2026-05-30 | 2026-05-30 | 已补充手柄控制和键盘映射 |
| 步骤四 | 自动操作Xbox主机 | ✅ 已完成 | 2026-05-30 | 2026-05-30 | 已补充场景识别和账号切换 |

### 当前执行步骤

> **所有步骤已完成！**

> **步骤四已完成**：已集成场景识别、账号切换和动作执行功能（参考streaming项目），新增/更新文件：
> - `src/agent/scene/game_automation_engine.py` - 场景识别和动作执行引擎
> - `src/agent/game/account_switcher.py` - 游戏账号切换器
> - `src/agent/automation/step4_game_automation.py` - 集成新功能

全部四个步骤开发完成！

***

## 一、步骤一：串流账号登录认证

### 1.1 执行状态

| 项目        | 内容         |
| --------- | ---------- |
| **状态**    | ✅ 已完成      |
| **依赖**    | 无          |
| **预计工作量** | 已完成，无需开发   |
| **完成日期**  | 2026-05-30 |

### 1.2 对比分析

**streaming项目实现**：

```
设备码认证 → Bearer Token → Xbox User Token → XSTS Token
```

**bend-agent实现**：

```
MSAL认证 / 浏览器自动化 → Xbox User Token → XSTS Token
```

### 1.3 差距对比

| 功能点      | streaming | bend-agent      | 结论        |
| -------- | --------- | --------------- | --------- |
| 认证方式     | 设备码轮询     | MSAL + 浏览器自动化   | ✅ Agent更优 |
| Token持久化 | ❌ 无       | ✅ Refresh Token | ✅ Agent更优 |
| 多账号管理    | ❌ 无       | ✅ 有             | ✅ Agent更优 |
| 生产验证     | ✅ 是       | ⚠️ 需验证          | 待验证       |

### 1.4 结论

**步骤一功能Agent更优，保持现状即可。**

### 1.5 验证清单

* [ ] 生产环境认证测试

* [ ] Refresh Token刷新验证

* [ ] 多账号切换验证

### 1.6 执行记录

| 日期         | 操作     | 结果                | 确认人 |
| ---------- | ------ | ----------------- | --- |
| 2026-05-30 | 技术对比分析 | MSAL方案优于streaming | -   |

***

## 二、步骤二：Xbox串流连接

### 2.1 执行状态

| 项目        | 内容       |
| --------- | -------- |
| **状态**    | ✅ 已完成    |
| **前置步骤**  | 步骤一完成   |
| **预计工作量** | 3-5天     |
| **完成日期**  | 2026-05-30 |

### 2.2 实现内容

**参考streaming项目实现的功能**：

| 功能 | 实现状态 | 文件位置 |
|------|--------|---------|
| PlaySession管理 | ✅ 已实现 | `src/agent/xbox/play_session.py` |
| Xbox服务器发现 | ✅ 已实现 | `src/agent/xbox/play_session.py` |
| SDP握手 | ✅ 已实现 | `src/agent/xbox/webrtc_handler.py` |
| WebRTC Offer/Answer | ✅ 已实现 | `src/agent/xbox/webrtc_handler.py` |
| ICE候选处理 | ✅ 已实现 | `src/agent/xbox/webrtc_handler.py` |

### 2.3 新增文件

#### `src/agent/xbox/play_session.py`
- `XboxPlaySessionManager`: PlaySession管理器类
- `PlaySessionConfig`: 会话配置
- `SessionState`: 会话状态枚举
- `SDPConfiguration`: SDP配置

#### `src/agent/xbox/webrtc_handler.py`
- `XboxWebRTCHandler`: WebRTC握手处理器
- `WebRTCConfig`: WebRTC配置
- `SDPBuilder`: SDP消息构建器
- `IceCandidate`: ICE候选信息

### 2.4 对比分析

**streaming项目实现**：

```
Token认证 → 发现Xbox服务器 → 创建播放会话 → SDP握手 → WebRTC连接
```

**bend-agent实现（已更新）**：

```
Token认证 → 发现Xbox主机 → 建立连接 → PlaySession创建 → SDP握手 → WebRTC连接
```

### 2.5 执行记录

| 日期         | 操作         | 结果                      | 确认人 |
| ---------- | ---------- | ----------------------- | --- |
| 2026-05-30 | PlaySession管理器 | 已实现                    | -   |
| 2026-05-30 | WebRTC SDP握手 | 已实现                    | -   |
| 2026-05-30 | step2集成 | 已更新step2_xsrp.py | -   |

### 2.4 待开发任务

#### 2.4.1 PlaySession创建（P0）

```python
# streaming实现参考
url_play = f'{url_root}/{play_path}'
data_play = {
    "clientSessionId": "",
    "titleId": "",
    "serverId": server_id,
    "settings": {
        "nanoVersion": "V3;WebrtcTransport.dll",
        "osName": "windows",
        "sdkType": "web",
        "useIceConnection": False
    }
}
requests.post(url_play, json=data_play)
```

**Agent实现方案**：

```python
# src/agent/xbox/play_session.py
class PlaySessionManager:
    async def create_session(self, xbox_info: XboxInfo, token: str) -> str:
        """创建Xbox流播放会话"""
        url = f'https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home'
        # 实现PlaySession创建逻辑
        pass
```

#### 2.4.2 SDP握手（P1）

**streaming实现参考**：

```python
url = f'{url_root}/{session_path}/sdp'
data_sdp = {
    "messageType": "offer",
    "sdp": x.sdp,
    "configuration": {
        "chatConfiguration": {"codec": "opus"},
        "control": {"minVersion": 1, "maxVersion": 3},
        "input": {"minVersion": 1, "maxVersion": 8}
    }
}
requests.post(url, json=data_sdp)
```

### 2.5 验证清单

- [x] PlaySession创建
- [x] Xbox服务器发现
- [x] SDP握手
- [x] WebRTC Offer/Answer
- [ ] 生产环境测试（待执行）

### 2.6 技术实现细节

#### 2.6.1 PlaySession创建流程

```python
# 1. 设置访问令牌
play_session_mgr.set_access_token(ms_token)

# 2. 发现Xbox服务器
servers = await play_session_mgr.discover_servers()

# 3. 创建播放会话
session = await play_session_mgr.create_session(
    server_id=server_id,
    config=PlaySessionConfig(
        nano_version="V3;WebrtcTransport.dll",
        os_name="windows",
        sdk_type="web"
    )
)
```

#### 2.6.2 SDP握手流程

```python
# 1. 创建WebRTC Offer
webrtc = XboxWebRTCHandler(WebRTCConfig(...))
sdp_offer = webrtc.create_offer()

# 2. 交换SDP
sdp_answer = await play_session_mgr.exchange_sdp(
    session_id=session.session_id,
    sdp_offer=sdp_offer
)

# 3. 处理Answer
webrtc.handle_answer(sdp_answer)
```

---

## 三、步骤三：串流前期准备

### 3.1 执行状态

| 项目        | 内容       |
| --------- | -------- |
| **状态**    | ✅ 已完成    |
| **前置步骤**  | 步骤二完成   |
| **预计工作量** | 5-7天     |
| **完成日期**  | 2026-05-30 |

### 3.2 实现内容

**参考streaming项目实现的功能**：

| 功能 | 实现状态 | 文件位置 |
|------|--------|---------|
| Xbox手柄控制器 | ✅ 已实现 | `src/agent/input/xbox_gamepad.py` |
| 键盘映射器 | ✅ 已实现 | `src/agent/input/keyboard_mapper.py` |
| 手柄信号协议 | ✅ 已实现 | `src/agent/input/controller_protocol.py` |
| 步骤三集成 | ✅ 已实现 | `src/agent/automation/step3_xsrp.py` |

### 3.3 新增文件

#### `src/agent/input/xbox_gamepad.py`
- `XboxGamepadController`: pygame手柄控制器
- `XboxButton`: 按钮枚举
- `XboxAxis`: 摇杆枚举
- `GamepadInput`: 输入数据
- `GamepadSignal`: 手柄信号

#### `src/agent/input/keyboard_mapper.py`
- `KeyboardMapper`: 键盘映射器
- `KeyAction`: 按键动作枚举
- `KeyBinding`: 按键绑定配置

#### `src/agent/input/controller_protocol.py`
- `ControllerProtocol`: 手柄协议处理器
- `ControllerSignal`: 手柄信号数据
- `XboxButtonFlag`: 按钮标志位

### 3.4 对比分析

**streaming项目实现**：

```
┌─────────────────────────────────────────────────────────────┐
│  硬件解码层：FFmpeg NVDEC/AMF/QSV                          │
│  渲染引擎层：SDL2自绘窗口                                    │
│  输入控制层：SDL2 GameController + 键盘映射                  │
└─────────────────────────────────────────────────────────────┘
```

**bend-agent实现（已更新）**：

```
┌─────────────────────────────────────────────────────────────┐
│  输入控制层：pygame GameController + 键盘映射               │
└─────────────────────────────────────────────────────────────┘
```

### 3.5 待补充（P1/P2优先级）

| 缺失项 | streaming实现 | 优先级 | 说明 |
|--------|--------------|--------|------|
| GPU解码 | FFmpeg NVDEC/AMF | P1 | 可后续优化 |
| 渲染引擎 | SDL2 | P2 | PySide6可选 |

### 3.6 执行记录

| 日期         | 操作         | 结果                | 确认人 |
| ---------- | ---------- | ----------------- | --- |
| 2026-05-30 | Xbox手柄控制器 | 已实现              | -   |
| 2026-05-30 | 键盘映射器 | 已实现              | -   |
| 2026-05-30 | 手柄信号协议 | 已实现              | -   |
| 2026-05-30 | step3集成 | 已更新step3_xsrp.py | -   |

### 3.4 待开发任务

#### 3.4.1 手柄控制（P0）

**streaming实现参考**：

```python
# SDL2 GameController
controller = sdl2.SDL_GameControllerOpen(0)
left_x = sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_LEFTX)
xsrp.WriteControllerData(username, signals)
```

**Agent实现方案（pygame）**：

```python
# src/agent/input/gamepad_controller.py
import pygame
from enum import IntEnum

class XboxButtons(IntEnum):
    A = pygame.CONTROLLER_BUTTON_A
    B = pygame.CONTROLLER_BUTTON_B
    X = pygame.CONTROLLER_BUTTON_X
    Y = pygame.CONTROLLER_BUTTON_Y

class GamepadController:
    def __init__(self, controller_id: int = 0):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > controller_id:
            self.controller = pygame.joystick.Joystick(controller_id)
            self.controller.init()
    
    def read_input(self) -> dict:
        pygame.event.pump()
        return {
            'buttons': {name: self.controller.get_button(btn) for name, btn in XboxButtons.__members__.items()},
            'axes': {
                'left_x': self.controller.get_axis(0),
                'left_y': self.controller.get_axis(1),
            }
        }
    
    async def send_signals(self, signals: List[Signal]):
        """发送手柄信号到Xbox"""
        pass
```

#### 3.4.2 键盘映射（P0）

**streaming实现参考**：

```csv
TapSeq,KeySeq
TAP_A,KEY_A
TAP_B,KEY_B
MOVE_UP,KEY_W
MOVE_DOWN,KEY_S
```

**Agent实现方案**：

```yaml
# configs/keybinding.yaml
keyboard_mapping:
  enabled: true
  preset: "xbox_controller"
  bindings:
    KEY_A: TAP_A
    KEY_B: TAP_B
    KEY_W: MOVE_FORWARD
    KEY_S: MOVE_BACKWARD
```

```python
# src/agent/input/keyboard_mapper.py
class KeyboardMapper:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
    
    def map_key_to_action(self, key: str) -> Optional[str]:
        """将键盘按键映射为Xbox手柄动作"""
        return self.config['bindings'].get(key)
```

#### 3.4.3 手柄信号发送（P0）

**streaming实现参考**：

```python
xsrp.WriteControllerData(username, signals)
```

**Agent实现方案**：

```python
# src/agent/input/controller_protocol.py
@dataclass
class GamepadSignal:
    buttons: int = 0
    left_trigger: int = 0
    right_trigger: int = 0
    left_thumbstick_x: int = 0
    left_thumbstick_y: int = 0
    right_thumbstick_x: int = 0
    right_thumbstick_y: int = 0

class ControllerProtocol:
    async def send_signals(self, signals: List[GamepadSignal]):
        """将手柄信号序列化为协议并发送"""
        # 序列化信号
        # 发送到Xbox流会话
        pass
```

### 3.5 验证清单

* [ ] 手柄读取测试

* [ ] 键盘映射测试

* [ ] 手柄发送测试

* [ ] 端到端控制测试

### 3.6 执行记录

| 日期 | 操作 | 结果 | 确认人 |
| -- | -- | -- | --- |
| -  | -  | -  | -   |

***

## 四、步骤四：自动操作Xbox主机

### 4.1 执行状态

| 项目        | 内容       |
| --------- | -------- |
| **状态**    | ✅ 已完成    |
| **前置步骤**  | 步骤三完成   |
| **预计工作量** | 7-10天     |
| **完成日期**  | 2026-05-30 |

### 4.2 实现内容

**参考streaming项目实现的功能**：

| 功能 | 实现状态 | 文件位置 |
|------|--------|---------|
| 场景识别器 | ✅ 已实现 | `src/agent/scene/game_automation_engine.py` |
| 模板管理器 | ✅ 已实现 | `src/agent/scene/scene_detector.py` |
| 账号切换器 | ✅ 已实现 | `src/agent/game/account_switcher.py` |
| 动作执行器 | ✅ 已实现 | `src/agent/scene/game_automation_engine.py` |
| 状态决策引擎 | ✅ 已实现 | `src/agent/scene/game_automation_engine.py` |
| 步骤四集成 | ✅ 已实现 | `src/agent/automation/step4_game_automation.py` |

### 4.3 新增/更新的文件

#### `src/agent/scene/game_automation_engine.py`
- `SceneState`: Xbox UI场景状态枚举
- `Action`: 动作数据类
- `ActionType`: 动作类型枚举
- `ActionExecutor`: 动作执行器
- `StateDecisionEngine`: 状态决策引擎
- `GameAutomationEngine`: 游戏自动化引擎

#### `src/agent/game/account_switcher.py`
- `AccountStatus`: 账号状态枚举
- `GameAccount`: 游戏账号数据类
- `AccountSwitchResult`: 账号切换结果
- `AccountSwitcher`: 游戏账号切换器

#### `src/agent/automation/step4_game_automation.py`
- `_init_game_automation()`: 初始化游戏自动化引擎
- 集成账号切换流程
- 集成场景识别和动作执行

### 4.4 待开发任务

#### 4.4.1 场景识别器（P0）

**streaming实现参考**：

```python
def recognize_scene(capture_mat, template):
    result = cv2.matchTemplate(capture_mat, template, cv.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    return max_val > threshold, max_val

schema = [
    2,      # 场景编号
    960,    # 显示宽度
    540,    # 显示高度
    1,      # 模板编号
    42,     # 左上X
    108,    # 左上Y
    90,     # 相似度阈值 (90%)
    3       # 算法编号
]
```

**Agent实现方案**：

```python
# src/agent/scene/scene_recognizer.py
class SceneRecognizer:
    def __init__(self, template_dir: str, threshold: float = 0.8):
        self.template_dir = template_dir
        self.threshold = threshold
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self):
        import cv2
        for template_file in Path(self.template_dir).glob("*.png"):
            scene_id = template_file.stem
            self.templates[scene_id] = cv2.imread(str(template_file))
    
    async def recognize(self, frame: np.ndarray) -> Tuple[str, float]:
        """识别场景"""
        import cv2
        best_match, best_score = None, 0.0
        
        for scene_id, template in self.templates.items():
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if max_val > best_score:
                best_score = max_val
                best_match = scene_id
        
        if best_score >= self.threshold:
            return best_match, best_score
        return None, 0.0
```

#### 4.4.2 模板管理（P0）

```python
# configs/scene_templates.yaml
scenes:
  MAIN_MENU:
    width: 1920
    height: 1080
    templates:
      - id: logo
        region: [100, 50, 300, 150]
        threshold: 0.85
    algorithm: TM_CCOEFF_NORMED
  
  MATCH_SEARCHING:
    templates:
      - id: searching
        region: [960, 540, 1100, 600]
        threshold: 0.80
  
  MATCH_PLAYING:
    templates:
      - id: timer
        region: [900, 50, 1020, 100]
        threshold: 0.85
```

#### 4.4.3 账号切换（P0）

**streaming实现参考**：

```python
def switch_account(account_id):
    # 1. 打开账号菜单
    # 2. 选择切换
    # 3. 输入账号密码
    # 4. 确认登录
```

**Agent实现方案**：

```python
# src/agent/game/account_switcher.py
class AccountSwitcher:
    def __init__(self, scene_recognizer: SceneRecognizer, 
                 controller: GamepadController):
        self.scene = scene_recognizer
        self.controller = controller
    
    async def switch_to(self, account: GameAccount) -> bool:
        """切换到指定账号"""
        # 1. 打开账号菜单
        await self._open_account_menu()
        
        # 2. 选择切换账号
        await self._select_switch_option()
        
        # 3. 选择目标账号或输入
        await self._select_or_input_account(account)
        
        # 4. 确认登录
        await self._confirm_login()
        
        # 5. 验证切换成功
        return await self._verify_login(account)
```

#### 4.4.4 比赛自动化（P0）

```python
# src/agent/game/match_automation.py
class MatchAutomation:
    def __init__(self, scene_recognizer, controller):
        self.scene = scene_recognizer
        self.controller = controller
    
    async def execute_match(self, config: MatchConfig) -> MatchResult:
        """执行一场比赛"""
        # 1. 进入比赛准备
        await self._enter_match_preparation()
        
        # 2. 等待匹配
        while True:
            scene, score = await self.scene.recognize()
            if scene == 'MATCH_SEARCHING':
                await asyncio.sleep(1)
            elif scene == 'MATCH_PLAYING':
                break
        
        # 3. 比赛进行中
        while True:
            scene, score = await self.scene.recognize()
            if scene == 'MATCH_END':
                break
            # 根据场景执行操作
            actions = self._decide_actions(scene)
            for action in actions:
                await self.controller.execute(action)
            await asyncio.sleep(0.1)
        
        # 4. 跳过结算
        await self._skip_settlement()
        
        return MatchResult(success=True)
```

### 4.5 验证清单

* [ ] 场景识别准确率测试

* [ ] 账号切换成功率测试

* [ ] 比赛自动化完成率测试

* [ ] 端到端流程测试

### 4.6 执行记录

| 日期 | 操作 | 结果 | 确认人 |
| -- | -- | -- | --- |
| -  | -  | -  | -   |

***

## 五、技术依赖关系

```
步骤一 ✅ → 步骤二 ⏳ → 步骤三 ⏳ → 步骤四 ⏳
   │           │            │            │
   │      Xbox发现      手柄控制      场景识别
   │      会话创建      渲染器       账号切换
   │      SDP握手       GPU解码      状态决策
```

***

## 六、附录

### 6.1 streaming项目文件对应

| streaming文件    | 功能   | Agent对应文件                     |
| -------------- | ---- | ----------------------------- |
| xsrp.py        | 串流核心 | `xbox/stream_controller.py`   |
| xsrpst.py      | 场景识别 | `scene/scene_recognizer.py`   |
| xsrputil.py    | 手柄控制 | `input/gamepad_controller.py` |
| accutil.py     | 账号管理 | `game/account_switcher.py`    |
| keybinding.csv | 键位映射 | `configs/keybinding.yaml`     |

### 6.2 技术替代方案

| C++技术               | Python替代             | 库              |
| ------------------- | -------------------- | -------------- |
| xsrpwrapper         | asyncio + websockets | Python原生       |
| SDL2 GameController | pygame               | pygame         |
| FFmpeg NVDEC        | imageio-ffmpeg       | imageio-ffmpeg |
| OpenCV              | cv2                  | opencv-python  |

