package com.bend.platform.config;

import io.github.cdimascio.dotenv.Dotenv;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * Dotenv 环境变量加载器
 *
 * 功能说明：
 * - 在应用启动时加载 .env 文件
 * - 将 .env 中的变量注入到系统环境变量
 * - 支持多环境配置（.env.local, .env.dev, .env.prod）
 *
 * 使用方式：
 * 1. 复制 .env.example 为 .env
 * 2. 填入实际配置值
 * 3. 重启应用
 */
@Slf4j
@Component
public class DotenvLoader {

    @PostConstruct
    public void loadDotenv() {
        try {
            Dotenv dotenv = Dotenv.configure()
                    .ignoreIfMissing()
                    .load();

            if (dotenv != null) {
                final int[] count = {0};
                dotenv.entries().forEach(entry -> {
                    String key = entry.getKey();
                    String value = entry.getValue();
                    if (System.getProperty(key) == null && value != null) {
                        System.setProperty(key, value);
                        count[0]++;
                    }
                });
                log.info("已从 .env 加载 {} 个环境变量", count[0]);
            }
        } catch (Exception e) {
            log.debug("未找到或无法加载 .env: {}", e.getMessage());
        }

        log.info("环境变量加载完成");
        logDatabaseConfig();
    }

    private void logDatabaseConfig() {
        String dbUrl = System.getProperty("DB_URL", "jdbc:mysql://localhost:3306/bend_platform");
        String redisHost = System.getProperty("REDIS_HOST", "127.0.0.1");
        String jwtSecret = System.getProperty("JWT_SECRET", "");
        String aesSecret = System.getProperty("AES_SECRET", "");

        log.info("数据库URL: {}", dbUrl.substring(0, Math.min(50, dbUrl.length())) + "...");
        log.info("Redis地址: {}:{}", redisHost, System.getProperty("REDIS_PORT", "6379"));
        log.info("JWT密钥配置: {}", jwtSecret.isEmpty() ? "❌ 未配置" : "✅ 已配置");
        log.info("AES密钥配置: {}", aesSecret.isEmpty() ? "❌ 未配置" : "✅ 已配置");
    }
}
