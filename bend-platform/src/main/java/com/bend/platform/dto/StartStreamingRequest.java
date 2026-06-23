package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

/**
 * 启动串流任务请求（两阶段入口第一阶段：Step1–3 串流准备）。
 */
@Data
public class StartStreamingRequest {

    private String agentId;
    private String xboxHostId;
    private List<String> gameAccountIds;
    /**
     * 在本 Xbox 主机上需走「添加新用户」流程的游戏账号 ID（任务级，不写入库表）。
     */
    private List<String> newOnHostGameAccountIds;
    private String description;
}
