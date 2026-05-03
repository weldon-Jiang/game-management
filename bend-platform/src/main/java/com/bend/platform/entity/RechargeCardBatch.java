package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 充值卡批次实体
 */
@Data
@TableName("recharge_card_batch")
public class RechargeCardBatch {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;

    private String cardType;

    private String targetMerchantId;

    private Integer totalCount;

    private Integer denomination;

    private Integer bonusPoints;

    private Integer pointsToGrant;

    private BigDecimal price;

    private Integer validDays;

    private String status;

    private Integer generatedCount;

    private Integer soldCount;

    private Integer usedCount;

    private String createdBy;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
