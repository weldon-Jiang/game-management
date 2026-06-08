package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 激活码实体：订阅类型、绑定资源、原价/折扣价与使用状态。
 */
@Data
@TableName("activation_code")
public class ActivationCode {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String code;

    private String subscriptionType;

    private String boundResourceType;

    private String boundResourceIds;

    private String boundResourceNames;

    private Integer durationDays;

    private Integer originalPrice;

    private Integer discountPrice;

    private Integer pointsAmount;

    private LocalDateTime startTime;

    private LocalDateTime endTime;

    private String status;

    private String usedBy;

    private LocalDateTime usedTime;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
