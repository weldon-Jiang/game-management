package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 商户 VIP 分组：各订阅类型的原价/折扣价（分）与升级门槛。
 */
@Data
@TableName("merchant_group")
public class MerchantGroup {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String description;
    private Integer vipLevel;
    private Integer amountThreshold;
    private Integer windowOriginalPrice;
    private Integer windowDiscountPrice;
    private Integer accountOriginalPrice;
    private Integer accountDiscountPrice;
    private Integer hostOriginalPrice;
    private Integer hostDiscountPrice;
    private Integer fullOriginalPrice;
    private Integer fullDiscountPrice;
    private Integer pointsOriginalPrice;
    private Integer pointsDiscountPrice;
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}