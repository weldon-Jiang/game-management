package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 对已就绪串流任务启动 Step4 自动化（两阶段入口第二阶段）。
 */
@Data
public class StartTaskAutomationRequest {

    @NotBlank(message = "gameActionType不能为空")
    private String gameActionType;
}
