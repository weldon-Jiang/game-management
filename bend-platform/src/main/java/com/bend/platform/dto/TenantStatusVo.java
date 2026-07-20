package com.bend.platform.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 分控在线状态(总控大盘用)
 *
 * <p>总控无法主动连分控,在线状态由分控最近的出站活动时间判断:
 * 取 license.last_verified_at(每30min) 与 最新 tenant_metrics.received_at(每5min) 的较大值,
 * 超过阈值(默认15min)未活动判离线。
 */
@Data
public class TenantStatusVo {
    private String merchantId;
    private String merchantName;
    private boolean online;
    /** 最近一次出站活动时间 */
    private LocalDateTime lastSeenAt;
    /** 活动来源: LICENSE_VERIFY / METRICS_REPORT / NONE */
    private String lastSeenSource;
    private String licenseStatus;
    private LocalDateTime licenseExpireAt;
    private Integer onlineAgents;
    private Integer todayTasks;
}
