package com.bend.platform.dto;

import lombok.Data;

/**
 * 仪表盘统计汇总（平台管理员可见全量，商户侧按 merchantId 过滤）。
 */
@Data
public class DashboardStatsResponse {
    private Long merchantCount;
    private Long merchantUserCount;
    private Long streamingAccountCount;
    private Long gameAccountCount;
    private Long xboxHostCount;
    private Long taskCount;
    private Long runningTaskCount;
    private Long agentCount;
    private Long onlineAgentCount;
}
