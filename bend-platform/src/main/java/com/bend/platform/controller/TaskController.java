package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.TaskPageRequest;
import com.bend.platform.entity.Task;
import com.bend.platform.service.TaskService;
import com.bend.platform.util.UserContext;
import com.bend.platform.websocket.WebSocketMessageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * 任务控制器
 *
 * 功能说明：
 * - 管理自动化任务的完整生命周期
 * - 提供任务的创建、分配、执行、取消、重试等功能
 * - 支持任务状态查询和分页浏览
 *
 * 任务类型：
 * - template_match: 模板匹配任务（图像识别）
 * - input_sequence: 输入序列任务（自动操作）
 * - scene_detection: 场景检测任务
 * - account_switch: 账号切换任务
 * - stream_control: 流媒体控制任务
 * - custom: 自定义任务
 *
 * 任务状态：
 * - pending: 等待分配
 * - running: 执行中
 * - completed: 已完成
 * - failed: 执行失败
 * - cancelled: 已取消
 */
@Slf4j
@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskService taskService;
    private final WebSocketMessageService messageService;

    /**
     * 创建任务
     *
     * @param task 任务信息
     * @return 创建的任务
     */
    @PostMapping
    public ApiResponse<Task> create(@RequestBody Task task) {
        task.setCreatedBy(UserContext.getUserId());
        Task created = taskService.create(task);
        return ApiResponse.success("创建成功", created);
    }

    /**
     * 获取任务详情
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @GetMapping("/{id}")
    public ApiResponse<Task> getById(@PathVariable String id) {
        Task task = taskService.findById(id);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }
        return ApiResponse.success(task);
    }

    /**
     * 根据Agent查询任务列表
     *
     * @param agentId AgentID
     * @return 任务列表
     */
    @GetMapping("/agent/{agentId}")
    public ApiResponse<List<Task>> listByAgent(@PathVariable String agentId) {
        List<Task> tasks = taskService.findByAgentId(agentId);
        return ApiResponse.success(tasks);
    }

    /**
     * 查询Agent的待处理任务
     *
     * @param agentId AgentID
     * @return 待处理任务列表
     */
    @GetMapping("/agent/{agentId}/pending")
    public ApiResponse<List<Task>> listPendingByAgent(@PathVariable String agentId) {
        List<Task> tasks = taskService.findPendingByAgentId(agentId);
        return ApiResponse.success(tasks);
    }

    /**
     * 分页查询任务列表
     *
     * @param request 分页请求参数
     * @return 任务分页列表
     */
    @GetMapping("/page")
    public ApiResponse<IPage<Task>> page(TaskPageRequest request) {
        IPage<Task> page = taskService.findPage(request);
        return ApiResponse.success(page);
    }

    /**
     * 分配任务给Agent
     *
     * @param id      任务ID
     * @param agentId 目标AgentID
     * @return 分配结果
     */
    @PostMapping("/{id}/assign/{agentId}")
    public ApiResponse<Task> assign(@PathVariable String id, @PathVariable String agentId) {
        if (!messageService.isAgentOnline(agentId)) {
            return ApiResponse.error(400, "Agent不在线");
        }
        Task task = taskService.assignToAgent(id, agentId);
        return ApiResponse.success("分配成功", task);
    }

    /**
     * 开始执行任务
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @PostMapping("/{id}/start")
    public ApiResponse<Task> start(@PathVariable String id) {
        Task task = taskService.start(id);
        return ApiResponse.success("开始执行", task);
    }

    /**
     * 标记任务完成
     *
     * @param id   任务ID
     * @param body 请求体（包含result结果）
     * @return 任务信息
     */
    @PostMapping("/{id}/complete")
    public ApiResponse<Task> complete(@PathVariable String id, @RequestBody Map<String, String> body) {
        String result = body.get("result");
        boolean idempotent = Boolean.parseBoolean(body.getOrDefault("idempotent", "false"));
        Task task = taskService.complete(id, result, idempotent);
        return ApiResponse.success("任务完成", task);
    }

    /**
     * 标记任务失败
     *
     * @param id   任务ID
     * @param body 请求体（包含errorMessage错误信息）
     * @return 任务信息
     */
    @PostMapping("/{id}/fail")
    public ApiResponse<Task> fail(@PathVariable String id, @RequestBody Map<String, String> body) {
        String errorMessage = body.get("errorMessage");
        boolean idempotent = Boolean.parseBoolean(body.getOrDefault("idempotent", "false"));
        Task task = taskService.fail(id, errorMessage, idempotent);
        return ApiResponse.success("标记失败", task);
    }

    /**
     * 取消任务
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @PostMapping("/{id}/cancel")
    public ApiResponse<Task> cancel(@PathVariable String id) {
        Task task = taskService.cancel(id);
        return ApiResponse.success("取消成功", task);
    }

    /**
     * 重试任务
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @PostMapping("/{id}/retry")
    public ApiResponse<Task> retry(@PathVariable String id) {
        Task task = taskService.retry(id);
        return ApiResponse.success("重试成功", task);
    }

    /**
     * 暂停任务
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @PostMapping("/{id}/pause")
    public ApiResponse<Task> pause(@PathVariable String id) {
        log.info("暂停任务 - TaskID: {}", id);
        Task task = taskService.findById(id);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        taskService.pause(id);

        messageService.sendToAgent(task.getTargetAgentId(), "pause", Map.of("taskId", id));

        task = taskService.findById(id);
        return ApiResponse.success("任务已暂停", task);
    }

    /**
     * 恢复任务
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @PostMapping("/{id}/resume")
    public ApiResponse<Task> resume(@PathVariable String id) {
        log.info("恢复任务 - TaskID: {}", id);
        Task task = taskService.findById(id);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        taskService.resume(id);

        messageService.sendToAgent(task.getTargetAgentId(), "resume", Map.of("taskId", id));

        task = taskService.findById(id);
        return ApiResponse.success("任务已恢复", task);
    }

    /**
     * 停止任务
     *
     * @param id 任务ID
     * @return 任务信息
     */
    @PostMapping("/{id}/stop")
    public ApiResponse<Task> stop(@PathVariable String id) {
        log.info("停止任务 - TaskID: {}", id);
        Task task = taskService.findById(id);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        taskService.stop(id);

        messageService.sendToAgent(task.getTargetAgentId(), "stop", Map.of("taskId", id));

        task = taskService.findById(id);
        return ApiResponse.success("任务已停止", task);
    }

    /**
     * 删除任务
     *
     * @param id 任务ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        taskService.delete(id);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 获取所有任务类型
     *
     * @return 任务类型列表
     */
    @GetMapping("/types")
    public ApiResponse<List<String>> getTypes() {
        return ApiResponse.success(Arrays.asList(
            "template_match", "input_sequence", "scene_detection",
            "account_switch", "stream_control", "custom"
        ));
    }

    /**
     * 获取所有任务状态
     *
     * @return 任务状态列表
     */
    @GetMapping("/statuses")
    public ApiResponse<List<String>> getStatuses() {
        return ApiResponse.success(Arrays.asList(
            "pending", "running", "completed", "failed", "cancelled"
        ));
    }
}