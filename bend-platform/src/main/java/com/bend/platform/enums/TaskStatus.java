package com.bend.platform.enums;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

public enum TaskStatus {

    PENDING("pending", "待处理"),
    RUNNING("running", "执行中"),
    COMPLETED("completed", "已完成"),
    FAILED("failed", "失败"),
    CANCELLED("cancelled", "已取消");

    private final String code;
    private final String description;

    private static final Map<String, TaskStatus> CODE_MAP = new HashMap<>();

    static {
        for (TaskStatus status : TaskStatus.values()) {
            CODE_MAP.put(status.code, status);
        }
    }

    TaskStatus(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() {
        return code;
    }

    public String getDescription() {
        return description;
    }

    public static TaskStatus fromCode(String code) {
        return CODE_MAP.get(code);
    }

    public static boolean isValid(String code) {
        return CODE_MAP.containsKey(code);
    }

    public List<TaskStatus> getAllowedTransitions() {
        return switch (this) {
            case PENDING -> Arrays.asList(RUNNING, CANCELLED);
            case RUNNING -> Arrays.asList(COMPLETED, FAILED, CANCELLED);
            case COMPLETED -> Arrays.asList();
            case FAILED -> Arrays.asList(PENDING, RUNNING);
            case CANCELLED -> Arrays.asList();
        };
    }

    public boolean canTransitionTo(TaskStatus target) {
        return getAllowedTransitions().contains(target);
    }

    public static TaskStatus[] getAllStatuses() {
        return values();
    }
}