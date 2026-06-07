-- Group task_event timeline by streaming session (run) within a reusable task

ALTER TABLE `task_event`
    ADD COLUMN `session_id` VARCHAR(64) DEFAULT NULL COMMENT '串流会话ID' AFTER `payload`,
    ADD KEY `idx_session_id` (`session_id`);
