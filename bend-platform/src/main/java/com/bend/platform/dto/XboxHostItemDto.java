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
    private Integer port;                    // SmartGlass端口
    private String liveId;                   // Xbox Live ID
    private String consoleType;              // 主机型号
    private String firmwareVersion;          // 固件版本
    private String macAddress;               // MAC地址
    private String boundStreamingAccountId;
    private String boundGamertag;
    private String status;
    private Boolean locked;                  // 是否被锁定
    private String lockedByAgentId;          // 锁定者Agent ID
    private LocalDateTime lockExpiresTime;   // 锁过期时间
    private String platform;
    private LocalDateTime lastSeenTime;
    private LocalDateTime createdTime;
}
