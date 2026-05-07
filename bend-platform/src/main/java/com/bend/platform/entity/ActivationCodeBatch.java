package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 激活码批次实体类
 * 代表一批生成的激活码
 * 支持多种订阅类型：points（点数）、account（游戏账号）、window（窗口）、host（主机）
 */
@Data
@TableName("activation_code_batch")
public class ActivationCodeBatch {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;
    private String batchName;
    private Integer totalCount;
    private Integer usedCount;
    private Integer remainingCount;
    private Integer points;
    private Integer pointsAmount;
    private LocalDateTime expireTime;
    private String status;

    // 订阅类型：points-点数、account-游戏账号、window-窗口、host-主机
    private String subscriptionType;
    // 定向订阅目标ID（游戏账号/窗口/主机ID）
    private String targetId;
    // 定向订阅目标名称
    private String targetName;
    // 订阅时长（天数）
    private Integer durationDays;
    // 每日价格
    private BigDecimal dailyPrice;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}