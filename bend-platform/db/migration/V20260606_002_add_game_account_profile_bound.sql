-- Xbox profile already bound on host; daily tasks use position_index switch only
ALTER TABLE `game_account`
    ADD COLUMN `profile_bound` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '档案已在Xbox主机绑定' AFTER `position_index`;
