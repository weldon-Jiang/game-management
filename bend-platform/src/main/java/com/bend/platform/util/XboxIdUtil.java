package com.bend.platform.util;

import org.apache.commons.lang3.StringUtils;

import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Xbox 设备 ID 规范化与别名展开。
 *
 * <p>对齐 Agent {@code XboxHostMatcher.normalize_server_id}：GSSV 短十六进制、
 * LAN SSDP UUID、{@code XBOX-} 前缀等形式在入库与查重时视为同一设备的多种写法。</p>
 */
public final class XboxIdUtil {

    private static final Pattern UUID_PATTERN = Pattern.compile(
            "^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$");
    private static final Pattern SHORT_HEX_PATTERN = Pattern.compile("^[0-9A-F]{16}$");

    private XboxIdUtil() {
    }

    /**
     * 规范化为带 {@code XBOX-} 前缀的大写形式，供新记录统一存储。
     */
    public static String normalizeCanonical(String raw) {
        String trimmed = StringUtils.trimToEmpty(raw).toUpperCase(Locale.ROOT);
        if (trimmed.isEmpty()) {
            return "";
        }
        if (trimmed.startsWith("XBOX-")) {
            return trimmed;
        }
        return "XBOX-" + trimmed;
    }

    /**
     * 展开可用于数据库匹配的别名集合（含原值、大小写变体、有无前缀）。
     */
    public static Set<String> expandAliasKeys(String raw) {
        Set<String> keys = new LinkedHashSet<>();
        if (!StringUtils.isNotBlank(raw)) {
            return keys;
        }
        String trimmed = raw.trim();
        String upper = trimmed.toUpperCase(Locale.ROOT);
        String lower = trimmed.toLowerCase(Locale.ROOT);
        keys.add(trimmed);
        keys.add(upper);
        keys.add(lower);

        String canonical = normalizeCanonical(trimmed);
        if (StringUtils.isNotBlank(canonical)) {
            keys.add(canonical);
            if (canonical.startsWith("XBOX-")) {
                keys.add(canonical.substring(5));
            }
        }

        String compact = upper.replace("-", "");
        if (StringUtils.isNotBlank(compact)) {
            keys.add(compact);
        }
        return keys;
    }

    /** 判断两个 ID 是否互为别名。 */
    public static boolean areAliases(String left, String right) {
        if (!StringUtils.isNotBlank(left) || !StringUtils.isNotBlank(right)) {
            return false;
        }
        Set<String> leftKeys = expandAliasKeys(left);
        for (String rightKey : expandAliasKeys(right)) {
            if (leftKeys.contains(rightKey)) {
                return true;
            }
        }
        return false;
    }

    /** GSSV 云端 serverId（16 位十六进制）。 */
    public static boolean isGssvShortId(String id) {
        String body = stripXboxPrefix(id);
        return SHORT_HEX_PATTERN.matcher(body).matches();
    }

    /** LAN SSDP 硬件 UUID。 */
    public static boolean isHardwareUuid(String id) {
        String body = stripXboxPrefix(id);
        return UUID_PATTERN.matcher(body).matches();
    }

    private static String stripXboxPrefix(String id) {
        String upper = StringUtils.trimToEmpty(id).toUpperCase(Locale.ROOT);
        if (upper.startsWith("XBOX-")) {
            return upper.substring(5);
        }
        return upper;
    }
}
