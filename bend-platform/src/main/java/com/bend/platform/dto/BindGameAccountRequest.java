package com.bend.platform.dto;

import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

@Data
public class BindGameAccountRequest {
    @NotEmpty(message = "游戏账号ID列表不能为空")
    private List<String> gameAccountIds;
}
