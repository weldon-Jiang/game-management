package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 充值卡实体
 */
@Data
@TableName("recharge_card")
public class RechargeCard {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String cardType;

    private String batchId;

    private String cardNo;

    private String cardPwd;

    private Integer denomination;

    private Integer bonusPoints;

    private Integer pointsToGrant;

    private BigDecimal price;

    private String status;

    private String soldToMerchantId;

    private String soldByUserId;

    private LocalDateTime soldTime;

    private String usedByMerchantId;

    private String usedByUserId;

    private LocalDateTime usedTime;

    private LocalDateTime expireTime;

    private String usedRechargeRecordId;

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
