package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.StreamingSession;
import com.bend.platform.entity.TaskEvent;
import com.bend.platform.dto.StartStreamingRequest;
import com.bend.platform.dto.StartTaskAutomationRequest;
import com.bend.platform.dto.TaskPauseRequest;
import com.bend.platform.service.TaskControlService;
import com.bend.platform.util.UserContext;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 任务会话控制接口（分阶段控制面）。
 *
 * <p>负责串流任务从「拉起串流」到「启动游戏自动化」再到「暂停/恢复/取消/终止」的完整生命周期，
 * 并向 Agent 下发 task_control 指令（WebSocket）。与旧的一步式 {@code StartAutomationController}
 * 不同，本控制器把「串流」与「游戏自动化」拆成两个阶段，使前端可以在串流就绪后再选择任务类型。</p>
 *
 * <p>典型时序：start-streaming -> （Agent 上报 session ready）-> start-automation
 * -> pause/resume -> cancel/terminate。所有写操作均按 {@code merchantId} 做租户隔离。</p>
 */
@RestController
@RequiredArgsConstructor
public class TaskControlController {

    private final TaskControlService taskControlService;

    /**
     * 阶段一：为指定流媒体账号创建并拉起串流任务（仅建立串流，不开始游戏自动化）。
     *
     * @param streamingAccountId 流媒体账号 ID
     * @param request            指定执行的 Agent、可选 Xbox 主机与游戏账号子集
     * @return 新建/复用的 taskId、sessionId 及初始 phase=opening
     */
    @PostMapping("/api/streaming-accounts/{streamingAccountId}/tasks/start-streaming")
    public ApiResponse<Map<String, Object>> startStreaming(
            @PathVariable String streamingAccountId,
            @Valid @RequestBody StartStreamingRequest request) {
        String merchantId = UserContext.getMerchantId();
        Map<String, Object> result = taskControlService.startStreaming(
                streamingAccountId, request, UserContext.getUserId(), merchantId);
        return ApiResponse.success("串流任务已创建", result);
    }

    /**
     * 阶段二：在串流就绪后，按选定的游戏操作类型启动游戏自动化，并锁定本会话的任务类型。
     *
     * @param taskId  阶段一返回的任务 ID
     * @param request 包含 gameActionType（如 squad_battle / auction_transfer 等）
     * @return taskId、生效的 gameActionType 及 phase=automating
     */
    @PostMapping("/api/tasks/{taskId}/start-automation")
    public ApiResponse<Map<String, Object>> startAutomation(
            @PathVariable String taskId,
            @Valid @RequestBody StartTaskAutomationRequest request) {
        Map<String, Object> result = taskControlService.startAutomation(
                taskId, request, UserContext.getMerchantId());
        return ApiResponse.success("自动化已启动", result);
    }

    /**
     * 暂停任务。支持立即暂停（immediate）或本场比赛结束后暂停（after_match），并下发 pause 指令。
     *
     * @param taskId  任务 ID
     * @param request 暂停模式，缺省为 immediate
     */
    @PostMapping("/api/tasks/{taskId}/pause")
    public ApiResponse<Void> pause(
            @PathVariable String taskId,
            @RequestBody(required = false) TaskPauseRequest request) {
        if (request == null) {
            request = new TaskPauseRequest();
        }
        taskControlService.pauseTask(taskId, request, UserContext.getMerchantId());
        return ApiResponse.success("任务已暂停", null);
    }

    /**
     * 恢复已暂停的任务，并根据是否仍待选择任务类型回到 ready 或 automating 阶段，下发 resume 指令。
     *
     * @param taskId 任务 ID
     */
    @PostMapping("/api/tasks/{taskId}/resume")
    public ApiResponse<Void> resume(@PathVariable String taskId) {
        taskControlService.resumeTask(taskId, UserContext.getMerchantId());
        return ApiResponse.success("任务已恢复", null);
    }

    /**
     * 取消任务（语义等同终止）：终止 Agent 执行、关闭会话并释放账号占用。
     *
     * @param taskId 任务 ID
     */
    @PostMapping("/api/tasks/{taskId}/cancel")
    public ApiResponse<Void> cancel(@PathVariable String taskId) {
        taskControlService.cancelTask(taskId, UserContext.getMerchantId());
        return ApiResponse.success("任务已取消", null);
    }

    /**
     * 终止任务：取消 Agent 执行、关闭串流会话、释放流媒体/游戏账号占用，并下发 terminate（含关闭窗口）。
     *
     * @param taskId 任务 ID
     */
    @PostMapping("/api/tasks/{taskId}/terminate")
    public ApiResponse<Void> terminate(@PathVariable String taskId) {
        taskControlService.terminateTask(taskId, UserContext.getMerchantId());
        return ApiResponse.success("任务已终止", null);
    }

    /**
     * 控制 Agent 端 SDL 显示窗口的显示/隐藏（不影响串流与自动化）。
     *
     * @param taskId 任务 ID
     * @param action 窗口动作（show / hide）
     */
    @PostMapping("/api/tasks/{taskId}/window/{action}")
    public ApiResponse<Void> windowControl(
            @PathVariable String taskId,
            @PathVariable String action) {
        taskControlService.windowControl(taskId, action, UserContext.getMerchantId());
        return ApiResponse.success(null);
    }

    /**
     * 跳过当前任务中的某个游戏账号：标记其状态为 skipped，并通知 Agent 跳过该账号。
     *
     * @param taskId        任务 ID
     * @param gameAccountId 待跳过的游戏账号 ID
     */
    @PostMapping("/api/tasks/{taskId}/skip-game-account/{gameAccountId}")
    public ApiResponse<Void> skipGameAccount(
            @PathVariable String taskId,
            @PathVariable String gameAccountId) {
        taskControlService.skipGameAccount(taskId, gameAccountId, UserContext.getMerchantId());
        return ApiResponse.success(null);
    }

    /**
     * 请求 Agent 重连串流（input DataChannel 异常时手动恢复），下发 reconnect_stream 指令。
     *
     * @param taskId 任务 ID
     */
    @PostMapping("/api/tasks/{taskId}/reconnect-stream")
    public ApiResponse<Void> reconnectStream(@PathVariable String taskId) {
        taskControlService.reconnectStream(taskId, UserContext.getMerchantId());
        return ApiResponse.success(null);
    }

    /**
     * 查询任务详情：含任务本体、当前串流会话与各游戏账号执行状态。
     *
     * @param taskId 任务 ID
     */
    @GetMapping("/api/tasks/{taskId}/detail")
    public ApiResponse<Map<String, Object>> getDetail(@PathVariable String taskId) {
        return ApiResponse.success(
                taskControlService.getTaskDetail(taskId, UserContext.getMerchantId()));
    }

    /**
     * 查询任务事件流（Agent 进度回调的时间线），可按会话过滤。
     *
     * @param taskId    任务 ID
     * @param limit     返回条数上限，默认 50
     * @param sessionId 可选，仅返回指定串流会话的事件
     */
    @GetMapping("/api/tasks/{taskId}/events")
    public ApiResponse<List<TaskEvent>> getEvents(
            @PathVariable String taskId,
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(required = false) String sessionId) {
        return ApiResponse.success(
                taskControlService.getTaskEvents(
                        taskId, UserContext.getMerchantId(), limit, sessionId));
    }

    /**
     * 查询任务的全部历史串流会话（最近一次在前）。用于前端在任务详情切换查看不同轮次。
     *
     * @param taskId 任务 ID
     */
    @GetMapping("/api/tasks/{taskId}/sessions")
    public ApiResponse<List<StreamingSession>> getSessions(@PathVariable String taskId) {
        return ApiResponse.success(
                taskControlService.getTaskSessions(taskId, UserContext.getMerchantId()));
    }

    /**
     * 查询某 Agent 当前活跃的任务列表（running / paused / 待选择任务类型）。
     *
     * @param agentId Agent ID
     */
    @GetMapping("/api/agents/{agentId}/active-tasks")
    public ApiResponse<List<Map<String, Object>>> activeTasks(@PathVariable String agentId) {
        return ApiResponse.success(
                taskControlService.getActiveTasks(agentId, UserContext.getMerchantId()));
    }
}
