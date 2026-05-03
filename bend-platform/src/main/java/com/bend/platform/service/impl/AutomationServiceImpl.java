package com.bend.platform.service.impl;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.StartAutomationRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.AutomationService;
import com.bend.platform.service.CredentialTokenService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.TaskService;
import com.bend.platform.util.UserContext;
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

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> startAutomation(StartAutomationRequest request, String userId, String merchantId) {
        String agentId = request.getAgentId();

        if (!AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            throw new BusinessException(400, "Agent不在线");
        }

        List<String> streamingAccountIds = request.getStreamingAccountIds();
        List<Map<String, Object>> results = new ArrayList<>();
        List<String> createdTaskIds = new ArrayList<>();

        for (String streamingAccountId : streamingAccountIds) {
            StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
            if (streamingAccount == null) {
                log.warn("娴佸獟浣撹处鍙蜂笉瀛樺湪: {}", streamingAccountId);
                continue;
            }

            if (!merchantId.equals(streamingAccount.getMerchantId())) {
                log.warn("娴佸獟浣撹处鍙蜂笉灞炰簬褰撳墠鍟嗘埛: {}", streamingAccountId);
                continue;
            }

            List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(streamingAccountId);

            Map<String, Object> taskParams = new HashMap<>();
            taskParams.put("streamingAccount", buildStreamingAccountInfo(streamingAccount));
            taskParams.put("gameAccounts", buildGameAccountsInfo(gameAccounts));
            taskParams.put("taskType", request.getTaskType());
            taskParams.put("merchantId", merchantId);

            Task task = new Task();
            task.setName("鑷姩鍖栦换鍔?" + streamingAccount.getName());
            task.setDescription(request.getDescription() != null ? request.getDescription() : "娴佸獟浣撹处鍙疯嚜鍔ㄥ寲浠诲姟");
            task.setType(request.getTaskType());
            task.setTargetAgentId(agentId);
            task.setStreamingAccountId(streamingAccountId);
            task.setPriority(request.getPriority() != null ? request.getPriority() : 0);
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

            log.info("鍒涘缓鑷姩鍖栦换鍔℃垚鍔?- 娴佸獟浣撹处鍙? {}, Agent: {}, TaskId: {}",
                streamingAccount.getName(), agentId, created.getId());
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

        log.info("鍋滄鑷姩鍖栦换鍔?- 娴佸獟浣撹处鍙? {}", streamingAccountId);
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

    private String toJson(Map<String, Object> data) {
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            return mapper.writeValueAsString(data);
        } catch (Exception e) {
            log.error("杞崲JSON澶辫触", e);
            return "{}";
        }
    }
}
