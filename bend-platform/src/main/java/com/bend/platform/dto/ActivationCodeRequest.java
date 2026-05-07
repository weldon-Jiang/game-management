package com.bend.platform.dto;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 激活码请求参数
 */
@Data
public class ActivationCodeRequest {
    private String merchantId;
    private String batchName;
    private Integer points;
    private Integer count;
    private LocalDateTime expireTime;

    // 订阅类型：points-点数、account-游戏账号、window-窗口、host-主机
    private String subscriptionType;
    // 定向目标ID
    private String targetId;
    // 定向目标名称
    private String targetName;
    // 订阅时长（天数）
    private Integer durationDays;
    // 每日价格
    private BigDecimal dailyPrice;
}