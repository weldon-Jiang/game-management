package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("merchant_registration_code")
public class MerchantRegistrationCode {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String code;

    private String status;

    private String usedByAgentId;

    private String agentId;

    private LocalDateTime createdAt;

    private LocalDateTime expireTime;

    private LocalDateTime usedAt;
}
