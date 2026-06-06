package com.bend.platform.util;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Debug-mode NDJSON logger (session ba0362). Remove after verification.
 */
public final class DebugSessionLog {

    private static final String SESSION_ID = "25877d";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private DebugSessionLog() {
    }

    public static void log(String hypothesisId, String location, String message, Map<String, Object> data) {
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
