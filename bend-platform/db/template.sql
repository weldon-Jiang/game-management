-- 模板表
-- 用于存储图像识别和自动化任务的模板图片

CREATE TABLE IF NOT EXISTS `template` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `name` VARCHAR(128) NOT NULL COMMENT '模板名称',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '模板描述',
    `category` VARCHAR(32) DEFAULT NULL COMMENT '分类：button,menu,icon,scene,text,other',
    `image_url` VARCHAR(512) NOT NULL COMMENT '模板图片URL',
    `thumbnail_url` VARCHAR(512) DEFAULT NULL COMMENT '缩略图URL',
    `width` INT DEFAULT NULL COMMENT '图片宽度',
    `height` INT DEFAULT NULL COMMENT '图片高度',
    `match_threshold` DECIMAL(3,2) DEFAULT 0.80 COMMENT '匹配阈值',
    `game` VARCHAR(32) DEFAULT NULL COMMENT '所属游戏',
    `region` VARCHAR(32) DEFAULT NULL COMMENT '所属区域',
    `usage_count` INT DEFAULT 0 COMMENT '使用次数',
    `status` TINYINT(1) DEFAULT 1 COMMENT '状态：0-禁用，1-启用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    KEY `idx_category` (`category`),
    KEY `idx_game` (`game`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模板表';
