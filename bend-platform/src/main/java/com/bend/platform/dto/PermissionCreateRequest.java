package com.bend.platform.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 创建/更新商户使用权限请求
 */
@Data
public class PermissionCreateRequest {

    /** 商户ID */
    private String merchantId;

    /** 到期时间 */
    private LocalDateTime expireAt;

    /** 最大Agent数量，默认5 */
    private Integer maxAgents;

    /** 最大并发任务数，默认50 */
    private Integer maxTasks;

    /** 功能特性JSON */
    private String features;

    /** 离线宽限小时数，默认24 */
    private Integer offlineGraceHours;
}
