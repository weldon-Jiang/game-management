package com.bend.platform.service.impl;

import com.bend.platform.dto.StartAutomationRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.*;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class AutomationServiceImpl implements AutomationService {

    private final TaskService taskService;
    private final StreamingAccountService streamingAccountService;
    private final GameAccountService gameAccountService;
    private final AgentInstanceService agentInstanceService;
    private final CredentialTokenService credentialTokenService;
    private final XboxHostService xboxHostService;
    private final AutomationUsageService automationUsageService;
    private final TaskExecutorService taskExecutorService;
    private final AgentLoadControlService loadControlService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> startAutomation(StartAutomationRequest request, String userId, String merchantId) {
        String agentId = request.getAgentId();

        if (!AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            throw new BusinessException(400, "Agent不在线");
        }

        if (!loadControlService.canAcceptTask(agentId)) {
            throw new BusinessException(400, "Agent已达到最大并发任务数，请稍后再试");
        }

        if (!credentialTokenService.isRedisEnabled()) {
            throw new BusinessException(503, "Redis未启用，无法启动自动化。请联系管理员启用Redis服务。");
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
            List<XboxHost> xboxHosts = xboxHostService.findByBoundStreamingAccountId(streamingAccountId);

            Map<String, Object> validationResult = automationUsageService.validateAndCalculatePoints(
                    merchantId, streamingAccountId, gameAccounts, xboxHosts);

            if (!Boolean.TRUE.equals(validationResult.get("canStart"))) {
                String message = (String) validationResult.get("message");
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("streamingAccountId", streamingAccountId);
                errorResult.put("streamingAccountName", streamingAccount.getName());
                errorResult.put("success", false);
                errorResult.put("message", message);
                results.add(errorResult);
                log.warn("自动化启动失败 - merchantId: {}, account: {}, reason: {}",
                        merchantId, streamingAccount.getName(), message);
                continue;
            }

            Map<String, Object> taskParams = new HashMap<>();
            taskParams.put("streamingAccount", buildStreamingAccountInfo(streamingAccount));
            taskParams.put("gameAccounts", buildGameAccountsInfo(gameAccounts));
            taskParams.put("xboxHosts", buildXboxHostsInfo(xboxHosts));
            taskParams.put("taskType", request.getTaskType());
            taskParams.put("merchantId", merchantId);

            Task task = new Task();
            task.setName("自动化任务-" + streamingAccount.getName());
            task.setDescription(request.getDescription() != null ? request.getDescription() : "流媒体账号自动化任务");
            task.setType(request.getTaskType());
            task.setTargetAgentId(agentId);
            task.setStreamingAccountId(streamingAccountId);
            task.setPriority(request.getPriority() != null ? request.getPriority() : 0);
            task.setParams(toJson(taskParams));
            task.setCreatedBy(userId);
            task.setStatus("pending");
            task.setTimeoutSeconds(3600);

            Task created = taskService.create(task);
            createdTaskIds.add(created.getId());

            automationUsageService.deductPointsAndRecordUsage(
                    merchantId, userId, created.getId(),
                    streamingAccountId, streamingAccount.getName(),
                    gameAccounts.size(), xboxHosts.size(), validationResult);

            streamingAccountService.updateAgentId(streamingAccountId, agentId);
            for (GameAccount ga : gameAccounts) {
                gameAccountService.updateAgentId(ga.getId(), agentId);
            }

            taskExecutorService.executeTaskAsync(created);

            Map<String, Object> result = new HashMap<>();
            result.put("streamingAccountId", streamingAccountId);
            result.put("streamingAccountName", streamingAccount.getName());
            result.put("taskId", created.getId());
            result.put("gameAccountsCount", gameAccounts.size());
            result.put("success", true);
            result.put("pointsDeducted", validationResult.get("totalPoints"));
            results.add(result);

            log.info("创建自动化任务成功 - 流媒体账号: {}, Agent: {}, TaskId: {}, Points: {}",
                streamingAccount.getName(), agentId, created.getId(), validationResult.get("totalPoints"));
        }

        Map<String, Object> response = new HashMap<>();
        response.put("total", results.size());
        response.put("taskIds", createdTaskIds);
        response.put("results", results);

        return response;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void stopAutomation(String streamingAccountId, String merchantId) {
        StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
        if (streamingAccount == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!merchantId.equals(streamingAccount.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
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
    }

    @Override
    public Map<String, Object> getAutomationStatus(String streamingAccountId, String merchantId) {
        StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
        if (streamingAccount == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!merchantId.equals(streamingAccount.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        Map<String, Object> status = new HashMap<>();
        status.put("streamingAccountId", streamingAccountId);
        status.put("agentId", streamingAccount.getAgentId());
        status.put("agentOnline", streamingAccount.getAgentId() != null &&
            AgentWebSocketEndpoint.isAgentOnline(streamingAccount.getAgentId()));
        status.put("status", streamingAccount.getStatus());

        List<Task> tasks = taskService.findByStreamingAccountId(streamingAccountId);
        status.put("tasks", tasks);

        return status;
    }

    private Map<String, Object> buildStreamingAccountInfo(StreamingAccount account) {
        Map<String, Object> info = new HashMap<>();
        info.put("id", account.getId());
        info.put("name", account.getName());
        info.put("email", account.getEmail());
        info.put("authCode", account.getAuthCode());
        info.put("passwordToken", credentialTokenService.generateToken(
            "streaming_account:" + account.getId(), account.getPasswordEncrypted()));
        return info;
    }

    private List<Map<String, Object>> buildGameAccountsInfo(List<GameAccount> accounts) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (GameAccount ga : accounts) {
            Map<String, Object> info = new HashMap<>();
            info.put("id", ga.getId());
            info.put("xboxGameName", ga.getXboxGameName());
            info.put("xboxLiveEmail", ga.getXboxLiveEmail());
            info.put("isPrimary", ga.getIsPrimary());
            info.put("passwordToken", credentialTokenService.generateToken(
                "game_account:" + ga.getId(), ga.getXboxLivePasswordEncrypted()));
            result.add(info);
        }
        return result;
    }

    private List<Map<String, Object>> buildXboxHostsInfo(List<XboxHost> xboxHosts) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (XboxHost xbox : xboxHosts) {
            Map<String, Object> info = new HashMap<>();
            info.put("id", xbox.getId());
            info.put("xboxId", xbox.getXboxId());
            info.put("name", xbox.getName());
            info.put("ipAddress", xbox.getIpAddress());
            info.put("boundGamertag", xbox.getBoundGamertag());
            result.add(info);
        }
        return result;
    }

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
