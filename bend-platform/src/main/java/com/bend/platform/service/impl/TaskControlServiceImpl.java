package com.bend.platform.service.impl;

import com.bend.platform.dto.StartStreamingRequest;
import com.bend.platform.dto.StartTaskAutomationRequest;
import com.bend.platform.dto.TaskPauseRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.StreamingSession;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskEvent;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.enums.AccountStatusEnum;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.*;
import com.bend.platform.service.TaskEventService;
import com.bend.platform.util.PlatformTypeUtil;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class TaskControlServiceImpl implements TaskControlService {

    private final TaskService taskService;
    private final TaskMapper taskMapper;
    private final StreamingSessionService streamingSessionService;
    private final StreamingAccountService streamingAccountService;
    private final TaskGameAccountStatusService statusService;
    private final TaskExecutorService taskExecutorService;
    private final AgentLoadControlService loadControlService;
    private final GameAccountService gameAccountService;
    private final XboxHostService xboxHostService;
    private final CredentialTokenService credentialTokenService;
    private final TaskEventService taskEventService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> startStreaming(String streamingAccountId, StartStreamingRequest request,
                                                String userId, String merchantId) {
        String agentId = request.getAgentId();
        if (agentId == null || agentId.isBlank()) {
            throw new BusinessException(400, "agentId不能为空");
        }
        if (!AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            throw new BusinessException(400, "Agent不在线");
        }
        if (!loadControlService.canAcceptTask(agentId)) {
            throw new BusinessException(400, "Agent已达到最大并发任务数");
        }

        StreamingAccount streamingAccount = streamingAccountService.findById(streamingAccountId);
        if (streamingAccount == null || !merchantId.equals(streamingAccount.getMerchantId())) {
            throw new BusinessException(404, "流媒体账号不存在");
        }
        if (taskService.hasRunningTask(streamingAccountId)) {
            throw new BusinessException(400, "该流媒体账号已有运行中的任务");
        }

        List<GameAccount> gameAccounts = gameAccountService.findByStreamingIdWithCredentials(streamingAccountId);
        if (request.getGameAccountIds() != null && !request.getGameAccountIds().isEmpty()) {
            Set<String> selected = new HashSet<>(request.getGameAccountIds());
            gameAccounts = gameAccounts.stream().filter(ga -> selected.contains(ga.getId())).toList();
        }

        XboxHost selectedHost = null;
        if (request.getXboxHostId() != null && !request.getXboxHostId().isBlank()) {
            selectedHost = xboxHostService.findById(request.getXboxHostId());
        }

        Map<String, Object> taskParams = buildStreamingTaskParams(
                streamingAccount, gameAccounts, selectedHost, merchantId);

        Task task = new Task();
        task.setName("串流任务-" + streamingAccount.getName());
        task.setDescription(request.getDescription());
        task.setType("automation");
        task.setTargetAgentId(agentId);
        task.setStreamingAccountId(streamingAccountId);
        task.setXboxHostId(selectedHost != null ? selectedHost.getId() : request.getXboxHostId());
        task.setCreatedBy(userId);
        task.setStatus("pending");
        task.setGameActionPending(true);
        task.setSessionPhase("opening");
        task.setWindowVisible(true);
        task.setTimeoutSeconds(3600);
        try {
            task.setParams(objectMapper.writeValueAsString(taskParams));
        } catch (Exception e) {
            task.setParams("{}");
        }

        Task created = taskService.create(task);
        StreamingSession session = streamingSessionService.createForTask(created, merchantId);

        created.setSessionId(session.getId());
        created.setSessionPhase("opening");
        taskMapper.updateById(created);

        streamingAccountService.updateTaskStatus(streamingAccountId, AccountStatusEnum.BUSY.getCode());
        streamingAccountService.updateAgentId(streamingAccountId, agentId);

        for (GameAccount ga : gameAccounts) {
            gameAccountService.updateStatus(ga.getId(), AccountStatusEnum.BUSY.getCode());
            gameAccountService.updateAgentId(ga.getId(), agentId);
        }

        taskExecutorService.executeTask(created);

        Map<String, Object> result = new HashMap<>();
        result.put("taskId", created.getId());
        result.put("sessionId", session.getId());
        result.put("phase", "opening");
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> startAutomation(String taskId, StartTaskAutomationRequest request, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        if (!"ready".equalsIgnoreCase(task.getSessionPhase())
                && !Boolean.TRUE.equals(task.getGameActionPending())) {
            throw new BusinessException(400, "任务尚未就绪，无法开始自动化");
        }

        task.setGameActionType(request.getGameActionType());
        task.setGameActionPending(false);
        task.setSessionPhase("automating");
        taskMapper.updateById(task);

        StreamingSession session = streamingSessionService.findByTaskId(taskId);
        if (session != null) {
            streamingSessionService.lockGameAction(session.getId(), request.getGameActionType());
        }

        sendTaskControl(task, "start_game_automation", Map.of(
                "gameActionType", request.getGameActionType()));

        Map<String, Object> result = new HashMap<>();
        result.put("taskId", taskId);
        result.put("gameActionType", request.getGameActionType());
        result.put("phase", "automating");
        return result;
    }

    @Override
    public void pauseTask(String taskId, TaskPauseRequest request, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        String mode = request.getMode() != null ? request.getMode() : "immediate";
        task.setPauseMode(mode);
        task.setStatus("paused");
        task.setSessionPhase("paused_" + mode);
        taskMapper.updateById(task);
        sendTaskControl(task, "pause", Map.of("mode", mode));
    }

    @Override
    public void resumeTask(String taskId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        task.setPauseMode(null);
        task.setStatus("running");
        if (Boolean.TRUE.equals(task.getGameActionPending())) {
            task.setSessionPhase("ready");
        } else {
            task.setSessionPhase("automating");
        }
        taskMapper.updateById(task);
        sendTaskControl(task, "resume", Map.of());
    }

    @Override
    public List<TaskEvent> getTaskEvents(String taskId, String merchantId, int limit) {
        return taskEventService.listByTaskIdForMerchant(taskId, merchantId, limit);
    }

    @Override
    public void cancelTask(String taskId, String merchantId) {
        terminateTask(taskId, merchantId);
    }

    @Override
    public void terminateTask(String taskId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        taskExecutorService.cancelTask(taskId);
        task.setStatus("cancelled");
        task.setSessionPhase("closed");
        task.setWindowVisible(false);
        taskMapper.updateById(task);
        StreamingSession session = streamingSessionService.findByTaskId(taskId);
        if (session != null) {
            streamingSessionService.closeSession(session.getId(), "closed");
        }
        sendTaskControl(task, "terminate", Map.of("closeWindow", true));
    }

    @Override
    public void windowControl(String taskId, String action, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        boolean visible = "show".equals(action);
        task.setWindowVisible(visible);
        taskMapper.updateById(task);
        sendTaskControl(task, "window_" + action, Map.of());
    }

    @Override
    public void skipGameAccount(String taskId, String gameAccountId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        statusService.updateStatus(taskId, gameAccountId, "skipped");
        sendTaskControl(task, "skip_game_account", Map.of("gameAccountId", gameAccountId));
    }

    @Override
    public void reconnectStream(String taskId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        sendTaskControl(task, "reconnect_stream", Map.of());
    }

    @Override
    public Map<String, Object> getTaskDetail(String taskId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        StreamingSession session = streamingSessionService.findByTaskId(taskId);
        List<TaskGameAccountStatus> statuses = statusService.findByTaskId(taskId);
        populateGameAccountDisplayNames(statuses);

        Map<String, Object> detail = new HashMap<>();
        detail.put("task", task);
        detail.put("session", session);
        detail.put("gameAccountStatuses", statuses);
        return detail;
    }

    private void populateGameAccountDisplayNames(List<TaskGameAccountStatus> statuses) {
        if (statuses == null || statuses.isEmpty()) {
            return;
        }
        for (TaskGameAccountStatus status : statuses) {
            if (!StringUtils.hasText(status.getGameAccountId())) {
                continue;
            }
            GameAccount account = gameAccountService.findById(status.getGameAccountId());
            if (account == null) {
                status.setGameAccountName(status.getGameAccountId());
                continue;
            }
            String displayName = account.getGameName();
            if (!StringUtils.hasText(displayName)) {
                displayName = account.getEmail();
            }
            if (!StringUtils.hasText(displayName)) {
                displayName = account.getId();
            }
            status.setGameAccountName(displayName);
        }
    }

    @Override
    public List<Map<String, Object>> getActiveTasks(String agentId, String merchantId) {
        List<Task> tasks = taskService.findByAgentId(agentId);
        List<Map<String, Object>> active = new ArrayList<>();
        for (Task task : tasks) {
            if (!merchantId.equals(task.getMerchantId())) {
                continue;
            }
            if ("running".equals(task.getStatus()) || "paused".equals(task.getStatus())
                    || Boolean.TRUE.equals(task.getGameActionPending())) {
                Map<String, Object> item = new HashMap<>();
                item.put("taskId", task.getId());
                item.put("id", task.getId());
                item.put("status", task.getStatus());
                item.put("streamingAccountId", task.getStreamingAccountId());
                item.put("sessionPhase", task.getSessionPhase());
                item.put("pauseMode", task.getPauseMode());
                item.put("windowVisible", task.getWindowVisible());
                item.put("gameActionType", task.getGameActionType());
                item.put("gameActionPending", task.getGameActionPending());
                active.add(item);
            }
        }
        return active;
    }

    private Task requireTask(String taskId, String merchantId) {
        Task task = taskService.findById(taskId);
        if (task == null || !merchantId.equals(task.getMerchantId())) {
            throw new BusinessException(404, "任务不存在");
        }
        return task;
    }

    private Map<String, Object> buildStreamingTaskParams(
            StreamingAccount account,
            List<GameAccount> gameAccounts,
            XboxHost host,
            String merchantId) {
        Map<String, Object> params = new HashMap<>();
        params.put("phase", "streaming_only");
        params.put("merchantId", merchantId);
        params.put("platform", PlatformTypeUtil.normalizeOrDefault(account.getPlatform()));
        params.put("autoMatchHost", host == null);
        params.put("streamingAccount", buildStreamingInfo(account));
        params.put("gameAccounts", buildGameAccountsInfo(gameAccounts));
        if (host != null) {
            params.put("host", buildHostInfo(host));
            params.put("xboxInfo", buildHostInfo(host));
        }
        return params;
    }

    private Map<String, Object> buildStreamingInfo(StreamingAccount account) {
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
            info.put("gameName", ga.getGameName());
            info.put("email", ga.getEmail());
            if (ga.getPositionIndex() != null) {
                info.put("positionIndex", ga.getPositionIndex());
            }
            if (Boolean.TRUE.equals(ga.getProfileBound())) {
                info.put("profileBound", true);
            }
            info.put("passwordToken", credentialTokenService.generateToken(
                    "game_account:" + ga.getId(), ga.getPasswordEncrypted()));
            result.add(info);
        }
        return result;
    }

    private Map<String, Object> buildHostInfo(XboxHost host) {
        Map<String, Object> info = new HashMap<>();
        info.put("id", host.getId());
        info.put("name", host.getName());
        info.put("ipAddress", host.getIpAddress());
        info.put("liveId", host.getLiveId());
        return info;
    }

    private void sendTaskControl(Task task, String action, Map<String, Object> extra) {
        Map<String, Object> data = new HashMap<>(extra);
        data.put("taskId", task.getId());
        data.put("action", action);
        AgentWebSocketEndpoint.sendTaskControlToAgent(task.getTargetAgentId(), data);
    }
}
