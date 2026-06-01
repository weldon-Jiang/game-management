USE bend_platform;

UPDATE streaming_account 
SET task_status = 'idle', agent_id = NULL 
WHERE id = '575f67249be844b0730249b1aab38bb0';

UPDATE game_account 
SET status = 'idle', agent_id = NULL 
WHERE streaming_id = '575f67249be844b0730249b1aab38bb0';

SELECT 'Status reset completed' AS result;