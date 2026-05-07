package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商户权限分组实体
 * 定义不同VIP等级的功能权限和定价
 */
@Data
@TableName("merchant_group")
public class MerchantGroup {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;

    private Integer vipLevel;

    /**
     * 升级到此VIP等级需要的累计点数阈值
     */
    private Integer pointsThreshold;

    private BigDecimal discountRate;

    private BigDecimal unbindRefundRate;

    private Integer maxUnbindPerWeek;

    private String features;

    private BigDecimal hostPrice;

    private BigDecimal windowPrice;

    private BigDecimal accountPrice;

    private String status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
