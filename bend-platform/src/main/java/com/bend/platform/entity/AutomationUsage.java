package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 自动化使用记录实体
 * 记录启动自动化任务时的使用情况和扣点信息
 */
@Data
@TableName("automation_usage")
public class AutomationUsage {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String userId;

    private String taskId;

    private String streamingAccountId;

    private String streamingAccountName;

    private Integer gameAccountsCount;

    private Integer hostsCount;

    /**
     * 使用的资源类型：window/account/host
     */
    private String resourceType;

    private String resourceId;

    private String resourceName;

    /**
     * 扣点模式：per_use(按次) / monthly(包月)
     */
    private String chargeMode;

    private Integer pointsDeducted;

    /**
     * 关联的订阅ID（如果是包月模式）
     */
    private String subscriptionId;

    private LocalDateTime usageTime;

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
