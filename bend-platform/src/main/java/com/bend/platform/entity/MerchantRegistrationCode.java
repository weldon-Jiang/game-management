package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 分控安装注册码：总控为商户签发，分控安装激活时一次性消费。
 */
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

    private LocalDateTime createdTime;

    private LocalDateTime expireTime;

    private LocalDateTime usedTime;
}
