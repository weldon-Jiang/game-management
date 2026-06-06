# 自动化任务优化方案 - 游戏任务类型扩展

## 一、需求分析

### 1.1 当前问题

| 字段                | 位置                            | 当前值                 | 问题            |
| ----------------- | ----------------------------- | ------------------- | ------------- |
| `type` (taskType) | Task / StartAutomationRequest | 固定 `stream_control` | **无实际作用，应删除** |
| `gameActionType`  | Task / StartAutomationRequest | `daily_match` 等     | **实际使用的类型字段** |

### 1.2 简化方案

**删除** **`type`/`taskType`，直接用** **`gameActionType`** **替换**

### 1.3 新的 gameActionType 类型

| 枚举值 | code | 说明 | visible |
|--------|------|------|---------|
| AUCTION_TRANSFER | `auction_transfer` | 拍卖行转会任务 | true |
| SQUAD_BATTLE | `squad_battle` | SQB模式（与电脑AI对战） | true |
| DIVISIONS_RIVALS | `divisions_rivals` | DR模式（与玩家线上对战） | false |
| WEEKEND_LEAGUE | `weekend_league` | 周赛（DR积分达标后可参加） | false |

> 前端枚举添加 `visible` 字段控制下拉展示，仅 `visible=true` 的选项显示

### 1.3 第一步目标（当前迭代）

实现 **拍卖行转会任务 + SQB游戏模式**，验证整体流程。

***

## 二、方案设计

### 2.1 后端 GameActionType 枚举（替换）

**文件**: `bend-platform/src/main/java/com/bend/platform/enums/GameActionType.java`

```java
public enum GameActionType {
    AUCTION_TRANSFER("auction_transfer", "拍卖行转会"),
    SQUAD_BATTLE("squad_battle", "SQB模式"),
    DIVISIONS_RIVALS("divisions_rivals", "DR模式"),
    WEEKEND_LEAGUE("weekend_league", "周赛");
}
```

### 2.2 Agent端 VALID\_TASK\_TYPES（硬编码）

**文件**: `bend-agent/src/agent/automation/step4_game_automation.py`

```python
VALID_TASK_TYPES = frozenset({
    'auction_transfer', 'squad_battle', 'divisions_rivals', 'weekend_league'
})
```

### 2.3 重构 \_apply\_task\_type()

```python
def _apply_task_type(context, game_account, logger):
    game_action_type = _normalize_game_action_type(context.game_action_type)

    if game_action_type == 'auction_transfer':
        _apply_auction_transfer_task(context, game_account, logger)
    elif game_action_type == 'squad_battle':
        _apply_squad_battle_task(context, game_account, logger)
    elif game_action_type == 'divisions_rivals':
        _apply_dr_task(context, game_account, logger)
    elif game_action_type == 'weekend_league':
        _apply_weekend_league_task(context, game_account, logger)
    else:
        logger.warning(f"未知游戏操作类型: {game_action_type}，默认使用SQB模式")
        _apply_squad_battle_task(context, game_account, logger)
```

***

## 三、任务拆解

### P0 - 核心改造

| 序号 | 任务                                           | 涉及文件                            | 工作量 |
| -- | -------------------------------------------- | ------------------------------- | --- |
| 1  | 替换 GameActionType 枚举为4种新类型                   | `GameActionType.java`           | 小   |
| 2  | 后端 TaskController 添加获取 gameActionType 列表接口   | `TaskController.java`           | 小   |
| 3  | 删除后端 StartAutomationRequest.taskType 字段      | `StartAutomationRequest.java`   | 小   |
| 4  | 删除前端启动自动化 taskType 相关代码                      | `StreamingAccountList.vue`      | 小   |
| 5  | 前端启动自动化添加 gameActionType 下拉选择                | `StreamingAccountList.vue`      | 小   |
| 6  | 前端 constants.js 添加 GAME\_ACTION\_TYPE\_MAP   | `constants.js`                  | 小   |
| 7  | 前端任务列表显示 gameActionType                      | `TaskList.vue`                  | 小   |
| 8  | Agent字段名统一 (task\_type → game\_action\_type) | `task_context.py`, `step4_*.py` | 小   |
| 9  | 更新 step4 VALID\_TASK\_TYPES                  | `step4_game_automation.py`      | 小   |
| 10 | 重构 \_apply\_task\_type()                     | `step4_game_automation.py`      | 中   |
| 11 | 实现 SQB 模式导航逻辑                                | `step4_game_automation.py`      | 大   |

### P1 - 后续扩展

| 序号 | 任务          | 说明 |
| -- | ----------- | -- |
| 12 | 实现拍卖行转会任务导航 | 大  |
| 13 | 实现 DR 模式导航  | 大  |
| 14 | 实现周赛导航      | 中  |

***

## 四、关键设计决策

### 4.1 类型传递链路

```
前端选择 gameActionType
    ↓
StartAutomationRequest.gameActionType
    ↓
Task.gameActionType
    ↓
WebSocket 消息 params.gameActionType
    ↓
Agent: params.get('gameActionType')
    ↓
context.game_action_type
    ↓
step4._apply_task_type(context.game_action_type)
```

### 4.2 类型字段说明

| 字段               | 说明             | 值                                                                           |
| ---------------- | -------------- | --------------------------------------------------------------------------- |
| ~~`taskType`~~   | **已删除**        | -                                                                           |
| `gameActionType` | 游戏操作类型（唯一类型字段） | `auction_transfer` / `squad_battle` / `divisions_rivals` / `weekend_league` |

### 4.3 场景检测依赖

SQB 模式需要新增场景模板（参考现有 Streaming 场景检测器架构）：

* 模板目录: `bend-agent/templates/`

* 配置文件: `bend-agent/configs/scene_schemas.py`

***

## 五、验证步骤

1. 启动后端服务，调用创建任务接口传入 `gameActionType=squad_battle`
2. 部署 Agent 服务，验证日志中 `game_action_type` 正确
3. 端到端验证：观察 Agent 是否正确导航到 SQB 模式

***

## 六、风险与注意事项

| 风险     | 缓解措施              |
| ------ | ----------------- |
| 场景模板缺失 | 先用基础场景检测，逐步添加模板   |
| 游戏UI变更 | 场景检测器设计为可配置       |
| 任务取消处理 | 确保各种任务类型都正确处理取消信号 |

