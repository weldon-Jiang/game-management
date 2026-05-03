package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 订阅定价配置实体
 */
@Data
@TableName("subscription_price")
public class SubscriptionPrice {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String groupId;

    private String type;

    private Integer price;

    private Integer durationDays;

    private String status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
