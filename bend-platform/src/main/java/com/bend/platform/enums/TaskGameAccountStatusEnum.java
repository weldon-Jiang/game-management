package com.bend.platform.enums;

/**
 * 子任务（游戏账号）状态枚举
 * 
 * 状态流转：
 * pending -> running -> game_preparing -> gaming -> completed
 *                                   ↓
 *                              failed/cancelled/timeout/skipped
 */
public enum TaskGameAccountStatusEnum {
    
    /**
     * 待执行 - 初始状态，等待执行
     */
    PENDING("pending", "待执行"),
    
    /**
     * 操作中 - 正在处理中，准备进入游戏
     */
    RUNNING("running", "操作中"),
    
    /**
     * 游戏准备中 - 正在准备游戏，如匹配队列等
     */
    GAME_PREPARING("game_preparing", "游戏准备中"),
    
    /**
     * 游戏中 - 比赛进行中
     */
    GAMING("gaming", "游戏中"),
    
    /**
     * 已完成 - 所有比赛完成
     */
    COMPLETED("completed", "已完成"),
    
    /**
     * 失败 - 执行失败
     */
    FAILED("failed", "失败"),
    

    
    /**
     * 取消 - 用户主动取消
     */
    CANCELLED("cancelled", "已取消"),
    
    /**
     * 超时 - 执行超时
     */
    TIMEOUT("timeout", "超时"),

    /**
     * 已跳过 - 用户或调度逻辑跳过该账号，视为终态
     */
    SKIPPED("skipped", "已跳过");
    
    private final String code;
    private final String description;
    
    TaskGameAccountStatusEnum(String code, String description) {
        this.code = code;
        this.description = description;
    }
    
    public String getCode() {
        return code;
    }
    
    public String getDescription() {
        return description;
    }
    
    public static TaskGameAccountStatusEnum fromCode(String code) {
        for (TaskGameAccountStatusEnum status : values()) {
            if (status.code.equals(code)) {
                return status;
            }
        }
        return PENDING;
    }
    
    /**
     * 判断是否为终态
     */
    public boolean isFinalStatus() {
        return this == COMPLETED || this == FAILED ||
               this == CANCELLED || this == TIMEOUT || this == SKIPPED;
    }
    
    /**
     * 判断是否为运行中状态
     */
    public boolean isRunningStatus() {
        return this == RUNNING || this == GAME_PREPARING || this == GAMING;
    }
    
    /**
     * 判断是否为忙碌状态（游戏账号正在执行任务，不可被分配新任务）
     * 忙碌状态：PENDING、RUNNING、GAME_PREPARING、GAMING
     */
    public boolean isBusy() {
        return this == PENDING || this == RUNNING || 
               this == GAME_PREPARING || this == GAMING;
    }
    
    /**
     * 判断是否为空闲状态（游戏账号可被分配新任务）
     * 空闲状态：COMPLETED、FAILED、CANCELLED、TIMEOUT、SKIPPED
     */
    public boolean isIdle() {
        return this == COMPLETED || this == FAILED ||
               this == CANCELLED || this == TIMEOUT || this == SKIPPED;
    }
}
