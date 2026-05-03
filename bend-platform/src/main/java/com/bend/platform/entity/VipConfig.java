package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * VIP配置实体类 ⚠️ 已废弃，请使用 MerchantGroup + Subscription 系统
 * 定义VIP套餐的价格和时长（平台级配置）
 *
 * @deprecated 请使用 {@link MerchantGroup} 和订阅系统
 */
@Data
@TableName("vip_config")
@Deprecated
public class VipConfig {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String vipType;
    private String vipName;
    private BigDecimal price;
    private Integer durationDays;
    private String features;
    private Boolean isDefault;
    private String status;
    private Integer sortOrder;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    @TableField(exist = false)
    private Boolean deprecated;

    @TableField(exist = false)
    private String deprecatedReason;

    @TableField(exist = false)
    private LocalDateTime deprecatedTime;
}