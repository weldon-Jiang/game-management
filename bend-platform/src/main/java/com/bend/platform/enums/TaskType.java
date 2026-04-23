package com.bend.platform.enums;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

public enum TaskType {

    STREAM_CONTROL("stream_control", "流媒体控制"),
    ACCOUNT_LOGIN("account_login", "账号登录"),
    ACCOUNT_LOGOUT("account_logout", "账号登出"),
    GAME_LAUNCH("game_launch", "游戏启动"),
    GAME_CLOSE("game_close", "游戏关闭"),
    CUSTOM("custom", "自定义任务");

    private final String code;
    private final String description;

    private static final Map<String, TaskType> CODE_MAP = new HashMap<>();

    static {
        for (TaskType type : TaskType.values()) {
            CODE_MAP.put(type.code, type);
        }
    }

    TaskType(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() {
        return code;
    }

    public String getDescription() {
        return description;
    }

    public static TaskType fromCode(String code) {
        return CODE_MAP.get(code);
    }

    public static boolean isValid(String code) {
        return CODE_MAP.containsKey(code);
    }

    public static List<String> getAllCodes() {
        return Arrays.stream(values()).map(TaskType::getCode).toList();
    }
}