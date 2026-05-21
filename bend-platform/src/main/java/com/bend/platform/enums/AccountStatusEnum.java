package com.bend.platform.enums;

/**
 * 账号状态枚举（空闲/忙碌）
 * 
 * 用于表示流媒体账号和游戏账号的当前状态
 */
public enum AccountStatusEnum {
    
    /**
     * 空闲 - 账号可被分配新任务
     */
    IDLE("idle", "空闲"),
    
    /**
     * 忙碌 - 账号正在执行任务，不可被分配新任务
     */
    BUSY("busy", "忙碌");
    
    private final String code;
    private final String description;
    
    AccountStatusEnum(String code, String description) {
        this.code = code;
        this.description = description;
    }
    
    public String getCode() {
        return code;
    }
    
    public String getDescription() {
        return description;
    }
    
    public static AccountStatusEnum fromCode(String code) {
        for (AccountStatusEnum status : values()) {
            if (status.code.equals(code)) {
                return status;
            }
        }
        return IDLE;
    }
}