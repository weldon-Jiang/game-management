package com.bend.platform.dto;

import lombok.Data;
import java.util.List;

@Data
public class StartAutomationRequest {
    private List<String> streamingAccountIds;
    private String agentId;
    private String taskType = "stream_control";
    private Integer priority = 0;
    private String description;
}
