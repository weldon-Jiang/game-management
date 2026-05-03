package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 订阅实体
 * 按主机/窗口/号计费的订阅记录
 */
@Data
@TableName("subscription")
public class Subscription {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String userId;

    private String groupId;

    private String type;

    private String targetId;

    private String targetName;

    private Integer pointsCost;

    private Integer durationDays;

    private LocalDateTime startTime;

    private LocalDateTime expireTime;

    private String status;

    private Boolean autoRenew;

    private LocalDateTime unboundTime;

    private Integer refundPoints;

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
