package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 商户用户实体类
 * 代表商户下的用户账号，用于登录认证
 */
@Data
@TableName("merchant_user")
public class MerchantUser {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;
    private String username;
    private String phone;
    private String passwordHash;
    private String role;
    private String status;
    private LocalDateTime lastLoginTime;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}