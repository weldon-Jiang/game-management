package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 点数变动记录实体
 */
@Data
@TableName("point_transaction")
public class PointTransaction {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String userId;

    private String type;

    private Integer points;

    private Integer balanceBefore;

    private Integer balanceAfter;

    private String refSubscriptionId;

    private String refDeviceBindingId;

    private String refRechargeRecordId;

    private String refRechargeCardId;

    private String description;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
