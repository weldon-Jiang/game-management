package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * Xbox主机列表项DTO（包含商户名称）
 */
@Data
public class XboxHostItemDto {
    private String id;
    private String merchantId;
    private String merchantName;
    private String xboxId;
    private String name;
    private String ipAddress;
    private String boundStreamingAccountId;
    private String boundGamertag;
    private String status;
    private LocalDateTime lastSeenAt;
    private LocalDateTime createdAt;
}