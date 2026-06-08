package com.bend.platform.dto;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 激活码列表/详情展示 DTO（含订阅类型、绑定资源与点数信息）。
 */
@Data
public class ActivationCodeDto {
    private String id;
    private String merchantId;
    private String merchantName;
    private String batchId;
    private String code;
    private Integer points;
    private Integer pointsAmount;
    private String status;
    private String usedBy;
    private String usedByName;
    private LocalDateTime usedTime;
    private LocalDateTime expireTime;
    private LocalDateTime generatedTime;
    private LocalDateTime createdTime;
    private LocalDateTime updatedTime;
    private String subscriptionType;
    private String targetId;
    private String targetName;
    private Integer durationDays;
    private BigDecimal dailyPrice;
}
