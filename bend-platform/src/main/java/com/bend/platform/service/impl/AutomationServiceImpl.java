package com.bend.platform.service.impl;

import com.bend.platform.dto.StartAutomationRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.enums.PlatformType;
import com.bend.platform.enums.AccountStatusEnum;
import com.bend.platform.enums.GameActionType;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.*;
import com.bend.platform.util.PlatformTypeUtil;
import com.bend.platform.util.StreamingTaskConflictMessage;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 自动化任务编排：校验 Agent/计费/账号状态，创建任务并异步下发 Agent。
 * <p>
 * 入口 {@link #startAutomation} 对应前端「开始自动化」；批量处理流媒体账号，
 * 单账号失败不影响同批其他账号。扣费与账号 busy 状态在同一事务内完成。
 */
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
    private final StreamingAccountHostBindingService hostBindingService;
    private final AutomationUsageService automationUsageService;
    private final TaskExecutorService taskExecutorService;
    private final AgentLoadControlService loadControlService;
    private final TaskWsDispatchService taskWsDispatchService;

    /**
     * 批量启动自动化：逐流媒体账号校验 → 扣点 → 创建 Task → executeTaskAsync。
     * 前置：Agent 在线、未超并发、Redis 可用、无活跃任务、游戏账号非 busy、计费通过。
     */
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

        if (!credentialTokenService.isReady()) {
            throw new BusinessException(503, "凭证令牌服务不可用，无法启动自动化。");
        }
        agentInstanceService.requireAgentOwnedByMerchant(agentId, merchantId);

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

            String platform = PlatformTypeUtil.normalizeOrDefault(streamingAccount.getPlatform());
            if (PlatformType.PLAYSTATION.getCode().equals(platform)) {
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("streamingAccountId", streamingAccountId);
                errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                errorResult.put("success", false);
                errorResult.put("message", ResultCode.System.PLATFORM_NOT_SUPPORTED.getMessage());
                results.add(errorResult);
                log.warn("自动化启动失败 - PlayStation 自动化尚未开放: {}", streamingAccount.getDisplayLabel());
                continue;
            }

            Task activeTask = taskService.findActiveTaskByStreamingAccountId(streamingAccountId);
            if (activeTask != null) {
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("streamingAccountId", streamingAccountId);
                errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                errorResult.put("success", false);
                errorResult.put("taskId", activeTask.getId());
                errorResult.put("agentId", activeTask.getTargetAgentId());
                String agentName = agentInstanceService.resolveDisplayName(activeTask.getTargetAgentId());
                errorResult.put("message", StreamingTaskConflictMessage.format(activeTask, agentName));
                results.add(errorResult);
                log.warn("自动化启动失败 - 流媒体账号已有运行中的任务: {}", streamingAccount.getDisplayLabel());
                continue;
            }

            List<GameAccount> gameAccounts = gameAccountService.findByStreamingIdWithCredentials(streamingAccountId);

            XboxHost selectedHost = null;
            boolean autoMatchHost = true;
            if (StringUtils.hasText(request.getHostId())) {
                try {
                    selectedHost = xboxHostService.requireForMerchant(request.getHostId(), merchantId);
                } catch (BusinessException ex) {
                    Map<String, Object> errorResult = new HashMap<>();
                    errorResult.put("streamingAccountId", streamingAccountId);
                    errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                    errorResult.put("success", false);
                    errorResult.put("message", "指定的主机不存在或无权访问");
                    results.add(errorResult);
                    continue;
                }
                if (!hostBindingService.hasActiveBinding(streamingAccountId, selectedHost.getId())) {
                    Map<String, Object> errorResult = new HashMap<>();
                    errorResult.put("streamingAccountId", streamingAccountId);
                    errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                    errorResult.put("success", false);
                    errorResult.put("message", "指定的主机未绑定到该流媒体账号");
                    results.add(errorResult);
                    continue;
                }
                if (!platform.equals(PlatformTypeUtil.normalizeOrDefault(selectedHost.getPlatform()))) {
                    Map<String, Object> errorResult = new HashMap<>();
                    errorResult.put("streamingAccountId", streamingAccountId);
                    errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                    errorResult.put("success", false);
                    errorResult.put("message", "主机平台与流媒体账号不一致");
                    results.add(errorResult);
                    continue;
                }
                if (Boolean.TRUE.equals(selectedHost.getLocked())) {
                    Map<String, Object> errorResult = new HashMap<>();
                    errorResult.put("streamingAccountId", streamingAccountId);
                    errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                    errorResult.put("success", false);
                    errorResult.put("message", "指定的主机已被锁定");
                    results.add(errorResult);
                    continue;
                }
                autoMatchHost = false;
            }

            List<XboxHost> xboxHostsForBilling = selectedHost != null
                    ? List.of(selectedHost) : List.of();

            // 校验游戏账号状态（是否有忙碌中的账号）
            List<String> busyGameAccountNames = new ArrayList<>();
            for (GameAccount ga : gameAccounts) {
                if (AccountStatusEnum.BUSY.getCode().equals(ga.getStatus())) {
                    busyGameAccountNames.add(ga.getGameName());
                }
            }
            if (!busyGameAccountNames.isEmpty()) {
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("streamingAccountId", streamingAccountId);
                errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                errorResult.put("success", false);
                errorResult.put("message", "以下游戏账号正在忙碌中: " + String.join(", ", busyGameAccountNames));
                results.add(errorResult);
                log.warn("自动化启动失败 - 游戏账号忙碌中: {}", busyGameAccountNames);
                continue;
            }

            Map<String, Object> validationResult = automationUsageService.validateAndCalculatePoints(
                    merchantId, streamingAccountId, gameAccounts, xboxHostsForBilling);

            if (!Boolean.TRUE.equals(validationResult.get("canStart"))) {
                String message = (String) validationResult.get("message");
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("streamingAccountId", streamingAccountId);
                errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                errorResult.put("success", false);
                errorResult.put("message", message);
                results.add(errorResult);
                log.warn("自动化启动失败 - merchantId: {}, account: {}, reason: {}",
                        merchantId, streamingAccount.getDisplayLabel(), message);
                continue;
            }

            // 构建任务参数（支持选择特定游戏账号）
            List<GameAccount> selectedGameAccounts = gameAccounts;
            if (request.getSelectedGameAccountIds() != null && !request.getSelectedGameAccountIds().isEmpty()) {
                // 根据选择的游戏账号ID过滤
                Set<String> selectedIds = new HashSet<>(request.getSelectedGameAccountIds());
                selectedGameAccounts = gameAccounts.stream()
                        .filter(ga -> selectedIds.contains(ga.getId()))
                        .collect(Collectors.toList());
                if (selectedGameAccounts.isEmpty()) {
                    Map<String, Object> errorResult = new HashMap<>();
                    errorResult.put("streamingAccountId", streamingAccountId);
                    errorResult.put("streamingAccountName", streamingAccount.getDisplayLabel());
                    errorResult.put("success", false);
                    errorResult.put("message", "未找到指定的游戏账号");
                    results.add(errorResult);
                    continue;
                }
            }

            Map<String, Object> taskParams = new HashMap<>();
            taskParams.put("platform", platform);
            taskParams.put("autoMatchHost", autoMatchHost);
            taskParams.put("host", selectedHost != null ? buildHostInfo(selectedHost) : null);
            taskParams.put("streamingAccount", buildStreamingAccountInfo(streamingAccount));
            taskParams.put("gameAccounts", buildGameAccountsInfo(selectedGameAccounts));
            if (selectedHost != null) {
                taskParams.put("xboxHosts", buildXboxHostsInfo(List.of(selectedHost)));
                taskParams.put("xboxInfo", buildHostInfo(selectedHost));
            }
            taskParams.put("gameActionType", request.getGameActionType());
            taskParams.put("merchantId", merchantId);

            Task task = new Task();
            task.setName("自动化任务-" + streamingAccount.getDisplayLabel());
            task.setDescription(request.getDescription() != null ? request.getDescription() : "流媒体账号自动化任务");
            task.setType("automation");
            task.setTargetAgentId(agentId);
            task.setStreamingAccountId(streamingAccountId);
            task.setGamePlatform(platform);
            if (selectedHost != null) {
                task.setXboxHostId(selectedHost.getId());
            }
            task.setPriority(request.getPriority() != null ? request.getPriority() : 0);
            task.setParams(toJson(taskParams));
            task.setCreatedBy(userId);
            task.setStatus("pending");
            task.setTimeoutSeconds(3600);
            
            // 设置游戏操作类型，默认为SQB模式
            String gameActionType = request.getGameActionType();
            if (gameActionType == null || gameActionType.isEmpty()) {
                gameActionType = GameActionType.SQUAD_BATTLE.getCode();
            }
            task.setGameActionType(gameActionType);

            Task created = taskService.create(task);
            createdTaskIds.add(created.getId());

            automationUsageService.deductPointsAndRecordUsage(
                    merchantId, userId, created.getId(),
                    streamingAccountId, streamingAccount.getDisplayLabel(),
                    selectedGameAccounts.size(), xboxHostsForBilling.size(), validationResult);

            // 更新流媒体账号状态为忙碌
            streamingAccountService.updateTaskStatus(streamingAccountId, AccountStatusEnum.BUSY.getCode());
            streamingAccountService.updateAgentId(streamingAccountId, agentId);
            
            // 更新游戏账号状态为忙碌
            for (GameAccount ga : selectedGameAccounts) {
                gameAccountService.updateStatus(ga.getId(), AccountStatusEnum.BUSY.getCode());
                gameAccountService.updateAgentId(ga.getId(), agentId);
            }

            final Task asyncTask = created;
            taskWsDispatchService.dispatchAfterCommit(() -> taskExecutorService.executeTaskAsync(asyncTask));

            Map<String, Object> result = new HashMap<>();
            result.put("streamingAccountId", streamingAccountId);
            result.put("streamingAccountName", streamingAccount.getDisplayLabel());
            result.put("taskId", created.getId());
            result.put("gameAccountsCount", selectedGameAccounts.size());
            result.put("success", true);
            result.put("pointsDeducted", validationResult.get("totalPoints"));
            results.add(result);

            log.info("创建自动化任务成功 - 流媒体账号: {}, Agent: {}, TaskId: {}, Points: {}",
                streamingAccount.getDisplayLabel(), agentId, created.getId(), validationResult.get("totalPoints"));
        }

        Map<String, Object> response = new HashMap<>();
        response.put("total", results.size());
        response.put("taskIds", createdTaskIds);
        response.put("results", results);
        
        boolean allFailed = results.stream().allMatch(r -> !Boolean.TRUE.equals(r.get("success")));
        response.put("success", !allFailed && !createdTaskIds.isEmpty());
        response.put("message", createdTaskIds.isEmpty() ? "没有成功创建任何任务" : "成功创建" + createdTaskIds.size() + "个任务");

        return response;
    }

    /**
     * 停止指定流媒体账号的自动化：WS 通知 Agent、释放账号 busy、取消关联 Task。
     */
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

        // 更新流媒体账号状态为空闲
        streamingAccountService.updateTaskStatus(streamingAccountId, AccountStatusEnum.IDLE.getCode());
        streamingAccountService.updateAgentId(streamingAccountId, null);
        
        // 更新游戏账号状态为空闲
        List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(streamingAccountId);
        for (GameAccount ga : gameAccounts) {
            gameAccountService.updateStatus(ga.getId(), AccountStatusEnum.IDLE.getCode());
            gameAccountService.updateAgentId(ga.getId(), null);
        }
        
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
        info.put("name", account.getDisplayLabel());
        info.put("email", account.getEmail());
        info.put("platform", PlatformTypeUtil.normalizeOrDefault(account.getPlatform()));
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
            info.put("gameName", ga.getGameName());
            info.put("email", ga.getEmail());
            info.put("isPrimary", ga.getIsPrimary());
            info.put("dailyMatchLimit", ga.getDailyMatchLimit());
            info.put("todayMatchCount", ga.getTodayMatchCount());
            info.put("cooldownHours", ga.getCooldownHours());
            info.put("totalCoins", ga.getTotalCoins());
            info.put("todayCoins", ga.getTodayCoins());
            info.put("drLevel", ga.getDrLevel());
            info.put("passwordToken", credentialTokenService.generateToken(
                "game_account:" + ga.getId(), ga.getPasswordEncrypted()));
            result.add(info);
        }
        return result;
    }

    private Map<String, Object> buildHostInfo(XboxHost host) {
        Map<String, Object> info = new HashMap<>();
        info.put("id", host.getId());
        info.put("xboxId", host.getXboxId());
        info.put("name", host.getName());
        info.put("ipAddress", host.getIpAddress());
        info.put("platform", PlatformTypeUtil.normalizeOrDefault(host.getPlatform()));
        info.put("boundGamertag", host.getBoundGamertag());
        return info;
    }

    private List<Map<String, Object>> buildXboxHostsInfo(List<XboxHost> xboxHosts) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (XboxHost xbox : xboxHosts) {
            result.add(buildHostInfo(xbox));
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
