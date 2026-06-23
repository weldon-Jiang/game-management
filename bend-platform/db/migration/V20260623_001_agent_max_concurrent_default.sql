SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `agent_instance`
  MODIFY COLUMN `max_concurrent_tasks` INT DEFAULT 20 COMMENT '最大并发任务数';
