package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class StartTaskAutomationRequest {

    @NotBlank(message = "gameActionType不能为空")
    private String gameActionType;
}
