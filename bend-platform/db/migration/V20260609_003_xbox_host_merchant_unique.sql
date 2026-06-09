SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `xbox_host`
    DROP INDEX `uk_xbox_id`,
    ADD UNIQUE KEY `uk_merchant_xbox` (`merchant_id`, `xbox_id`);
