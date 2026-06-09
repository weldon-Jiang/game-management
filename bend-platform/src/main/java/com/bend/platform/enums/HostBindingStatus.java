package com.bend.platform.enums;

/**
 * 流媒体账号与主机绑定状态。
 */
public enum HostBindingStatus {

    ACTIVE("active"),
    INACTIVE("inactive");

    private final String code;

    HostBindingStatus(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}
