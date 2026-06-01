package com.bend.platform.enums;

/**
 * Step4 game automation mode (sent to Agent as gameActionType / task_type).
 *
 * @see TaskType Agent WebSocket task routing channel (stream_control, etc.)
 */
public enum GameActionType {

    DAILY_MATCH("daily_match", "每日比赛"),
    TRAINING("training", "训练模式"),
    MISSION("mission", "任务挑战"),
    CUSTOM("custom", "自定义操作");

    private final String code;
    private final String description;

    GameActionType(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() {
        return code;
    }

    public String getDescription() {
        return description;
    }

    public static GameActionType fromCode(String code) {
        if (code == null || code.isEmpty()) {
            return DAILY_MATCH;
        }
        for (GameActionType type : values()) {
            if (type.code.equals(code)) {
                return type;
            }
        }
        return DAILY_MATCH;
    }
}
