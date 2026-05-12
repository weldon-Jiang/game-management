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
}