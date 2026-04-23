package com.bend.platform.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;
import java.util.List;

@Data
public class StartAutomationRequest {

    @NotNull(message = "流媒体账号列表不能为空")
    @Size(min = 1, max = 100, message = "单次批量操作不超过100条")
    private List<String> streamingAccountIds;

    @NotBlank(message = "Agent ID不能为空")
    private String agentId;

    @NotBlank(message = "任务类型不能为空")
    private String taskType = "stream_control";

    @Min(value = 0, message = "优先级最小值为0")
    @Max(value = 99, message = "优先级最大值为99")
    private Integer priority = 0;

    @Size(max = 500, message = "描述最大500字符")
    private String description;
}