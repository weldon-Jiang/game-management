package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 更新 Agent 显示名称请求
 */
@Data
public class UpdateAgentNameRequest {

    @NotBlank(message = "Agent名称不能为空")
    @Size(max = 64, message = "Agent名称不能超过64个字符")
    private String agentName;
}
