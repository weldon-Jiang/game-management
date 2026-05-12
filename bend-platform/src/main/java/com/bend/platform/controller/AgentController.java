package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentInstancePageRequest;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.MerchantRegistrationCodeService;
import com.bend.platform.service.MerchantRegistrationCodeService.ActivationResult;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Agent控制器
 *
 * 功能说明：
 * - 处理Agent的注册、上下线、心跳等生命周期管理
 * - 提供Agent状态监控和查询接口
 * - 支持Agent卸载和重新注册
 *
 * 认证方式：
 * - 使用X-Agent-ID和X-Agent-Secret请求头进行身份验证
 *
 * 主要功能：
 * - Agent注册：使用注册码激活Agent并注册到系统
 * - 心跳上报：接收Agent定期发送的心跳，维持在线状态
 * - 状态管理：管理Agent的在线、离线、卸载等状态
 * - 卸载处理：支持Agent卸载并可选清除注册表信息
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有final字段生成构造器进行依赖注入
 */
@Slf4j
@RestController
@RequestMapping("/api/agents")
@RequiredArgsConstructor
public class AgentController {

    private final AgentInstanceService agentInstanceService;
    private final MerchantRegistrationCodeService registrationCodeService;

    /**
     * Agent注册接口
     *
     * 安全说明：
     * - Agent传递注册码进行注册（无需Secret）
     * - 后端生成 agentId 和 agentSecret 并返回
     * - Secret只返回一次，请Agent本地保存
     *
     * @param registrationCode 注册码（商户后台生成）
     * @param host Agent主机地址
     * @param port Agent端口
     * @param version Agent版本（可选）
     * @return 注册结果，包含 agentId 和 agentSecret
     */
    @PostMapping("/register")
    public ApiResponse<Map<String, String>> register(
            @RequestParam String registrationCode,
            @RequestParam String host,
            @RequestParam(defaultValue = "8888") Integer port,
            @RequestParam(required = false) String version) {

        log.info("Agent注册请求 - 注册码: {}, 主机: {}", registrationCode, host);

        // 验证注册码
        ActivationResult result = registrationCodeService.validateAndConsume(registrationCode);
        if (!result.isSuccess()) {
            log.warn("Agent注册失败 - 注册码: {}, 原因: {}", registrationCode, result.getMessage());
            return ApiResponse.error(400, result.getMessage());
        }

        String merchantId = result.getMerchantId();

        // 后端生成 agentId 和 agentSecret
        String agentId = "agent-" + UUID.randomUUID().toString().substring(0, 8);
        String agentSecret = generateSecureSecret();

        // 检查是否已存在该注册码对应的Agent（重新安装场景）
        AgentInstance existing = agentInstanceService.findByRegistrationCode(registrationCode);
        if (existing != null) {
            if ("uninstalled".equals(existing.getStatus())) {
                // 重新安装上线 - 更新信息
                existing.setAgentId(agentId);
                existing.setAgentSecret(agentSecret);
                existing.setHost(host);
                existing.setPort(port);
                existing.setVersion(version);
                existing.setStatus("online");
                existing.setLastHeartbeat(LocalDateTime.now());
                existing.setLastOnlineTime(LocalDateTime.now());
                existing.setUninstallReason(null);
                agentInstanceService.updateByAgentId(existing);
                log.info("Agent重新安装上线 - AgentID: {}, 商户ID: {}", agentId, merchantId);
            } else {
                // 已存在的Agent重新上线
                existing.setStatus("online");
                existing.setHost(host);
                existing.setPort(port);
                existing.setVersion(version);
                existing.setLastHeartbeat(LocalDateTime.now());
                existing.setLastOnlineTime(LocalDateTime.now());
                agentInstanceService.updateByAgentId(existing);
                log.info("Agent重新上线 - AgentID: {}, 商户ID: {}", existing.getAgentId(), merchantId);

                // 返回已有的凭证
                Map<String, String> response = new HashMap<>();
                response.put("agentId", existing.getAgentId());
                response.put("agentSecret", existing.getAgentSecret());
                response.put("merchantId", merchantId);
                return ApiResponse.success("注册成功", response);
            }
        } else {
            // 创建新的Agent实例
            AgentInstance instance = new AgentInstance();
            instance.setAgentId(agentId);
            instance.setAgentSecret(agentSecret);
            instance.setMerchantId(merchantId);
            instance.setRegistrationCode(registrationCode);
            instance.setHost(host);
            instance.setPort(port);
            instance.setVersion(version);
            instance.setStatus("online");
            instance.setLastHeartbeat(LocalDateTime.now());
            instance.setLastOnlineTime(LocalDateTime.now());

            agentInstanceService.create(instance);
            log.info("Agent注册成功 - AgentID: {}, 商户ID: {}", agentId, merchantId);
        }

        // 返回凭证（Secret只返回这一次）
        Map<String, String> response = new HashMap<>();
        response.put("agentId", agentId);
        response.put("agentSecret", agentSecret);
        response.put("merchantId", merchantId);

        return ApiResponse.success("注册成功", response);
    }

    /**
     * 生成安全的随机密钥
     */
    private String generateSecureSecret() {
        return UUID.randomUUID().toString().replace("-", "") +
               UUID.randomUUID().toString().substring(0, 16);
    }

    /**
     * Agent心跳接口
     *
     * 功能说明：
     * - 接收Agent定期发送的心跳
     * - 更新Agent最后心跳时间
     * - 接收Agent当前状态和任务信息
     */
    @PostMapping("/heartbeat")
    public ApiResponse<Void> heartbeat(
            @RequestHeader("X-Agent-Id") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String currentTaskId,
            @RequestParam(required = false) String currentStreamingId,
            @RequestParam(required = false) String version) {

        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        agentInstanceService.updateHeartbeat(agentId, status, currentTaskId, currentStreamingId, version);
        return ApiResponse.success("心跳接收成功", null);
    }

    /**
     * 查询Agent详情
     */
    @GetMapping("/{agentId}")
    public ApiResponse<AgentInstance> getAgent(@PathVariable String agentId) {
        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent不存在");
        }
        return ApiResponse.success(instance);
    }

    /**
     * Agent卸载接口
     *
     * 功能说明：
     * - 处理Agent卸载通知
     * - 可选择清除注册信息或保留配置
     *
     * @param clearRegistry 是否清除注册表（true则Agent需要重新注册）
     */
    @PostMapping("/uninstall")
    public ApiResponse<Map<String, Object>> uninstall(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam(required = false) String reason,
            @RequestParam(required = false, defaultValue = "false") Boolean clearRegistry) {

        log.info("Agent卸载请求 - AgentID: {}, 原因: {}, 清除注册表: {}", agentId, reason, clearRegistry);

        // 验证Agent身份
        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        if (clearRegistry) {
            instance.setStatus("uninstalled");
            instance.setUninstallReason(reason);
        } else {
            instance.setStatus("offline");
        }

        agentInstanceService.updateByAgentId(instance);

        Map<String, Object> response = new HashMap<>();
        response.put("needReregister", clearRegistry);

        if (clearRegistry != null && clearRegistry) {
            response.put("warning", "注册表已清除，需要重新注册");
            log.info("Agent注册表已清除 - AgentID: {}, 需要重新注册", agentId);
        }

        log.info("Agent卸载完成 - AgentID: {}, 原因: {}", agentId, reason);
        return ApiResponse.success(response);
    }

    /**
     * Agent下线接口
     *
     * 功能说明：
     * - 处理Agent正常下线
     * - 更新Agent状态为offline
     * - 记录最后在线时间
     */
    @PostMapping("/offline")
    public ApiResponse<Void> offline(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret) {

        log.info("Agent下线请求 - AgentID: {}", agentId);

        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        instance.setStatus("offline");
        agentInstanceService.updateByAgentId(instance);

        log.info("Agent已下线 - AgentID: {}", agentId);
        return ApiResponse.success("下线成功", null);
    }

    /**
     * Agent状态更新接口
     *
     * 功能说明：
     * - 接收Agent状态更新
     * - 更新Agent相关信息
     */
    @PostMapping("/status")
    public ApiResponse<Void> status(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String currentTaskId) {

        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        if (status != null) {
            instance.setStatus(status);
        }
        agentInstanceService.updateByAgentId(instance);

        return ApiResponse.success("状态更新成功", null);
    }

    /**
     * 分页查询Agent列表
     *
     * 权限说明：
     * - 平台管理员：查询所有Agent
     * - 商户用户：只查询自己商户下的Agent
     *
     * @param request 分页请求参数
     * @return Agent分页列表
     */
    @GetMapping("/page")
    public ApiResponse<IPage<AgentInstance>> page(AgentInstancePageRequest request) {     
        if (!UserContext.isPlatformAdmin()) {
            // 商户用户：只查询自己商户下的
            String merchantId = UserContext.getMerchantId();
            request.setMerchantId(merchantId);
        }
        IPage<AgentInstance> page = agentInstanceService.findPageWithFilters(request);
        return ApiResponse.success(page);
    }
}
