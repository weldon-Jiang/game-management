package com.bend.platform.enums;

/**
 * Game console platform type for streaming accounts, game accounts, and hosts.
 */
public enum PlatformType {

    XBOX("xbox", "Xbox"),
    PLAYSTATION("playstation", "PlayStation");

    private final String code;
    private final String displayName;

    PlatformType(String code, String displayName) {
        this.code = code;
        this.displayName = displayName;
    }

    public String getCode() {
        return code;
    }

    public String getDisplayName() {
        return displayName;
    }

    public static PlatformType fromCode(String code) {
        if (code == null || code.isBlank()) {
            return XBOX;
        }
        for (PlatformType type : values()) {
            if (type.code.equalsIgnoreCase(code.trim())) {
                return type;
            }
        }
        return null;
    }

    public static String normalizeOrDefault(String code) {
        PlatformType type = fromCode(code);
        return type != null ? type.getCode() : XBOX.getCode();
    }

    public static void validateOrThrow(String code) {
        if (fromCode(code) == null) {
            throw new IllegalArgumentException("Invalid platform: " + code);
        }
    }

    public boolean supportsAutomation() {
        return this == XBOX;
    }
}
