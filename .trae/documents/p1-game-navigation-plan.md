# P1 任务详细方案 - 游戏操作类型导航实现

## 一、概述

### 1.1 目标

为四种游戏操作类型实现完整的导航逻辑，包括：
- **拍卖行转会任务 (auction_transfer)**: 自动进行球员买入/卖出操作
- **SQB模式 (squad_battle)**: 与电脑AI对战的赛季模式
- **DR模式 (divisions_rivals)**: 与玩家线上对战的排位赛
- **周赛 (weekend_league)**: DR积分达标后可参加的周末联赛

### 1.2 当前状态

| 类型 | 当前状态 | 说明 |
|------|---------|------|
| `auction_transfer` | 仅打印日志 | 无实际导航 |
| `squad_battle` | 仅打印日志 | 复用现有比赛流程 |
| `divisions_rivals` | 仅打印日志 | 无实际导航 |
| `weekend_league` | 仅打印日志 | 无实际导航 |

---

## 二、整体架构设计

### 2.1 导航结构

```
_enter_match()
    │
    ├── _navigate_to_auction()      # 拍卖行转会
    ├── _navigate_to_squad_battle() # SQB模式
    ├── _navigate_to_dr()           # DR模式
    └── _navigate_to_weekend_league() # 周赛
```

### 2.2 代码结构变更

**文件**: `step4_game_automation.py`

新增函数：
```python
async def _navigate_to_game_mode(context, game_action_type, logger, game_logger)
async def _navigate_to_auction(context, logger, game_logger, operation_type='buy')
async def _navigate_to_squad_battle(context, logger, game_logger)
async def _navigate_to_dr(context, logger, game_logger)
async def _navigate_to_weekend_league(context, logger, game_logger)
async def _execute_auction_transfer(context, logger, game_logger, operation_type)
```

---

## 三、拍卖行转会任务 (auction_transfer)

### 3.1 业务流程

```
游戏主页
    │
    ├── 选择"Ultimate Team" (UT)
    │
    ├── 选择"Transfer Market" (转会市场)
    │       │
    │       ├── Buy: 搜索球员 → 出价 → 购买
    │       └── Sell: 我的球员 → 挂售 → 设置价格
    │
    └── 返回主页
```

### 3.2 菜单导航路径

| 步骤 | 操作 | 按钮位置 |
|------|------|---------|
| 1 | 从主页进入 UT | RB × 3 → A |
| 2 | 进入转会市场 | LB → A |
| 3a | 买入操作 | 选择球员 → 出价 → 确认 |
| 3b | 卖出操作 | 我的球员 → 选择 → 挂售 |

### 3.3 需要的新场景模板

| 场景ID | 模板名称 | 用途 |
|--------|---------|------|
| 50 | UT主菜单 | 检测UT菜单 |
| 51 | 转会市场入口 | 检测转会市场按钮 |
| 52 | 球员搜索结果 | 检测搜索结果 |
| 53 | 球员详情-买入 | 检测买入界面 |
| 54 | 球员详情-卖出 | 检测卖出界面 |

### 3.4 转会任务配置

```python
AUCTION_CONFIG = {
    'buy': {
        'min_price': 1000,      # 最低价格
        'max_price': 50000,     # 最高价格
        'max_bid_increase': 1000, # 最大出价增幅
        'retry_count': 3,
    },
    'sell': {
        'starting_price_ratio': 0.8,  # 起始价为市场价80%
        'buy_now_price_ratio': 1.0,   # 一口价为市场价100%
        'duration_minutes': 60,
    }
}
```

---

## 四、SQB模式 (squad_battle)

### 4.1 业务流程

```
游戏主页
    │
    ├── 选择"Ultimate Team" (UT)
    │
    ├── 选择"Home"或"Squad Battles"
    │       │
    │       ├── 选择难度(Harder/Ultimate)
    │       ├── 选择对手
    │       └── 开始比赛
    │
    └── 比赛结束后返回
```

### 4.2 菜单导航路径

| 步骤 | 操作 | 按钮位置 |
|------|------|---------|
| 1 | 从主页进入 UT | RB × 3 → A |
| 2 | 进入 Squad Battles | LB → A → 多次A |
| 3 | 选择难度 | 选择 "Harder" 或更高 |
| 4 | 选择对手 | 选择列表中的对手 |
| 5 | 开始比赛 | A |

### 4.3 需要的场景模板

| 场景ID | 模板名称 | 用途 |
|--------|---------|------|
| 55 | UT主菜单 | 检测UT菜单 |
| 56 | Squad Battles入口 | 检测SQB入口 |
| 57 | 难度选择 | 检测难度选择界面 |
| 58 | 对手选择 | 检测对手列表 |

### 4.4 SQB难度配置

```python
SQB_DIFFICULTY_MAP = {
    'easy': 'World Class',
    'normal': 'Professional',
    'hard': 'Harder',
    'ultimate': 'Ultimate',
}
```

---

## 五、DR模式 (divisions_rivals)

### 5.1 业务流程

```
游戏主页
    │
    ├── 选择"Ultimate Team" (UT)
    │
    ├── 选择"Division Rivals"
    │       │
    │       ├── 查看当前段位
    │       ├── 选择比赛类型(Skilling/Weekly Rewards)
    │       ├── 开始匹配
    │       └── 比赛结束
    │
    └── 返回主页
```

### 5.2 菜单导航路径

| 步骤 | 操作 | 按钮位置 |
|------|------|---------|
| 1 | 从主页进入 UT | RB × 3 → A |
| 2 | 进入 Division Rivals | LB × 2 → A |
| 3 | 选择"Play Champions"或"Play Skill Games" | A |
| 4 | 开始匹配 | A |
| 5 | 比赛结束后确认奖励 | A × 2 |

### 5.3 需要的场景模板

| 场景ID | 模板名称 | 用途 |
|--------|---------|------|
| 60 | UT主菜单 | 检测UT菜单 |
| 61 | Division Rivals入口 | 检测DR入口 |
| 62 | 段位信息 | 检测当前段位 |
| 63 | 匹配等待 | 检测匹配中 |
| 64 | 奖励确认 | 检测奖励界面 |

### 5.4 DR段位配置

```python
DR_DIVISION_MAP = {
    'champion': {'min_points': 2000, 'max_points': 9999},
    'elite': {'min_points': 1500, 'max_points': 1999},
    'gold': {'min_points': 1000, 'max_points': 1499},
    'silver': {'min_points': 500, 'max_points': 999},
    'bronze': {'min_points': 0, 'max_points': 499},
}
```

---

## 六、周赛 (weekend_league)

### 6.1 业务流程

```
周赛资格要求：DR段位达到Champion或Elite

游戏主页
    │
    ├── 选择"Ultimate Team" (UT)
    │
    ├── 选择"Weekend League" (需资格)
    │       │
    │       ├── 查看资格状态
    │       ├── 成功：进入周赛
    │       └── 失败：提示"无资格"
    │
    └── 比赛结束后确认奖励
```

### 6.2 菜单导航路径

| 步骤 | 操作 | 按钮位置 |
|------|------|---------|
| 1 | 从主页进入 UT | RB × 3 → A |
| 2 | 进入 Weekend League | LB × 3 → A |
| 3 | 检查资格 | 检测资格状态 |
| 4 | 有资格：开始匹配 | A |
| 5 | 无资格：返回并报错 | B |
| 6 | 比赛结束后确认奖励 | A × 2 |

### 6.3 需要的场景模板

| 场景ID | 模板名称 | 用途 |
|--------|---------|------|
| 70 | UT主菜单 | 检测UT菜单 |
| 71 | Weekend League入口 | 检测WL入口 |
| 72 | 资格确认-成功 | 检测有资格 |
| 73 | 资格确认-失败 | 检测无资格 |
| 74 | WL匹配等待 | 检测匹配中 |

### 6.4 周赛资格配置

```python
WEEKEND_LEAGUE_REQUIREMENTS = {
    'min_division': 'elite',  # 最低需要Elite段位
    'min_dr_points': 1500,
    'max_matches_per_day': 5,
    'total_matches': 10,
}
```

---

## 七、场景模板配置

### 7.1 新增模板清单

**文件**: `configs/scene_schemas.py`

```python
# === 拍卖行相关 (50-54) ===
[50, 960, 540, 1, 50, 100, 150, 200, 1, 48, 98, 152, 202, 90, 3],  # UT主菜单

# === SQB相关 (55-58) ===
[55, 960, 540, 1, 50, 100, 150, 200, 1, 48, 98, 152, 202, 90, 3],  # UT主菜单
[56, 960, 540, 1, 100, 200, 200, 300, 1, 98, 198, 202, 302, 90, 3], # Squad Battles入口

# === DR相关 (60-64) ===
[60, 960, 540, 1, 50, 100, 150, 200, 1, 48, 98, 152, 202, 90, 3],  # UT主菜单
[61, 960, 540, 1, 100, 200, 200, 300, 1, 98, 198, 202, 302, 90, 3], # Division Rivals入口

# === 周赛相关 (70-74) ===
[70, 960, 540, 1, 50, 100, 150, 200, 1, 48, 98, 152, 202, 90, 3],  # UT主菜单
[71, 960, 540, 1, 100, 200, 200, 300, 1, 98, 198, 202, 302, 90, 3], # Weekend League入口
```

### 7.2 模板目录

```
bend-agent/templates/
├── ... (现有模板)
├── 50.1.png  # UT主菜单
├── 51.1.png  # 转会市场入口
├── 56.1.png  # Squad Battles入口
├── 61.1.png  # Division Rivals入口
├── 71.1.png  # Weekend League入口
└── ... (其他模板)
```

---

## 八、代码实现详情

### 8.1 _apply_task_type() 重构

```python
def _apply_task_type(context: AgentTaskContext, game_account: GameAccountInfo, logger) -> None:
    """根据游戏操作类型应用不同配置"""
    game_action_type = _normalize_game_action_type(context.game_action_type)

    if game_action_type == 'auction_transfer':
        _apply_auction_config(game_account, logger)
    elif game_action_type == 'squad_battle':
        _apply_squad_battle_config(game_account, logger)
    elif game_action_type == 'divisions_rivals':
        _apply_dr_config(game_account, logger)
    elif game_action_type == 'weekend_league':
        _apply_weekend_league_config(game_account, logger)
```

### 8.2 导航函数实现

```python
async def _navigate_to_game_mode(context, game_action_type, logger, game_logger):
    """根据game_action_type导航到对应模式"""
    if game_action_type == 'auction_transfer':
        await _navigate_to_auction(context, logger, game_logger)
    elif game_action_type == 'squad_battle':
        await _navigate_to_squad_battle(context, logger, game_logger)
    elif game_action_type == 'divisions_rivals':
        await _navigate_to_dr(context, logger, game_logger)
    elif game_action_type == 'weekend_league':
        await _navigate_to_weekend_league(context, logger, game_logger)
```

### 8.3 _enter_match() 修改

```python
async def _enter_match(context, game_account, logger, game_logger, report_progress):
    """进入比赛准备，根据game_action_type导航到对应模式"""
    logger.info(f"进入比赛准备: {game_account.gamertag}")

    # 先检测主菜单
    screen_detected = await _detect_screen_state(context, "MAIN_MENU", logger, game_logger)

    # 根据game_action_type导航
    await _navigate_to_game_mode(
        context,
        _normalize_game_action_type(context.game_action_type),
        logger,
        game_logger
    )

    await report_progress(context.task_id, "STEP4", "GAME_PREPARING", ...)
```

---

## 九、任务拆解

### P1.1 - 基础架构

| 序号 | 任务 | 涉及文件 | 工作量 |
|------|------|---------|--------|
| 1 | 创建导航分发函数 `_navigate_to_game_mode()` | `step4_game_automation.py` | 小 |
| 2 | 创建各模式导航骨架函数 | `step4_game_automation.py` | 小 |
| 3 | 更新 `_enter_match()` 调用导航分发 | `step4_game_automation.py` | 小 |

### P1.2 - 拍卖行功能

| 序号 | 任务 | 涉及文件 | 工作量 |
|------|------|---------|--------|
| 4 | 添加场景模板 50-54 | `scene_schemas.py`, `templates/` | 中 |
| 5 | 实现 `_navigate_to_auction()` | `step4_game_automation.py` | 中 |
| 6 | 实现 `_execute_auction_transfer()` | `step4_game_automation.py` | 大 |
| 7 | 添加拍卖配置 `AUCTION_CONFIG` | `step4_game_automation.py` | 小 |

### P1.3 - SQB功能

| 序号 | 任务 | 涉及文件 | 工作量 |
|------|------|---------|--------|
| 8 | 添加场景模板 55-58 | `scene_schemas.py`, `templates/` | 中 |
| 9 | 实现 `_navigate_to_squad_battle()` | `step4_game_automation.py` | 中 |
| 10 | 复用现有 `_play_match()` | 已有 | - |

### P1.4 - DR功能

| 序号 | 任务 | 涉及文件 | 工作量 |
|------|------|---------|--------|
| 11 | 添加场景模板 60-64 | `scene_schemas.py`, `templates/` | 中 |
| 12 | 实现 `_navigate_to_dr()` | `step4_game_automation.py` | 中 |
| 13 | 添加段位配置 `DR_DIVISION_MAP` | `step4_game_automation.py` | 小 |

### P1.5 - 周赛功能

| 序号 | 任务 | 涉及文件 | 工作量 |
|------|------|---------|--------|
| 14 | 添加场景模板 70-74 | `scene_schemas.py`, `templates/` | 中 |
| 15 | 实现 `_navigate_to_weekend_league()` | `step4_game_automation.py` | 中 |
| 16 | 添加资格检查逻辑 | `step4_game_automation.py` | 中 |

---

## 十、验证步骤

### 10.1 单元测试

| 测试项 | 验证内容 |
|--------|---------|
| 导航分发 | 根据不同 game_action_type 调用正确导航函数 |
| 场景检测 | 各场景模板能正确识别 |
| 资格检查 | 周赛资格判断逻辑正确 |

### 10.2 集成测试

| 测试项 | 验证内容 |
|--------|---------|
| 拍卖行任务 | 能正确导航到转会市场并执行买入/卖出 |
| SQB任务 | 能正确导航到SQB并完成比赛 |
| DR任务 | 能正确导航到DR并完成比赛 |
| 周赛任务 | 能检测资格并正确导航 |

### 10.3 端到端测试

```
1. 启动后端服务
2. 创建任务传入 gameActionType=auction_transfer
3. 部署 Agent 服务
4. 观察 Agent 是否正确进入转会市场
```

---

## 十一、风险与注意事项

| 风险 | 缓解措施 |
|------|---------|
| 游戏UI变更 | 场景模板设计为可配置，发现失效模板可快速替换 |
| 导航超时 | 设置合理的超时时间(30s)，超时后重试或跳过 |
| 资格检测失败 | 周赛资格检测增加备用方案(基于DR积分) |
| 模板匹配不稳定 | 降低相似度阈值到85%，或使用多模板投票 |

---

## 十二、依赖关系

```
P1.1 (基础架构)
    │
    ├── P1.2 (拍卖行) - 可独立
    ├── P1.3 (SQB) - 依赖 P1.1
    ├── P1.4 (DR) - 依赖 P1.1
    └── P1.5 (周赛) - 依赖 P1.1
```

---

*文档版本: 1.0*
*创建日期: 2026-06-04*
