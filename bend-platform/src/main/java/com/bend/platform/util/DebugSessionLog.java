package com.bend.platform.util;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 本地调试用 NDJSON 日志（session 25877d）。
 *
 * <p>仅用于本地排障，默认关闭：必须显式设置系统属性 {@code -Dbend.debug.session=true}
 * 或环境变量 {@code BEND_DEBUG_SESSION=true} 才会写日志。生产打包后该工具不产生任何动作，
 * 写出的 {@code debug-*.log} 也已被 .gitignore 忽略、不会进入构建产物。</p>
 */
public final class DebugSessionLog {

    private static final String SESSION_ID = "25877d";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 调试开关：默认关闭，仅本地通过系统属性或环境变量显式开启。 */
    private static final boolean ENABLED = resolveEnabled();

    private DebugSessionLog() {
    }

    private static boolean resolveEnabled() {
        String prop = System.getProperty("bend.debug.session");
        if (prop == null || prop.isBlank()) {
            prop = System.getenv("BEND_DEBUG_SESSION");
        }
        if (prop == null) {
            return false;
        }
        String v = prop.trim().toLowerCase();
        return v.equals("1") || v.equals("true") || v.equals("on") || v.equals("yes");
    }

    public static void log(String hypothesisId, String location, String message, Map<String, Object> data) {
        if (!ENABLED) {
            return;
        }
        try {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("sessionId", SESSION_ID);
            entry.put("hypothesisId", hypothesisId);
            entry.put("location", location);
            entry.put("message", message);
            entry.put("data", data != null ? data : Map.of());
            entry.put("timestamp", System.currentTimeMillis());
            String line = MAPPER.writeValueAsString(entry) + System.lineSeparator();
            Files.writeString(resolveLogPath(), line, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception ignored) {
            // debug only
        }
    }

    private static Path resolveLogPath() {
        Path cwd = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        if ("bend-platform".equals(cwd.getFileName().toString())) {
            return cwd.getParent().resolve("debug-25877d.log");
        }
        return cwd.resolve("debug-25877d.log");
    }
}
