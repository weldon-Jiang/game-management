package com.bend.platform.enums;

/**
 * 流媒体账号与主机绑定来源。
 */
public enum HostBindingSource {

    MANUAL("manual"),
    CLOUD_SYNC("cloud_sync"),
    STREAM_SUCCESS("stream_success");

    private final String code;

    HostBindingSource(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    public static HostBindingSource fromCode(String code) {
        if (code == null || code.isBlank()) {
            return MANUAL;
        }
        for (HostBindingSource source : values()) {
            if (source.code.equalsIgnoreCase(code.trim())) {
                return source;
            }
        }
        return MANUAL;
    }
}
