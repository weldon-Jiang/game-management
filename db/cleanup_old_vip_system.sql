-- 数据库清理脚本
-- 删除旧的 VIP 配置表（vip_config）
-- 注意：现在的 vipLevel 是商户等级概念，在 MerchantGroup 表中，不要删除

USE bend_platform;

-- 删除旧的 VIP 配置表（vip_config）
DROP TABLE IF EXISTS vip_config;

SELECT 'Old vip_config table has been removed!' AS message;
