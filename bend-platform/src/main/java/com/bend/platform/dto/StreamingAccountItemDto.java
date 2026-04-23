package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 流媒体账号列表项DTO（包含商户名称）
 */
@Data
public class StreamingAccountItemDto {
    private String id;
    private String merchantId;
    private String merchantName;
    private String name;
    private String email;
    private String status;
    private LocalDateTime lastHeartbeat;
    private LocalDateTime createdTime;
}
