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
 * Agent 回调接口。
 *
 * <p>这些端点只供 Agent 经网关调用，认证由 AgentAuthFilter 校验 X-Agent-Id /
 * X-Agent-Secret。Controller 只做统一响应封装，任务归属、商户隔离、幂等和状态迁移
 * 均委托 {@link AgentCallbackService} 处理。
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/agent-callback")
@RequiredArgsConstructor
public class AgentCallbackController {

    private final AgentCallbackService agentCallbackService;

    /**
     * 接收 Agent 任务进度上报。
     *
     * <p>payload 支持任务级和 session 级进度；当包含 phase/sessionId 时会驱动前端
     * 会话阶段展示和任务事件时间线。
     */
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

    /**
     * Agent 拉取任务上下文。
     *
     * <p>用于执行前确认任务仍存在、未被取消，并获取账号、主机、会话等执行参数。
     */
    @GetMapping("/task/{taskId}")
    public ApiResponse<Map<String, Object>> getTaskInfo(@PathVariable String taskId) {
        try {
            return ApiResponse.success(agentCallbackService.getTaskInfo(taskId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /**
     * 锁定 Xbox 主机占用。
     *
     * <p>Step2 串流连接前调用，服务层会校验主机归属和当前占用，避免多个任务同时连接同一主机。
     */
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

    /**
     * 释放 Xbox 主机占用。
     *
     * <p>任务失败、取消、终止或串流关闭时调用；payload 可携带 taskId/sessionId 用于服务层校验释放边界。
     */
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

    /** 查询 Xbox 主机当前锁定和在线状态，供 Agent 匹配前做只读确认。 */
    @GetMapping("/xbox/{xboxHostId}")
    public ApiResponse<Map<String, Object>> getXboxHostStatus(@PathVariable String xboxHostId) {
        try {
            return ApiResponse.success(agentCallbackService.getXboxHostStatus(xboxHostId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /** 按 GSSV serverId（xbox_host.xbox_id）查询占用状态。 */
    @GetMapping("/xbox/device/{xboxId}")
    public ApiResponse<Map<String, Object>> getXboxHostStatusByXboxId(@PathVariable String xboxId) {
        try {
            return ApiResponse.success(agentCallbackService.getXboxHostStatusByXboxId(xboxId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /** 按 GSSV serverId 申请串流租约（Redis 跨 Agent；未登记主机也可互斥）。 */
    @PostMapping("/xbox/device/{xboxId}/lock")
    public ApiResponse<Map<String, Object>> lockXboxHostByXboxId(
            @PathVariable String xboxId,
            @RequestBody(required = false) Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.lockXboxHostByXboxId(xboxId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /** 按 GSSV serverId 释放主机锁定。 */
    @PostMapping("/xbox/device/{xboxId}/unlock")
    public ApiResponse<Map<String, Object>> unlockXboxHostByXboxId(
            @PathVariable String xboxId,
            @RequestBody(required = false) Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.unlockXboxHostByXboxId(xboxId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /**
     * 读取同商户、同 platform、同 /24 网段的 LAN 发现缓存。
     *
     * <p>请求方须传本机 RFC1918 地址与 platform；仅同网段时返回缓存。
     */
    @GetMapping("/lan-discovery")
    public ApiResponse<Map<String, Object>> getLanDiscoveryCache(
            @RequestParam String localIp,
            @RequestParam String platform) {
        try {
            return ApiResponse.success(agentCallbackService.getLanDiscoveryCache(localIp, platform));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /**
     * 上报 LAN SmartGlass 发现结果：写入 Redis（TTL 默认 90s）并 upsert xbox_host。
     */
    @PostMapping("/lan-discovery/report")
    public ApiResponse<Map<String, Object>> reportLanDiscovery(@RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.reportLanDiscovery(payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /**
     * 交换加密凭据。
     *
     * <p>Agent 不直接读取数据库密文，必须通过该接口按任务上下文换取本次执行所需账号凭据。
     */
    @PostMapping("/credentials/exchange")
    public ApiResponse<Map<String, Object>> exchangeCredential(@RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.exchangeCredential(payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        }
    }

    /**
     * 更新游戏账号档案绑定状态。
     *
     * <p>账号开通/档案绑定模块在 Xbox 侧确认后上报，后端据此决定后续任务是否可跳过登录开通流程。
     */
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

    /**
     * 接收 Step4 可计费事件。
     *
     * <p>payload 必须包含 taskId、gameAccountId、billingUnit、unitIndex 等字段；
     * 服务层会生成幂等键，重复上报不会重复扣点。
     */
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

    /**
     * Step2 串流成功后自动确保账号与主机绑定（source=stream_success）。
     */
    @PostMapping("/streaming-accounts/{streamingAccountId}/hosts/ensure-binding")
    public ApiResponse<Map<String, Object>> ensureHostBinding(
            @PathVariable String streamingAccountId,
            @RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.ensureHostBinding(streamingAccountId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("确保主机绑定失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
    }

    /**
     * Step1 读取串流账号 xblive Token 平台缓存（跨 Agent 复用/刷新）。
     */
    @GetMapping("/streaming-accounts/{streamingAccountId}/auth-cache")
    public ApiResponse<Map<String, Object>> getStreamingAuthCache(
            @PathVariable String streamingAccountId,
            @RequestParam("taskId") String taskId) {
        try {
            return ApiResponse.success(agentCallbackService.getStreamingAuthCache(streamingAccountId, taskId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("读取串流 Token 缓存失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
    }

    /**
     * Step1 写入/刷新串流账号 xblive Token 平台缓存。
     */
    @PutMapping("/streaming-accounts/{streamingAccountId}/auth-cache")
    public ApiResponse<Map<String, Object>> saveStreamingAuthCache(
            @PathVariable String streamingAccountId,
            @RequestBody Map<String, Object> payload) {
        try {
            return ApiResponse.success(agentCallbackService.saveStreamingAuthCache(streamingAccountId, payload));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("写入串流 Token 缓存失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
    }

    /**
     * Step1 清除串流账号 xblive Token 平台缓存（refresh 作废或不可恢复失败）。
     */
    @DeleteMapping("/streaming-accounts/{streamingAccountId}/auth-cache")
    public ApiResponse<Map<String, Object>> deleteStreamingAuthCache(
            @PathVariable String streamingAccountId,
            @RequestParam("taskId") String taskId) {
        try {
            return ApiResponse.success(
                    agentCallbackService.deleteStreamingAuthCache(streamingAccountId, taskId));
        } catch (BusinessException e) {
            return ApiResponse.error(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("清除串流 Token 缓存失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
    }

    /**
     * 旧版任务状态回调。
     *
     * <p>保留给旧 Agent 版本兼容，新任务流应使用 /progress 和 task_control 协议。
     */
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

    /** 旧版游戏账号状态回调，兼容旧 Agent；新流程使用 progress payload 更新账号级状态。 */
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

    /** 旧版账号状态查询接口，兼容旧前端/Agent；新前端应查询任务详情接口。 */
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
