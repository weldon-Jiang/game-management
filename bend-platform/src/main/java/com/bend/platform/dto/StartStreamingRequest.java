package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

@Data
public class StartStreamingRequest {

    private String agentId;
    private String xboxHostId;
    private List<String> gameAccountIds;
    private String description;
}
