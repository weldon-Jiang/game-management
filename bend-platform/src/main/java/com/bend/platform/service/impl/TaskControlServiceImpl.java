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
import com.bend.platform.util.PlatformTypeUtil;
import com.bend.platform.util.StreamingTaskConflictMessage;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.*;

/**
 * {@link TaskControlService} 的实现。
 *
 * <p>实现分阶段任务控制面：阶段一 {@link #startStreaming} 负责创建或复用串流任务、生成串流会话、
 * 标记账号忙碌并交由 {@code TaskExecutorService} 拉起；阶段二 {@link #startAutomation} 在串流就绪后
 * 锁定本会话的 gameActionType 并下发开始指令。其余方法覆盖暂停/恢复/取消/终止与窗口、跳过账号、
 * 重连串流等运行时控制。</p>
 *
 * <p>所有写操作经 {@link #requireTask} 做 merchant 归属校验；对 Agent 的指令统一经
 * {@link #sendTaskControl} 通过 {@code AgentWebSocketEndpoint} 下发。</p>
 */
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
    private final AgentInstanceService agentInstanceService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 阶段一实现：校验 Agent 在线与并发余量、流媒体账号归属与冲突，构建任务参数后
     * 新建或复用串流任务，创建串流会话并标记账号忙碌，最后交由执行器拉起串流。
     */
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
        Task activeTask = taskService.findActiveTaskByStreamingAccountId(streamingAccountId);
        if (activeTask != null) {
            String agentName = agentInstanceService.resolveDisplayName(activeTask.getTargetAgentId());
            Map<String, Object> conflict = new HashMap<>();
            conflict.put("taskId", activeTask.getId());
            conflict.put("agentId", activeTask.getTargetAgentId());
            conflict.put("agentName", agentName);
            throw new BusinessException(
                    400,
                    StreamingTaskConflictMessage.format(activeTask, agentName),
                    conflict);
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

        Task reusable = taskService.findReusableTaskByStreamingAccountAndAgent(streamingAccountId, agentId);
        final Task task;
        final boolean reused;
        if (reusable != null) {
            task = reactivateStreamingTask(reusable, taskParams, selectedHost, request);
            reused = true;
            log.info("复用串流任务 - TaskID: {}, StreamingAccount: {}, Agent: {}",
                    task.getId(), streamingAccountId, agentId);
        } else {
            task = createStreamingTask(
                    streamingAccount, agentId, userId, request, selectedHost, taskParams);
            reused = false;
            log.info("新建串流任务 - TaskID: {}, StreamingAccount: {}, Agent: {}",
                    task.getId(), streamingAccountId, agentId);
        }

        streamingSessionService.closeOpenSessionsForTask(task.getId(), "closed");
        StreamingSession session = streamingSessionService.createForTask(task, merchantId);

        task.setSessionId(session.getId());
        task.setSessionPhase("opening");
        taskMapper.updateById(task);

        markStreamingAccountsBusy(streamingAccountId, agentId, gameAccounts);

        taskExecutorService.executeTask(task);

        Map<String, Object> result = new HashMap<>();
        result.put("taskId", task.getId());
        result.put("sessionId", session.getId());
        result.put("phase", "opening");
        result.put("reused", reused);
        return result;
    }

    private Task createStreamingTask(
            StreamingAccount streamingAccount,
            String agentId,
            String userId,
            StartStreamingRequest request,
            XboxHost selectedHost,
            Map<String, Object> taskParams) {
        Task task = new Task();
        task.setName("串流任务-" + streamingAccount.getDisplayLabel());
        task.setDescription(request.getDescription());
        task.setType("automation");
        task.setTargetAgentId(agentId);
        task.setStreamingAccountId(streamingAccount.getId());
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
        return taskService.create(task);
    }

    private Task reactivateStreamingTask(
            Task task,
            Map<String, Object> taskParams,
            XboxHost selectedHost,
            StartStreamingRequest request) {
        taskParams.put("relaunch", true);
        task.setStatus("pending");
        task.setErrorMessage(null);
        task.setResult(null);
        task.setGameActionType(null);
        task.setGameActionPending(true);
        task.setSessionPhase("opening");
        task.setWindowVisible(true);
        task.setPauseMode(null);
        task.setProgressMessage(null);
        task.setCurrentStep(null);
        task.setStepStatus(null);
        task.setCompletedTime(null);
        task.setStartedTime(null);
        if (selectedHost != null) {
            task.setXboxHostId(selectedHost.getId());
        } else if (request.getXboxHostId() != null && !request.getXboxHostId().isBlank()) {
            task.setXboxHostId(request.getXboxHostId());
        }
        if (request.getDescription() != null) {
            task.setDescription(request.getDescription());
        }
        statusService.deleteByTaskId(task.getId());
        try {
            task.setParams(objectMapper.writeValueAsString(taskParams));
        } catch (Exception e) {
            task.setParams("{}");
        }
        taskMapper.updateById(task);
        return task;
    }

    private void markStreamingAccountsBusy(
            String streamingAccountId, String agentId, List<GameAccount> gameAccounts) {
        streamingAccountService.updateTaskStatus(streamingAccountId, AccountStatusEnum.BUSY.getCode());
        streamingAccountService.updateAgentId(streamingAccountId, agentId);
        for (GameAccount ga : gameAccounts) {
            gameAccountService.updateStatus(ga.getId(), AccountStatusEnum.BUSY.getCode());
            gameAccountService.updateAgentId(ga.getId(), agentId);
        }
    }

    private void restoreStreamingAccountState(Task task) {
        String streamingAccountId = task.getStreamingAccountId();
        if (streamingAccountId == null) {
            return;
        }
        streamingAccountService.updateTaskStatus(streamingAccountId, AccountStatusEnum.IDLE.getCode());
        streamingAccountService.updateAgentId(streamingAccountId, null);
        for (GameAccount ga : gameAccountService.findByStreamingId(streamingAccountId)) {
            gameAccountService.updateStatus(ga.getId(), AccountStatusEnum.IDLE.getCode());
            gameAccountService.updateAgentId(ga.getId(), null);
        }
    }

    /**
     * 阶段二实现：仅当任务明确处于 ready / automation_failed 时允许启动；
     * gameActionPending 只表示 UI 上“待选择模式”，不能绕过串流会话就绪检查。通过后写入
     * gameActionType、切换 phase=automating，锁定会话任务类型并向 Agent 下发开始指令。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> startAutomation(String taskId, StartTaskAutomationRequest request, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        if (!"ready".equalsIgnoreCase(task.getSessionPhase())
                && !"automation_failed".equalsIgnoreCase(task.getSessionPhase())) {
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

    /**
     * 实现：写入 pauseMode（immediate/after_match），将 status 置 paused，sessionPhase 标为
     * {@code paused_<mode>}，并向 Agent 下发 pause 指令。
     */
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

    /**
     * 实现：清理 pauseMode、置 status=running；若仍待选择任务类型则回到 ready，否则回到 automating，
     * 随后下发 resume 指令。
     */
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

    /**
     * 实现：显式 sessionId 优先；否则取任务当前会话；缺会话时退回任务级查询（仅商户隔离）。
     */
    @Override
    public List<StreamingSession> getTaskSessions(String taskId, String merchantId) {
        requireTask(taskId, merchantId);
        return streamingSessionService.listByTaskId(taskId);
    }

    @Override
    public List<TaskEvent> getTaskEvents(String taskId, String merchantId, int limit, String sessionId) {
        if (StringUtils.hasText(sessionId)) {
            return taskEventService.listByTaskIdAndSession(taskId, merchantId, sessionId, limit);
        }
        Task task = requireTask(taskId, merchantId);
        if (StringUtils.hasText(task.getSessionId())) {
            return taskEventService.listByTaskIdAndSession(
                    taskId, merchantId, task.getSessionId(), limit);
        }
        return taskEventService.listByTaskIdForMerchant(taskId, merchantId, limit);
    }

    /** 实现：直接复用 {@link #terminateTask}，二者语义等同。 */
    @Override
    public void cancelTask(String taskId, String merchantId) {
        terminateTask(taskId, merchantId);
    }

    /**
     * 实现：先取消 Agent 执行（{@code taskExecutorService.cancelTask}），再将任务置 cancelled、
     * sessionPhase=closed、windowVisible=false；关闭当前会话、释放流媒体/游戏账号占用，
     * 最后下发 terminate（含关闭窗口）。
     */
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
        restoreStreamingAccountState(task);
        sendTaskControl(task, "terminate", Map.of("closeWindow", true));
    }

    /**
     * 实现：根据 action（show/hide）更新 windowVisible，向 Agent 下发 {@code window_<action>} 指令。
     */
    @Override
    public void windowControl(String taskId, String action, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        boolean visible = "show".equals(action);
        task.setWindowVisible(visible);
        taskMapper.updateById(task);
        sendTaskControl(task, "window_" + action, Map.of());
    }

    /**
     * 实现：将该任务-账号的状态置为 skipped 并下发 skip_game_account 通知，Agent 收到后跳过该账号。
     */
    @Override
    public void skipGameAccount(String taskId, String gameAccountId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        statusService.updateStatus(taskId, gameAccountId, "skipped");
        sendTaskControl(task, "skip_game_account", Map.of("gameAccountId", gameAccountId));
    }

    /** 实现：向 Agent 下发 reconnect_stream 指令，由 Agent 端复用 PlaySession 重连 DataChannel。 */
    @Override
    public void reconnectStream(String taskId, String merchantId) {
        Task task = requireTask(taskId, merchantId);
        sendTaskControl(task, "reconnect_stream", Map.of());
    }

    /**
     * 实现：聚合任务本体、当前串流会话与各游戏账号执行状态；为状态记录补齐展示名。
     */
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

    /**
     * 实现：按 Agent 拉取任务，过滤 merchant 后保留 running/paused 或仍待选择任务类型的项。
     */
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
        info.put("name", account.getDisplayLabel());
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
