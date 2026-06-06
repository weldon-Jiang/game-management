-- 修复 streaming_account.status CHECK 约束未包含 'busy' 的问题
-- 现象：启动自动化时将 status 更新为 busy 触发 chk_streaming_account_status 违反约束

ALTER TABLE streaming_account DROP CONSTRAINT chk_streaming_account_status;

ALTER TABLE streaming_account
ADD CONSTRAINT chk_streaming_account_status
CHECK (status IN ('idle', 'ready', 'running', 'paused', 'error', 'busy'));
