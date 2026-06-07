-- Streaming account display name is optional; email is the primary identifier
ALTER TABLE `streaming_account`
    MODIFY COLUMN `name` VARCHAR(100) DEFAULT NULL COMMENT '账号名称（可选，已弃用）';
