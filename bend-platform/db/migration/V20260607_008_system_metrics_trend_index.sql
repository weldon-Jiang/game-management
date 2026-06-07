-- Add composite index for bounded monitoring trend queries

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `system_metrics`
    ADD INDEX `idx_metric_type_name_time` (`metric_type`, `metric_name`, `recorded_time`);
