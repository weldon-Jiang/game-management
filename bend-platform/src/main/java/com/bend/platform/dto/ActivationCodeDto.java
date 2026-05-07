package com.bend.platform.dto;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

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
