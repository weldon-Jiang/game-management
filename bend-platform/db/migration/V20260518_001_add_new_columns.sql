-- 添加新字段的迁移脚本
-- 2026-05-18

-- 1. 任务表添加游戏操作类型字段
ALTER TABLE task ADD COLUMN game_action_type VARCHAR(50) DEFAULT 'daily_match' COMMENT '游戏操作类型 daily_match-每日比赛 training-训练模式 mission-任务挑战 custom-自定义操作';

-- 2. 游戏账号表添加状态字段
ALTER TABLE game_account ADD COLUMN status VARCHAR(20) DEFAULT 'idle' COMMENT '账号状态 idle-空闲 busy-忙碌';

-- 3. 流媒体账号表添加任务状态字段
ALTER TABLE streaming_account ADD COLUMN task_status VARCHAR(20) DEFAULT 'idle' COMMENT '任务状态 idle-空闲 busy-忙碌';

-- 4. 更新现有数据的状态为空闲
UPDATE game_account SET status = 'idle' WHERE status IS NULL;
UPDATE streaming_account SET task_status = 'idle' WHERE task_status IS NULL;

-- 5. 添加索引
CREATE INDEX idx_game_account_status ON game_account(status);
CREATE INDEX idx_streaming_account_task_status ON streaming_account(task_status);