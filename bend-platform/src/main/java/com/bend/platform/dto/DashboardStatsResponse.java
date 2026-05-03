package com.bend.platform.dto;

import lombok.Data;

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
