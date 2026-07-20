package com.bend.platform.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 创建授权(License)请求 —— 总控后台为商户签发分控 license
 */
@Data
public class LicenseCreateRequest {

    /** 商户ID */
    private String merchantId;

    /** 到期时间 */
    private LocalDateTime expireAt;

    /** 最大Agent数量,默认5 */
    private Integer maxAgents;

    /** 最大并发任务数,默认50 */
    private Integer maxTasks;

    /** 功能特性JSON,可选 */
    private String features;

    /** 离线宽限小时数,默认24 */
    private Integer offlineGraceHours;

    /** 是否立即绑定机器指纹(打包时已知目标机器则传入),可选 */
    private String machineFingerprint;
}
