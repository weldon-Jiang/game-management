-- Fix task game account status values used by runtime cancellation/progress flows.

ALTER TABLE task_game_account_status
DROP CONSTRAINT chk_task_game_account_status;

ALTER TABLE task_game_account_status
ADD CONSTRAINT chk_task_game_account_status
CHECK (status IN (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled',
    'skipped',
    'game_preparing',
    'gaming'
));
