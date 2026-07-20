package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 分控汇总指标(总控库,分控定时上报)
 */
@Data
@TableName("tenant_metrics")
public class TenantMetrics {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String licenseKey;

    /** 分控上报时间(分控本地) */
    private LocalDateTime reportAt;

    /** 总控接收时间 */
    private LocalDateTime receivedAt;

    private Integer onlineAgentCount;
    private Integer totalAgentCount;
    private Integer todayTaskCount;
    private Integer runningTaskCount;
    private Integer todayPointsConsumed;
    private Integer balance;
    private String licenseStatus;
    private String platformVersion;
    private String extra;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
