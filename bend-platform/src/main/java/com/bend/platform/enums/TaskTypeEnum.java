package com.bend.platform.enums;

/**
 * 任务类型枚举
 * 
 * 定义自动化任务的类型，用于区分不同的游戏操作
 */
public enum TaskTypeEnum {
    
    /**
     * 每日比赛 - 默认任务类型，执行每日比赛
     */
    DAILY_MATCH("daily_match", "每日比赛"),
    
    /**
     * 训练模式 - 游戏训练操作
     */
    TRAINING("training", "训练模式"),
    
    /**
     * 任务挑战 - 完成游戏内任务
     */
    MISSION("mission", "任务挑战"),
    
    /**
     * 自定义操作 - 用户自定义的游戏操作
     */
    CUSTOM("custom", "自定义操作");
    
    private final String code;
    private final String description;
    
    TaskTypeEnum(String code, String description) {
        this.code = code;
        this.description = description;
    }
    
    public String getCode() {
        return code;
    }
    
    public String getDescription() {
        return description;
    }
    
    public static TaskTypeEnum fromCode(String code) {
        for (TaskTypeEnum type : values()) {
            if (type.code.equals(code)) {
                return type;
            }
        }
        return DAILY_MATCH;
    }
}