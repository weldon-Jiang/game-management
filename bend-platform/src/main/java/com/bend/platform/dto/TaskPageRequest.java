package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 任务分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class TaskPageRequest extends PageRequest {

    /**
     * 任务状态过滤
     */
    private String status;

    /**
     * 任务类型过滤
     */
    private String type;

    /**
     * 执行Agent过滤
     */
    private String targetAgentId;

    /**
     * 串流账号过滤
     */
    private String streamingAccountId;

    /**
     * 仅返回今日有更新的任务（按 updated_time 当天 00:00 起算，适配长寿命任务复用场景）
     */
    private Boolean activeToday;
}