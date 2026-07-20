package com.bend.platform.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 总控返回给分控的 License 校验结果
 *
 * <p>该对象会被序列化为 JSON 并由总控签名,分控本地缓存整个签名结果用于离线宽限。
 */
@Data
public class LicenseVerifyResponse {

    /** 是否有效 */
    private Boolean valid;

    /** 商户ID */
    private String merchantId;

    /** 商户名称 */
    private String merchantName;

    /** 授权状态: active, expired, revoked */
    private String status;

    /** 到期时间 */
    private LocalDateTime expireAt;

    /** 最大Agent数量 */
    private Integer maxAgents;

    /** 最大并发任务数 */
    private Integer maxTasks;

    /** 功能特性JSON */
    private String features;

    /** 离线宽限小时数 */
    private Integer offlineGraceHours;

    /** 本次校验时间(总控服务器时间,参与签名) */
    private LocalDateTime verifiedAt;

    /** 失效原因(valid=false 时填充) */
    private String invalidReason;

    /** 校验结果签名(对除 signature 外字段的 JSON 做 HMAC-SHA256) */
    private String signature;
}
