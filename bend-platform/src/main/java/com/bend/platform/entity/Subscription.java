package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("subscription")
public class Subscription {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String userId;

    private String activationCodeId;

    private String subscriptionType;

    private String boundResourceType;

    private String boundResourceIds;

    private String boundResourceNames;

    private LocalDateTime startTime;

    private LocalDateTime endTime;

    private Integer originalPrice;

    private Integer discountPrice;

    private String status;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
