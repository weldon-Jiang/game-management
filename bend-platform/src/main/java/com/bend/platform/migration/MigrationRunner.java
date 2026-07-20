package com.bend.platform.migration;

import com.bend.platform.config.LicenseClientCondition;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Conditional;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 数据库增量迁移执行器（仅分控 tenant 模式启用）。
 *
 * <p>工作原理:
 * <ol>
 *   <li>启动时在数据库中创建 migration_history 表（如不存在）</li>
 *   <li>扫描 classpath:db/migration/V*.sql，按文件名排序</li>
 *   <li>对比 migration_history，只执行未跑过的脚本</li>
 *   <li>每条脚本执行后立即记录到 migration_history</li>
 * </ol>
 *
 * <p>迁移脚本编写要求（确保幂等）:
 * <ul>
 *   <li>DDL 使用 IF NOT EXISTS / IF EXISTS</li>
 *   <li>DML 使用 INSERT IGNORE 或先检查再插入</li>
 * </ul>
 *
 * <p>零外部依赖，纯 JDBC + Spring classpath 扫描。
 */
@Slf4j
@Component
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
@ConditionalOnProperty(name = "bend.migration.enabled", havingValue = "true")
public class MigrationRunner {

    private static final String MIGRATION_TABLE = "migration_history";
    private static final String MIGRATION_LOCATION = "classpath:db/migration/V*.sql";
    private static final DateTimeFormatter DTF = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;

    /**
     * 迁移脚本在 application.properties/tenant.env 中可控开关，
     * 但属性注入仅用于日志提示，实际的 @ConditionalOnProperty 已在类级别控制装配。
     */
    @Value("${bend.migration.enabled:false}")
    private boolean enabled;

    @PostConstruct
    public void run() {
        if (!enabled) {
            log.info("[MigrationRunner] bend.migration.enabled=false，跳过迁移");
            return;
        }

        log.info("[MigrationRunner] 开始数据库增量迁移...");

        // 1. 确保追踪表存在
        ensureHistoryTable();

        // 2. 获取已执行的迁移
        List<String> executed = getExecutedMigrations();

        // 3. 扫描待执行的迁移脚本
        List<MigrationFile> pending = scanPendingMigrations(executed);

        if (pending.isEmpty()) {
            log.info("[MigrationRunner] 数据库已是最新，无需迁移 (已执行 {} 条)", executed.size());
            return;
        }

        log.info("[MigrationRunner] 发现 {} 条待执行迁移: {}", pending.size(),
                pending.stream().map(m -> m.filename).collect(Collectors.joining(", ")));

        // 4. 按文件名排序后依次执行
        Collections.sort(pending);
        int applied = 0;
        for (MigrationFile mf : pending) {
            try {
                executeMigration(mf);
                applied++;
            } catch (Exception e) {
                log.error("[MigrationRunner] 迁移执行失败: {} — 终止后续迁移", mf.filename, e);
                recordMigration(mf.filename, mf.content, false);
                throw new RuntimeException("数据库迁移失败: " + mf.filename, e);
            }
        }

        log.info("[MigrationRunner] 迁移完成: 本次执行 {} 条，累计已执行 {} 条",
                applied, executed.size() + applied);
    }

    // ---------- 内部方法 ----------

    private void ensureHistoryTable() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS `%s` (
                    `filename` VARCHAR(255) NOT NULL COMMENT '迁移脚本文件名',
                    `executed_at` DATETIME NOT NULL COMMENT '执行时间',
                    `checksum` VARCHAR(64) DEFAULT NULL COMMENT '脚本内容 MD5',
                    `success` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否成功',
                    `error_message` TEXT DEFAULT NULL COMMENT '失败原因',
                    PRIMARY KEY (`filename`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库迁移历史'
                """.formatted(MIGRATION_TABLE));
    }

    private List<String> getExecutedMigrations() {
        // 确保表存在后再查（fresh install 时 ensureHistoryTable 刚建表）
        return jdbc.queryForList(
                "SELECT filename FROM `%s` WHERE success = 1 ORDER BY filename".formatted(MIGRATION_TABLE),
                String.class);
    }

    private List<MigrationFile> scanPendingMigrations(List<String> executed) {
        List<MigrationFile> pending = new ArrayList<>();
        try {
            PathMatchingResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();
            Resource[] resources = resolver.getResources(MIGRATION_LOCATION);

            for (Resource res : resources) {
                String filename = res.getFilename();
                if (filename == null || !filename.startsWith("V")) {
                    continue;
                }
                if (executed.contains(filename)) {
                    log.debug("[MigrationRunner] 跳过已执行: {}", filename);
                    continue;
                }
                String content = readContent(res);
                if (content.isBlank()) {
                    log.warn("[MigrationRunner] 跳过空脚本: {}", filename);
                    continue;
                }
                pending.add(new MigrationFile(filename, content));
            }
        } catch (Exception e) {
            log.error("[MigrationRunner] 扫描迁移脚本失败", e);
            throw new RuntimeException("扫描迁移脚本失败", e);
        }
        return pending;
    }

    private String readContent(Resource resource) {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append("\n");
            }
        } catch (Exception e) {
            throw new RuntimeException("读取迁移脚本失败: " + resource.getFilename(), e);
        }
        return sb.toString();
    }

    private void executeMigration(MigrationFile mf) {
        log.info("[MigrationRunner] 执行迁移: {}", mf.filename);
        jdbc.execute(mf.content);
        recordMigration(mf.filename, mf.content, true);
        log.info("[MigrationRunner] 迁移完成: {}", mf.filename);
    }

    private void recordMigration(String filename, String content, boolean success) {
        String checksum = md5(content);
        jdbc.update(
                "INSERT INTO `%s` (filename, executed_at, checksum, success) VALUES (?, ?, ?, ?)"
                        .formatted(MIGRATION_TABLE),
                filename,
                LocalDateTime.now().format(DTF),
                checksum,
                success ? 1 : 0);
    }

    private String md5(String input) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return "unknown";
        }
    }

    // ---------- 内部类 ----------

    private static class MigrationFile implements Comparable<MigrationFile> {
        final String filename;
        final String content;

        MigrationFile(String filename, String content) {
            this.filename = filename;
            this.content = content;
        }

        @Override
        public int compareTo(MigrationFile other) {
            return this.filename.compareTo(other.filename);
        }
    }
}
