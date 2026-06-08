-- Add missing column comments for task_game_account_status (sync with schema.sql)

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `task_game_account_status`
    MODIFY COLUMN `game_action_type` VARCHAR(50) DEFAULT NULL COMMENT 'Step4自动化类型：squad_battle/auction_transfer等',
    MODIFY COLUMN `match_index` INT DEFAULT 0 COMMENT '当前比赛序号，从1开始',
    MODIFY COLUMN `match_total` INT DEFAULT 0 COMMENT '本账号本轮计划比赛总数',
    MODIFY COLUMN `provisioning_phase` VARCHAR(32) DEFAULT NULL COMMENT '账号开通阶段：creating_profile/binding_profile等',
    MODIFY COLUMN `provisioning_step` INT DEFAULT NULL COMMENT '当前开通步骤序号',
    MODIFY COLUMN `provisioning_step_total` INT DEFAULT NULL COMMENT '开通步骤总数',
    MODIFY COLUMN `provisioning_message` VARCHAR(512) DEFAULT NULL COMMENT '开通阶段前端展示说明',
    MODIFY COLUMN `active_module` VARCHAR(64) DEFAULT NULL COMMENT '当前占用模块：provisioning/step4/manual_control';
