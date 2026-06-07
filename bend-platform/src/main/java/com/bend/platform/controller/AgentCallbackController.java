package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.service.AgentCallbackService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Agent callback REST endpoints (delegates to {@link AgentCallbackService}).
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/agent-callback")
@RequiredArgsConstructor
public class AgentCallbackController {

    private final AgentCallbackService agentCallbackService;

    @PostMapping("/progress")
    public ApiResponse<Map<String, Object>> reportProgress(@RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.reportProgress(payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("处理进度上报失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
    }

    @GetMapping("/task/{taskId}")
    public ApiResponse<Map<String, Object>> getTaskInfo(@PathVariable String taskId) {
        try {
            return ApiResponse.success(agentCallbackService.getTaskInfo(taskId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @PostMapping("/xbox/{xboxHostId}/lock")
    public ApiResponse<Map<String, Object>> lockXboxHost(
            @PathVariable String xboxHostId,
            @RequestBody(required = false) Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.lockXboxHost(xboxHostId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @PostMapping("/xbox/{xboxHostId}/unlock")
    public ApiResponse<Map<String, Object>> unlockXboxHost(
            @PathVariable String xboxHostId,
            @RequestBody(required = false) Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.unlockXboxHost(xboxHostId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @GetMapping("/xbox/{xboxHostId}")
    public ApiResponse<Map<String, Object>> getXboxHostStatus(@PathVariable String xboxHostId) {
        try {
            return ApiResponse.success(agentCallbackService.getXboxHostStatus(xboxHostId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @PostMapping("/credentials/exchange")
    public ApiResponse<Map<String, Object>> exchangeCredential(@RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.exchangeCredential(payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @PostMapping("/game-account/{gameAccountId}/profile-binding")
    public ApiResponse<Map<String, Object>> updateProfileBinding(
            @PathVariable String gameAccountId,
            @RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.updateProfileBinding(gameAccountId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @PostMapping("/billing-event")
    public ApiResponse<Map<String, Object>> reportBillingEvent(@RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.reportBillingEvent(payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("处理计费事件失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
    }

    @Deprecated
    @PostMapping("/task/{taskId}/status")
    public ApiResponse<Void> reportTaskStatus(
            @PathVariable String taskId,
            @RequestBody Map<String, String> payload) {
        try {
            agentCallbackService.reportTaskStatusLegacy(taskId, payload);
            return ApiResponse.success();
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @Deprecated
    @PostMapping("/task/{taskId}/game-account/{gameAccountId}/status")
    public ApiResponse<Void> updateGameAccountStatus(
            @PathVariable String taskId,
            @PathVariable String gameAccountId,
            @RequestBody Map<String, Object> payload) {
        try {
            agentCallbackService.updateGameAccountStatusLegacy(taskId, gameAccountId, payload);
            return ApiResponse.success();
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    @Deprecated
    @GetMapping("/{taskId}/game-accounts/status")
    public ApiResponse<List<Map<String, Object>>> getGameAccountsStatus(@PathVariable String taskId) {
        try {
            return ApiResponse.success(agentCallbackService.getGameAccountsStatusLegacy(taskId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }
}
