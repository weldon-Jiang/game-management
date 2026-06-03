
# Streaming项目 vs Agent项目 功能对比分析

## 概述

本文档对比分析 `streaming` 项目（原始项目）与 `bend-agent` 项目（重构项目）的功能差异，识别 Agent 项目缺少的关键功能模块。

---

## 一、项目结构对比

### Streaming项目
```
streaming/
├── xsrpst.py              # 核心场景检测和模板配置
├── xsrputil.py            # 控制器和工具类
├── payload.py             # 数据模型和协议
├── xsrp.py                # 主程序和状态机
├── xsplayer.py            # 播放器
├── accutil.py             # 账户工具
├── logutil.py             # 日志工具
└── template/              # 模板图片目录
    ├── 1.1.png, 2.1.png, ...
    └── templates.dat      # 序列化模板数据
```

### Bend-Agent项目
```
bend-agent/
├── src/agent/
│   ├── automation/        # 4步自动化框架
│   ├── scene/             # 场景检测
│   ├── vision/            # 视觉处理
│   ├── input/             # 输入控制
│   ├── xbox/              # Xbox连接
│   ├── game/              # 游戏管理
│   ├── api/               # API通信
│   └── task/              # 任务管理
├── configs/
│   ├── scene_schemas.py   # 场景配置
│   └── football_scenes.py # 足球场景配置
├── templates/             # 模板目录（需要创建）
└── docs/                  # 文档
```

---

## 二、核心功能对比表

| 功能模块 | Streaming项目 | Bend-Agent项目 | 差异说明 |
|---------|--------------|---------------|---------|
| **场景检测** | ✅ 完整实现 | ✅ 部分实现 | Agent缺少游戏特定场景 |
| **模板管理** | ✅ 支持序列化 | ✅ 基础实现 | Agent缺少模板优化 |
| **状态机** | ✅ Graph类实现 | ✅ GameAutomationEngine | Agent缺少完整状态图 |
| **游戏场景** | ✅ FUT菜单、比赛场景 | ❌ 缺失 | **关键缺失** |
| **小地图识别** | ❌ 无 | ❌ 无 | 双方都缺少 |
| **控制器** | ✅ XsrpController | ✅ FootballController | 功能对等 |
| **帧捕获** | ✅ 完整实现 | ✅ GPU优化 | Agent更优 |
| **任务管理** | ❌ 无 | ✅ 完整框架 | Agent更优 |
| **平台集成** | ❌ 无 | ✅ WebSocket API | Agent更优 |

---

## 三、Streaming项目独有功能分析

### 1. 完整的场景模板配置 (xsrpst.py)

#### 场景ID映射表
```
UI导航场景 (1-9)
├── 1: 刚串流上的主页界面
├── 2: 西瓜主页界面
├── 3: 档案和系统页面
├── 4: 注销页面
├── 5: 你是谁页面
├── 6: 选择用户
├── 7: 关机/重启页面
├── 8: 关闭主机
└── 9: 重启系统

登录场景 (10-33)
├── 10: XB账号登录页面
├── 11-33: 小键盘按键 (0-9, a-z, 符号)

游戏场景 (100+)
├── 100: GAME NEWS
├── 101-110: FUT主菜单
├── 200-235: FUT子菜单
├── 1002-1035: 游戏中场景
├── 1100-1108: 队伍管理
├── 1200-1206: 分区比赛
└── ...更多游戏场景
```

#### 每个场景的配置格式
```python
[
    场景ID,
    宽度(960),
    高度(540),
    模板ID,
    模板左X,
    模板顶Y,
    模板右X,
    模板底Y,
    搜索区ID,
    搜索区左X,
    搜索区顶Y,
    搜索区右X,
    搜索区底Y,
    相似度(90),
    算法ID(3=TM_CCORR_NORMED)
]
```

### 2. 完整的状态机系统 (xsrp.py)

#### Graph类定义的状态
```python
SCENE_ID_UNKNOWN = -1

# 游戏菜单场景
SCENE_ID_GAME_NEWS = 100
SCENE_ID_GAME_ULTIMATE_TEAM = 101
SCENE_ID_GAME_TRAIN = 102
SCENE_ID_GAME_CAREER_MANAGER = 103
SCENE_ID_GAME_CAREER_PLAYER = 104
SCENE_ID_GAME_CLUB = 105
SCENE_ID_GAME_PLAY_OFF = 106
SCENE_ID_GAME_SEASON = 107
SCENE_ID_GAME_TOURNAMENT = 108
SCENE_ID_GAME_COOPERATIVE = 109
SCENE_ID_GAME_FRIEND_ONLINE = 110

# FUT菜单场景
SCENE_ID_FUT_MAIN = 200
SCENE_ID_FUT_OBJECTIVE = 201
SCENE_ID_FUT_PLAY = 202
SCENE_ID_FUT_CLUB = 203
SCENE_ID_FUT_STORE = 204
SCENE_ID_FUT_OFFLINE = 205

# FUT子菜单
SCENE_ID_FUT_PLAY_SWITCH = 210
SCENE_ID_FUT_PLAY_AI_SQUAD_BATTLE = 220
SCENE_ID_FUT_PLAY_AI_TIMES = 221
SCENE_ID_FUT_PLAY_AI_SINGLE_DRAFT = 222
SCENE_ID_FUT_PLAY_ARENA_RUSH = 230
SCENE_ID_FUT_PLAY_ARENA_RIVALS = 231
SCENE_ID_FUT_PLAY_ARENA_CHALLENGE = 232
SCENE_ID_FUT_PLAY_ARENA_CHAMPION = 233
SCENE_ID_FUT_PLAY_ARENA_ULTIMATE = 234
SCENE_ID_FUT_PLAY_ARENA_ONLINE_DRAFT = 235

# 游戏中场景
SCENE_ID_HOLD_SKIP = 1002
SCENE_ID_SOCIAL = 1004
SCENE_ID_SIDE_SELECT = 1005
SCENE_ID_HOME_AWAY_SELECT = 1006
SCENE_ID_KIT_HOME_HOME = 1007
SCENE_ID_KIT_HOME_AWAY = 1008
SCENE_ID_KIT_AWAY_HOME = 1009
SCENE_ID_KIT_AWAY_AWAY = 1010
SCENE_ID_KIT_SWITCH = 1011
SCENE_ID_GAME_RESUME = 1014
SCENE_ID_GAME_COINS = 1015
SCENE_ID_GAME_STATS = 1016
SCENE_ID_GAME_KICK_GOAL = 1017
SCENE_ID_GAME_KICK_CORNER = 1018
SCENE_ID_GAME_KICK_FREE = 1019
SCENE_ID_GAME_KICK_BORDER = 1020
SCENE_ID_GAME_HYPERMOTION = 1021
SCENE_ID_GAME_PENALTY_SHOOT = 1022
SCENE_ID_GAME_PENALTY_SAVE = 1023
SCENE_ID_GAME_PENALTY_ENTRY = 1024
SCENE_ID_GAME_REFEREE_VIEW = 1025
SCENE_ID_GAME_ABANDON = 1026
SCENE_ID_GAME_COACH = 1027
SCENE_ID_GAME_ASSIST = 1028
SCENE_ID_GAME_SETTINGS = 1029
SCENE_ID_GAME_HIGHLIGHT = 1030
SCENE_ID_GAME_PLAYER_PERFORMANCE = 1031
SCENE_ID_GAME_MANAGE_SQUAD = 1032
SCENE_ID_GAME_MANAGE_TACTICS = 1033
SCENE_ID_GAME_MANAGE_ROLE = 1034
SCENE_ID_GAME_PROFILE = 1035

# 队伍管理场景
SCENE_ID_SQUAD_ENTRY = 1100
SCENE_ID_SQUAD_OK = 1101
SCENE_ID_SQUAD_FAIL = 1102
SCENE_ID_SQUAD_PLAYER_MOVE = 1103
SCENE_ID_SQUAD_PLAYER_LOCATED = 1104
SCENE_ID_SQUAD_PLAYER_SELECTED = 1105
SCENE_ID_SQUAD_PLAYER_OPTIONS = 1106
SCENE_ID_SQUAD_PLAYER_ADD = 1107
SCENE_ID_SQUAD_PLAYER_CLUB = 1108

# 分区比赛场景
SCENE_ID_DIVISION_RIVAL_PROGRESS = 1200
SCENE_ID_DIVISION_RIVAL_SEARCH = 1201
SCENE_ID_DIVISION_RIVAL_INIT = 1202
SCENE_ID_DIVISION_RIVAL_KIT = 1203
SCENE_ID_DIVISION_RIVAL_WAIT = 1204
SCENE_ID_DIVISION_RIVAL_PLAY = 1205
SCENE_ID_DIVISION_RIVAL_RESUME = 1206
```

### 3. 完整的XsrpController (xsrputil.py)

```python
class XsrpController:
    TAP_SEQ = "TapSeq"
    TAP_A = 0
    TAP_B = 1
    TAP_X = 2
    TAP_Y = 3
    TAP_UP = 4
    TAP_DOWN = 5
    TAP_LEFT = 6
    TAP_RIGHT = 7
    TAP_XB = 8
    TAP_SHARE = 9
    TAP_MENU = 10
    TAP_L1 = 11
    TAP_L2 = 12
    TAP_R1 = 13
    TAP_R2 = 14
    TAP_LS = 15
    TAP_RS = 16
    TAP_LS_MOVE = 17
    TAP_RS_MOVE = 18
    TAP_LS_DIRECTION = 19
    TAP_RS_DIRECTION = 20
    
    AXIS_RANGE_MIN = -32768
    AXIS_RANGE_MAX = 32767
    TRIGGER_RANGE_MIN = 0
    TRIGGER_RANGE_MAX = 32767
    
    @staticmethod
    def TapController(id: int, taps: list):
        """创建控制器输入"""
        
    @staticmethod
    def InitTaps():
        """初始化taps列表"""
        
    @staticmethod
    def Clone(controller):
        """克隆控制器"""
```

### 4. 模板序列化加载 (xsrpst.py)

```python
def generate_templates():
    """生成模板文件"""
    
def recognize_scenes():
    """识别场景"""
    
def run_diagram():
    """运行状态图"""
```

---

## 四、Agent项目现有功能

### 1. 已实现模块

| 模块 | 文件 | 状态 |
|-----|-----|-----|
| Streaming场景检测器 | `scene/streaming_scene_detector.py` | ✅ 完成 |
| 模板管理器 | `vision/template_manager.py` | ✅ 完成 |
| 场景-动作映射器 | `scene/scene_action_mapper.py` | ✅ 完成 |
| 足球控制器 | `input/football_controller.py` | ✅ 完成 |
| 4步自动化框架 | `automation/step*.py` | ✅ 完成 |
| 游戏自动化引擎 | `scene/game_automation_engine.py` | ✅ 基础 |
| 异步任务管理 | `task/automation_scheduler.py` | ✅ 完成 |

### 2. 现有配置

- `scene_schemas.py`: UI导航场景（1-33）
- `football_scenes.py`: 足球比赛场景（100+）- 仅有占位符
- `football_actions.yaml`: 足球动作配置

---

## 五、Agent项目关键缺失功能

### 🎯 高优先级（必须实现）

#### 1. 完整的游戏场景模板配置
**问题**：Agent缺少游戏中场景（100-1206）的模板配置

**需要补充**：
```python
# configs/full_scene_schemas.py
# 补充从100开始的所有游戏场景配置

# 示例：
schema = [
    100,    # SCENE_ID_GAME_NEWS
    960,
    540,
    1,      # 模板ID
    100,    # 模板区域
    100,
    200,
    150,
    1,      # 搜索区ID
    90,     # 搜索区
    90,
    210,
    160,
    90,     # 相似度
    3       # 算法
]
```

#### 2. 完整的场景-动作映射系统
**问题**：缺少对应游戏场景的自动化操作

**需要实现**：
```python
# configs/scene_action_map.yaml

scene_100:  # GAME NEWS
  actions:
    - wait: 2
    - navigate: ['DOWN', 'DOWN', 'A']

scene_202:  # FUT PLAY
  actions:
    - navigate: ['DOWN', 'DOWN', 'DOWN', 'A']

scene_220:  # SQUAD BATTLE
  actions:
    - navigate: ['A']
    
scene_1200:  # DIVISION RIVAL PROGRESS
  actions:
    - navigate: ['DOWN', 'A']
```

#### 3. 模板图片资源
**问题**：缺少实际的模板图片文件

**需要**：
```
templates/
├── 1.1.png
├── 2.1.png
...
├── 100.1.png  # GAME NEWS
├── 200.1.png  # FUT MAIN
├── 202.1.png  # FUT PLAY
...
└── templates.dat  # 序列化数据
```

#### 4. 模板序列化优化
**问题**：当前TemplateManager缺少完整的序列化功能

**需要优化**：
- 完善 `save_serialized()`
- 完善 `load_serialized()`
- 添加性能优化

### ⚡ 中优先级（建议实现）

#### 5. 小地图识别（新增功能）
```
功能需求：
- 检测小地图区域
- 识别我方球员位置
- 识别对方球员位置
- 识别足球位置
- 识别当前控制球员

技术方案：
- 颜色分割
- 形状识别
- 位置跟踪
```

#### 6. 高级足球比赛策略
```
功能需求：
- 基于场景的智能决策
- 进攻策略
- 防守策略
- 传球策略
- 射门策略

配置文件：
configs/football_strategy.yaml
```

#### 7. 更完善的状态机系统
```
需要改进 GameAutomationEngine：
- 添加所有游戏场景的状态转换
- 添加完整的状态转换规则
- 添加错误处理和回退策略
```

### 📊 低优先级（可选增强）

#### 8. 性能优化
```
- 模板预加载优化
- 多线程/多进程场景检测
- GPU加速的模板匹配
- 缓存策略优化
```

#### 9. 调试和可视化工具
```
- 场景检测可视化
- 动作执行日志
- 性能分析工具
- 模板管理工具
```

---

## 六、功能实现优先级路线图

### Phase 1: 基础游戏功能（1-2周）
- [ ] 补充完整的游戏场景配置（100-1206）
- [ ] 创建场景-动作映射配置
- [ ] 收集/创建模板图片
- [ ] 完善模板序列化功能
- [ ] 测试基础游戏流程

### Phase 2: 足球自动化（2-3周）
- [ ] 实现完整的比赛流程自动化
- [ ] 添加足球比赛策略
- [ ] 实现场景检测回调
- [ ] 测试完整比赛流程

### Phase 3: 高级功能（3-4周）
- [ ] 实现小地图识别
- [ ] 添加智能决策系统
- [ ] 性能优化
- [ ] 调试工具

---

## 七、总结

### 核心结论

1. **Agent项目架构更优**：异步、模块化、平台集成
2. **Streaming项目场景更完整**：有完整的游戏场景配置
3. **关键缺失**：游戏特定场景、状态机图、完整模板库

### 建议策略

**短期**：
1. 从Streaming项目移植场景配置
2. 收集/创建模板图片
3. 补充场景-动作映射

**中期**：
1. 完善GameAutomationEngine
2. 实现完整的游戏流程
3. 添加小地图识别

**长期**：
1. AI增强的足球策略
2. 性能优化
3. 更多游戏支持

---

*文档版本: 1.0*  
*最后更新: 2026-06-03*

