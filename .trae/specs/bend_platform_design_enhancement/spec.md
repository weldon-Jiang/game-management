# bend_platform_design.md 完善计划规格书

## 一、目的

完善 `bend_platform_design.md`，补充缺失的 Python Agent 架构、场景智能匹配系统、手柄自动化、前端 Vue 组件详细设计，使其成为可直接落地开发的完整需求方案。

## 二、现状评估

**已有内容（完整度约 70%）：**

| 章节 | 内容 | 状态 |
|------|------|------|
| 第一章 | 项目概述与架构图 | ✅ 完整 |
| 第二章 | 技术栈 | ✅ 完整 |
| 第三章 | 串流系统架构（xStreamingPlayer） | ✅ 完整 |
| 第四章 | 数据库设计 | ✅ 完整 |
| 第五章 | 后端 API 设计 | ✅ 完整 |
| 第六章 | 登录认证、商户管理 | ✅ 完整 |
| 第六章 6.8-6.12 | 模板管理、游戏账号切换、暂停恢复、视频流 | ✅ 完整 |
| 第七章 | WebSocket 实时通信 | ✅ 完整 |
| 第八章 | 前端页面设计 | ⚠️ 部分完整 |
| 第九章 | 与自动化项目集成 | ✅ 完整 |

**缺失内容（需补充约 30%）：**

| 缺失内容 | 说明 | 优先级 |
|---------|------|--------|
| **Python Agent 核心架构** | CentralManager、StreamWindow、VideoFrameCapture | P0 |
| **场景智能匹配系统** | SceneBasedMatcher、HybridMatcher、OCRTextMatcher | P0 |
| **手柄操作自动化** | GamepadButton、界面检测循环 | P1 |
| **前端 Vue 组件详细设计** | 组件 props、events、状态管理详细设计 | P1 |

## 三、需要整合的设计文档

| 文档 | 主要内容 | 整合位置 |
|------|---------|---------|
| `multi_window_automation_complete_design.md` | Python Agent 架构、场景匹配、游戏账号轮询 | 新增第七章后部分 |
| `multi_window_stream_design.md` | Electron 窗口管理、视频帧捕获 | 新增第七章 |
| `login_auth_fix_plan.md` | 登录自动化错误处理 | 补充第六章 |
| `ttt_reference_analysis.md` | 状态机模式、OCR方案 | 新增第八章 |
| `游戏手柄操作自动化计划.md` | 手柄操作自动化 | 新增第九章 |

## 四、完善后的文档结构

```
bend_platform_design.md (完善后)
├── 第一章 项目概述与架构 (保持不变)
├── 第二章 技术栈 (保持不变)
├── 第三章 串流系统架构 (保持不变)
├── 第四章 数据库设计 (保持不变)
├── 第五章 后端 API 设计 (保持不变)
├── 第六章 登录认证与商户管理
│   ├── 6.1-6.7 商户登录认证 (保持不变)
│   ├── 6.8 模板更新机制 (保持不变)
│   ├── 6.9 游戏账号切换 (保持不变)
│   ├── 6.10 暂停恢复 (保持不变)
│   ├── 6.11 视频流 (保持不变)
│   └── 6.12 登录自动化补充 (新增 - login_auth_fix_plan.md)
│       ├── 登录流程状态机
│       ├── 错误处理与重试机制
│       └── 关键代码示例
├── 第七章 Python Agent 架构 (新增 - multi_window_automation_complete_design.md)
│   ├── 7.1 CentralManager 中央管理器
│   ├── 7.2 StreamWindow 串流窗口
│   ├── 7.3 VideoFrameCapture 视频帧捕获
│   ├── 7.4 InputController 输入控制器
│   ├── 7.5 窗口拖拽与最小化
│   ├── 7.6 归一化坐标系统
│   ├── 7.7 异常恢复机制
│   └── 7.8 CentralManager 与后端交互
├── 第八章 场景智能匹配系统 (新增)
│   ├── 8.1 SceneBasedMatcher 场景匹配器
│   ├── 8.2 HybridMatcher 综合匹配器
│   ├── 8.3 OCRTextMatcher 文字识别
│   ├── 8.4 场景配置与性能对比
│   └── 8.5 Xbox UI 常用文字目标
├── 第九章 手柄操作自动化 (新增 - 游戏手柄操作自动化计划.md)
│   ├── 9.1 GamepadButton 枚举定义
│   ├── 9.2 手柄操作方法
│   └── 9.3 界面检测循环
├── 第十章 游戏账号管理与轮询 (整合 - multi_window_automation_complete_design.md)
│   ├── 10.1 GameAccountRotationService
│   ├── 10.2 Xbox 账号切换流程
│   ├── 10.3 比赛次数限制
│   └── 10.4 每日重置逻辑
├── 第十一章 WebSocket 实时通信 (保持不变)
├── 第十二章 前端页面设计 (补充完善 - Vue 3)
│   ├── 12.1 前端技术栈与组件
│   ├── 12.2 核心组件结构
│   ├── 12.3 状态管理方案
│   └── 12.4 WebSocket 封装
└── 第十三章 与自动化项目集成 (补充完善)
    ├── 13.1 模板管理系统
    ├── 13.2 Xbox 变动检测
    └── 13.3 商户数据隔离
```

## 五、新增章节详细内容要点

### 5.1 第七章 Python Agent 架构

**来源**: multi_window_automation_complete_design.md

**核心类设计**:
```python
# CentralManager - 中央管理器
class CentralManager:
    windows: Dict[str, StreamWindow]  # instance_id -> StreamWindow

    async def register_to_backend()
    async def start_streaming_account() -> str  # 返回 instance_id
    async def stop_instance()

# StreamWindow - 串流窗口
class StreamWindow:
    state: WindowState  # INITIALIZING → READY → CONNECTING → CONNECTED → AUTOMATING
    frame_capture: VideoFrameCapture
    template_matcher: TemplateMatcher
    input_controller: InputController

# VideoFrameCapture - 视频帧捕获
class VideoFrameCapture:
    capture_frame() -> np.ndarray  # 返回 BGR 格式
    get_coordinate_transform() -> CoordinateTransform  # 处理黑边
```

### 5.2 第八章 场景智能匹配系统

**来源**: multi_window_automation_complete_design.md + ttt_reference_analysis.md

**场景枚举**:
```python
class Scene(Enum):
    COMPETITION = "competition"  # 比赛 - 只用模板 (<20ms)
    GAMING = "gaming"            # 游戏 - 只用模板 (<20ms)
    LOGIN = "login"              # 登录 - 模板优先+OCR fallback
    MENU = "menu"                # 菜单 - 模板优先+OCR fallback
    SETTINGS = "settings"         # 设置 - OCR 优先
    ACCOUNT = "account"           # 账号 - OCR 优先
    STREAMING = "streaming"       # 串流 - 模板优先+OCR
    GENERAL = "general"           # 通用 - 模板优先+OCR
```

### 5.3 第九章 手柄操作自动化

**来源**: 游戏手柄操作自动化计划.md

**枚举定义**:
```python
class GamepadButton(Enum):
    A = 0
    B = 1
    X = 2
    Y = 3
    LB = 4
    RB = 5
    LT = 6
    RT = 7
    BACK = 8
    START = 9
    L3 = 10
    R3 = 11
    DPAD_UP = 12
    DPAD_DOWN = 13
    DPAD_LEFT = 14
    DPAD_RIGHT = 15
```

### 5.4 第十二章 前端 Vue 组件设计

**技术栈**: Vue 3 + Composition API + Element Plus + Pinia + Vue Router 4

**核心组件详细设计**:
- VideoMonitor.vue - 视频监控组件 (props: instanceId, agentHost; events: onConnect, onDisconnect)
- LogViewer.vue - 日志查看器 (支持 DEBUG/INFO/WARN/ERROR 筛选)
- RealtimeChart.vue - 实时图表 (使用 ECharts)

## 六、文档完善质量标准

1. **完整性**: 所有关键模块都有详细设计
2. **可执行性**: 代码示例可直接参考实现
3. **一致性**: 术语、命名、格式统一
4. **可追踪性**: 每个设计点可追溯到需求来源

## 七、输出文件

完善后的文档输出到: `d:\auto-xbox\team-management\.trae\documents\bend_platform_design.md`
