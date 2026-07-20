package com.bend.platform.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 分控汇总指标上报请求
 *
 * <p>分控定时(每5-10min)POST 到总控 /api/tenant-metrics/report。
 * 用 licenseKey + licenseSecret 鉴权(复用 license 凭证)。
 */
@Data
public class TenantMetricsReport {

    private String licenseKey;
    private String licenseSecret;

    /** 分控上报时间(分控本地) */
    private LocalDateTime reportAt;

    private Integer onlineAgentCount;
    private Integer totalAgentCount;
    private Integer todayTaskCount;
    private Integer runningTaskCount;
    private Integer todayPointsConsumed;
    private Integer balance;
    private String licenseStatus;
    private String platformVersion;
    private String extra;
}
