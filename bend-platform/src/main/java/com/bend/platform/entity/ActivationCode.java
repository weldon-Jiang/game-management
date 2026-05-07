package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 激活码实体类
 * 代表一个具体的激活码
 * 继承批次的订阅类型信息
 */
@Data
@TableName("activation_code")
public class ActivationCode {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;
    private String batchId;
    private String code;
    private String status;
    private String usedBy;
    private LocalDateTime usedTime;
    private LocalDateTime expireTime;
    private LocalDateTime generatedTime;

    // 订阅类型：points-点数、account-游戏账号、window-窗口、host-主机（继承自批次）
    private String subscriptionType;
    // 定向订阅目标ID（继承自批次）
    private String targetId;
    // 定向订阅目标名称（继承自批次）
    private String targetName;
    // 订阅时长（天数，继承自批次）
    private Integer durationDays;
    // 每日价格（继承自批次）
    private java.math.BigDecimal dailyPrice;
    // 点数数量（继承自批次）
    private Integer pointsAmount;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}