-- 删除 streaming_account 表的 task_status 字段
-- 原因：task_status 和 status 字段含义重复，统一使用 status 字段

ALTER TABLE streaming_account DROP COLUMN task_status;
