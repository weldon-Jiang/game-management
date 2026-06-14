SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

-- Agent 实例级键盘→手柄映射（NULL 表示使用平台默认模板）
ALTER TABLE `agent_instance`
    ADD COLUMN `keyboard_mapping_json` TEXT DEFAULT NULL COMMENT '自定义键盘映射 JSON（key→action）；NULL=默认模板' AFTER `cpu_count`;
