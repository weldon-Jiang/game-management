package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.StartAutomationRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.TaskService;
import com.bend.platform.util.UserContext;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * 自动化控制器
 *
 * 功能说明：
 * - 管理Xbox流媒体自动化任务的启动和停止
 * - 支持批量启动多个流媒体账号的自动化任务
 * - 提供自动化任务状态查询
 *
 * 核心流程：
 * 1. 根据流媒体账号列表创建对应的自动化任务
 * 2. 通过WebSocket将任务下发到目标Agent
 * 3. 实时跟踪任务执行状态
 *
 * 主要功能：
 * - 启动自动化：根据流媒体账号列表创建并下发任务
 * - 停止自动化：停止指定账号的自动化任务
 * - 查询状态：查看自动化任务的执行状态
 */
@Slf4j
@RestController
@RequestMapping("/api/automation")
@RequiredArgsConstructor
public class StartAutomationController {

    private final TaskService taskService;
    private final StreamingAccountService streamingAccountService;
    private final GameAccountService gameAccountService;
    private final AgentInstanceService agentInstanceService;

    /**
     * 启动自动化任务
     * 根据流媒体账号列表批量创建任务并下发到Agent
     *
     * @param request 启动自动化请求（包含AgentID和流媒体账号ID列表）
     * @return 创建的任务统计信息
     */
    @PostMapping("/start")
    public ApiResponse<Map<String, Object>> startAutomation(@RequestBody StartAutomationRequest request) {
        String userId = UserContext.getUserId();
        String merchantId = UserContext.getMerchantId();

        if (merchantId == null) {
            return ApiResponse.error(400, "无法获取商户信息");
        }

        String agentId = request.getAgentId();

        if (!AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            return ApiResponse.error(400, "Agent不在线");
        }

        List<String> streamingAccountIds = request.getStreamingAccountIds();
        List<Map<String, Object>> results = new ArrayList<>();
        List<String> createdTaskIds = new ArrayList<>();

        for (String streamingAccountId : streamingAccountIds) {
            StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
            if (streamingAccount == null) {
                log.warn("流媒体账号不存在: {}", streamingAccountId);
                continue;
            }

            if (!merchantId.equals(streamingAccount.getMerchantId())) {
                log.warn("流媒体账号不属于当前商户: {}", streamingAccountId);
                continue;
            }

            List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(streamingAccountId);

            Map<String, Object> taskParams = new HashMap<>();
            taskParams.put("streamingAccount", buildStreamingAccountInfo(streamingAccount));
            taskParams.put("gameAccounts", buildGameAccountsInfo(gameAccounts));
            taskParams.put("taskType", request.getTaskType());
            taskParams.put("merchantId", merchantId);

            Task task = new Task();
            task.setName("自动化任务-" + streamingAccount.getName());
            task.setDescription(request.getDescription() != null ? request.getDescription() : "流媒体账号自动化任务");
            task.setType(request.getTaskType());
            task.setTargetAgentId(agentId);
            task.setStreamingAccountId(streamingAccountId);
            task.setPriority(request.getPriority() != null ? String.valueOf(request.getPriority()) : "0");
            task.setParams(toJson(taskParams));
            task.setCreatedBy(userId);
            task.setStatus("pending");

            Task created = taskService.create(task);
            createdTaskIds.add(created.getId());

            streamingAccountService.updateAgentId(streamingAccountId, agentId);
            for (GameAccount ga : gameAccounts) {
                gameAccountService.updateAgentId(ga.getId(), agentId);
            }

            Map<String, Object> taskData = new HashMap<>();
            taskData.put("taskId", created.getId());
            taskData.put("name", created.getName());
            taskData.put("type", created.getType());
            taskData.put("params", taskParams);

            AgentWebSocketEndpoint.sendTaskToAgent(agentId, created.getId(), taskData);

            Map<String, Object> result = new HashMap<>();
            result.put("streamingAccountId", streamingAccountId);
            result.put("streamingAccountName", streamingAccount.getName());
            result.put("taskId", created.getId());
            result.put("gameAccountsCount", gameAccounts.size());
            results.add(result);

            log.info("创建自动化任务成功 - 流媒体账号: {}, Agent: {}, TaskId: {}",
                streamingAccount.getName(), agentId, created.getId());
        }

        Map<String, Object> response = new HashMap<>();
        response.put("total", results.size());
        response.put("taskIds", createdTaskIds);
        response.put("results", results);

        return ApiResponse.success("已创建" + results.size() + "个自动化任务", response);
    }

    /**
     * 停止自动化任务
     *
     * @param streamingAccountId 流媒体账号ID
     * @return 操作结果
     */
    @PostMapping("/stop/{streamingAccountId}")
    public ApiResponse<Void> stopAutomation(@PathVariable String streamingAccountId) {
        String merchantId = UserContext.getMerchantId();
        if (merchantId == null) {
            return ApiResponse.error(400, "无法获取商户信息");
        }

        StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
        if (streamingAccount == null) {
            return ApiResponse.error(404, "流媒体账号不存在");
        }

        if (!merchantId.equals(streamingAccount.getMerchantId())) {
            return ApiResponse.error(403, "无权操作此账号");
        }

        String agentId = streamingAccount.getAgentId();
        if (agentId != null && AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            Map<String, Object> stopData = new HashMap<>();
            stopData.put("action", "stop");
            stopData.put("streamingAccountId", streamingAccountId);
            AgentWebSocketEndpoint.sendMessageToAgent(agentId, "automation_control", stopData);
        }

        streamingAccountService.updateAgentId(streamingAccountId, null);
        taskService.cancelByStreamingAccountId(streamingAccountId);

        log.info("停止自动化任务 - 流媒体账号: {}", streamingAccountId);
        return ApiResponse.success("已停止自动化任务", null);
    }

    /**
     * 获取自动化任务状态
     *
     * @param streamingAccountId 流媒体账号ID
     * @return 自动化状态信息
     */
    @GetMapping("/status/{streamingAccountId}")
    public ApiResponse<Map<String, Object>> getAutomationStatus(@PathVariable String streamingAccountId) {
        String merchantId = UserContext.getMerchantId();
        if (merchantId == null) {
            return ApiResponse.error(400, "无法获取商户信息");
        }

        StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
        if (streamingAccount == null) {
            return ApiResponse.error(404, "流媒体账号不存在");
        }

        if (!merchantId.equals(streamingAccount.getMerchantId())) {
            return ApiResponse.error(403, "无权操作此账号");
        }

        Map<String, Object> status = new HashMap<>();
        status.put("streamingAccountId", streamingAccountId);
        status.put("agentId", streamingAccount.getAgentId());
        status.put("agentOnline", streamingAccount.getAgentId() != null &&
            AgentWebSocketEndpoint.isAgentOnline(streamingAccount.getAgentId()));
        status.put("status", streamingAccount.getStatus());

        List<Task> tasks = taskService.findByStreamingAccountId(streamingAccountId);
        status.put("tasks", tasks);

        return ApiResponse.success(status);
    }

    /**
     * 构建流媒体账号信息
     *
     * @param account 流媒体账号
     * @return 账号信息Map
     */
    private Map<String, Object> buildStreamingAccountInfo(StreamingAccount account) {
        Map<String, Object> info = new HashMap<>();
        info.put("id", account.getId());
        info.put("name", account.getName());
        info.put("email", account.getEmail());
        info.put("passwordEncrypted", account.getPasswordEncrypted());
        info.put("authCode", account.getAuthCode());
        return info;
    }

    /**
     * 构建游戏账号列表信息
     *
     * @param accounts 游戏账号列表
     * @return 游戏账号信息列表
     */
    private List<Map<String, Object>> buildGameAccountsInfo(List<GameAccount> accounts) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (GameAccount ga : accounts) {
            Map<String, Object> info = new HashMap<>();
            info.put("id", ga.getId());
            info.put("name", ga.getName());
            info.put("xboxGamertag", ga.getXboxGamertag());
            info.put("xboxLiveEmail", ga.getXboxLiveEmail());
            info.put("xboxLivePasswordEncrypted", ga.getXboxLivePasswordEncrypted());
            info.put("isPrimary", ga.getIsPrimary());
            result.add(info);
        }
        return result;
    }

    /**
     * 对象转JSON字符串
     *
     * @param data 要转换的对象
     * @return JSON字符串
     */
    private String toJson(Map<String, Object> data) {
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            return mapper.writeValueAsString(data);
        } catch (Exception e) {
            log.error("转换JSON失败", e);
            return "{}";
        }
    }
}