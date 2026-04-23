package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 用户列表项DTO（包含商户名称）
 */
@Data
public class MerchantUserItemDto {
    private String id;
    private String merchantId;
    private String merchantName;
    private String username;
    private String phone;
    private String role;
    private String status;
    private LocalDateTime lastLoginTime;
    private LocalDateTime createdTime;
}
