package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class ActivationCodeDto {
    private String id;
    private String merchantId;
    private String merchantName;
    private String batchId;
    private String code;
    private String vipType;
    private String vipConfigId;
    private String status;
    private String usedBy;
    private String usedByName;
    private LocalDateTime usedAt;
    private LocalDateTime expireTime;
    private LocalDateTime generatedAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}