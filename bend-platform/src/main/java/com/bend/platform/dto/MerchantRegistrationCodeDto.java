package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 注册码列表 DTO
 */
@Data
public class MerchantRegistrationCodeDto {
    private String id;
    private String merchantId;
    private String merchantName;
    private String code;
    private String status;
    private String usedByAgentId;
    private String agentId;
    private LocalDateTime createdAt;
    private LocalDateTime expireTime;
    private LocalDateTime usedAt;
}
