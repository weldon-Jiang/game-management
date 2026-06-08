-- 开发环境维护脚本：将指定 streaming_account 及其 game_account 重置为 idle。
-- 使用前请替换下方 ID；非版本化脚本，勿在生产环境盲目执行。
USE bend_platform;

UPDATE streaming_account 
SET task_status = 'idle', agent_id = NULL 
WHERE id = '575f67249be844b0730249b1aab38bb0';

UPDATE game_account 
SET status = 'idle', agent_id = NULL 
WHERE streaming_id = '575f67249be844b0730249b1aab38bb0';

SELECT 'Status reset completed' AS result;