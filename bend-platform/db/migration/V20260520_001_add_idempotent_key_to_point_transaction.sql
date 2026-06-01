-- 添加幂等键字段用于扣点幂等控制
-- 日期: 2026-05-20

ALTER TABLE `point_transaction`
ADD COLUMN `idempotent_key` VARCHAR(128) DEFAULT NULL COMMENT '幂等键' AFTER `ref_recharge_card_id`;

-- 添加索引
ALTER TABLE `point_transaction`
ADD INDEX `idx_idempotent_key` (`idempotent_key`);
