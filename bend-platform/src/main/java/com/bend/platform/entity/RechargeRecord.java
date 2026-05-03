package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 充值记录实体
 */
@Data
@TableName("recharge_record")
public class RechargeRecord {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String userId;

    private BigDecimal amount;

    private Integer points;

    private Integer bonusPoints;

    private String paymentMethod;

    private String transactionId;

    private String status;

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
