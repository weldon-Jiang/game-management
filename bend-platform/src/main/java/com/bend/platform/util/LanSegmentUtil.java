package com.bend.platform.util;

/**
 * LAN 网段工具：用于判断 Agent 是否处于同一局域网（/24 粗粒度）。
 */
public final class LanSegmentUtil {

    private LanSegmentUtil() {
    }

    /**
     * 从 IPv4 提取 /24 网段键，如 192.168.1.10 → 192.168.1。
     */
    public static String segmentFromIp(String ip) {
        if (ip == null || ip.isBlank()) {
            return null;
        }
        String trimmed = ip.trim();
        int slash = trimmed.indexOf('/');
        if (slash > 0) {
            trimmed = trimmed.substring(0, slash);
        }
        String[] parts = trimmed.split("\\.");
        if (parts.length != 4) {
            return null;
        }
        try {
            for (String part : parts) {
                int octet = Integer.parseInt(part);
                if (octet < 0 || octet > 255) {
                    return null;
                }
            }
        } catch (NumberFormatException e) {
            return null;
        }
        return parts[0] + "." + parts[1] + "." + parts[2];
    }

    public static boolean isSameSegment(String ipA, String ipB) {
        String segA = segmentFromIp(ipA);
        String segB = segmentFromIp(ipB);
        return segA != null && segA.equals(segB);
    }

    public static boolean isPrivateLanIp(String ip) {
        if (segmentFromIp(ip) == null) {
            return false;
        }
        String trimmed = ip.trim();
        int slash = trimmed.indexOf('/');
        if (slash > 0) {
            trimmed = trimmed.substring(0, slash);
        }
        String[] parts = trimmed.split("\\.");
        if (parts.length != 4) {
            return false;
        }
        try {
            int first = Integer.parseInt(parts[0]);
            int second = Integer.parseInt(parts[1]);
            if (first == 10) {
                return true;
            }
            if (first == 192 && second == 168) {
                return true;
            }
            if (first == 172 && second >= 16 && second <= 31) {
                return true;
            }
        } catch (NumberFormatException ignored) {
            return false;
        }
        return false;
    }
}
