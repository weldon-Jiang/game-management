package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentInstancePageRequest;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.MerchantRegistrationCodeService;
import com.bend.platform.service.MerchantRegistrationCodeService.ActivationResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

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
     * 功能说明：
     * - 使用注册码激活Agent
     * - 创建新的Agent实例或恢复已卸载的Agent
     * - 验证Agent身份并分配商户ID
     *
     * 请求参数：
     * - registrationCode: 注册码（从平台获取）
     * - host: Agent所在主机IP
     * - port: Agent监听端口（默认8888）
     * - version: Agent版本号（可选）
     *
     * 返回值：
     * - 注册成功返回AgentInstance信息
     * - 注册码无效返回错误信息
     */
    @PostMapping("/register")
    public ApiResponse<AgentInstance> register(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam String registrationCode,
            @RequestParam String host,
            @RequestParam(defaultValue = "8888") Integer port,
            @RequestParam(required = false) String version) {

        log.info("Agent注册请求 - AgentID: {}, 注册码: {}", agentId, registrationCode);

        // 使用注册码激活Agent
        ActivationResult result = registrationCodeService.activateCode(registrationCode, agentId, agentSecret);
        if (!result.isSuccess()) {
            return ApiResponse.error(400, result.getMessage());
        }

        String merchantId = result.getMerchantId();

        // 检查Agent是否已存在（重新安装场景）
        AgentInstance existing = agentInstanceService.findByAgentId(agentId);
        if (existing != null) {
            if ("uninstalled".equals(existing.getStatus())) {
                // 重新安装上线
                existing.setStatus("online");
                existing.setHost(host);
                existing.setPort(port);
                existing.setVersion(version);
                existing.setLastHeartbeat(LocalDateTime.now());
                existing.setLastOnlineTime(LocalDateTime.now());
                existing.setAgentSecret(agentSecret);
                existing.setUninstallReason(null);
                agentInstanceService.updateByAgentId(existing);
                log.info("Agent重新安装上线 - AgentID: {}, 商户ID: {}", agentId, merchantId);
            } else {
                // 重新上线（如网络断开后恢复）
                existing.setStatus("online");
                existing.setHost(host);
                existing.setPort(port);
                existing.setVersion(version);
                existing.setLastHeartbeat(LocalDateTime.now());
                existing.setLastOnlineTime(LocalDateTime.now());
                agentInstanceService.updateByAgentId(existing);
                log.info("Agent重新上线 - AgentID: {}, 商户ID: {}", agentId, merchantId);
            }
            return ApiResponse.success("注册成功", existing);
        }

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

        AgentInstance created = agentInstanceService.create(instance);
        log.info("Agent注册成功 - AgentID: {}, 商户ID: {}", agentId, merchantId);

        return ApiResponse.success("注册成功", created);
    }

    /**
     * Agent心跳接口
     *
     * 功能说明：
     * - 接收Agent定期发送的心跳
     * - 更新Agent最后心跳时间
     * - 接收Agent当前状态和任务信息
     *
     * 请求参数：
     * - status: Agent当前状态（可选）
     * - currentTaskId: 当前执行的任务ID（可选）
     * - currentStreamingId: 当前流媒体账号ID（可选）
     * - version: Agent版本号（可选）
     *
     * 返回值：
     * - 心跳确认信息
     */
    @PostMapping("/heartbeat")
    public ApiResponse<Map<String, Object>> heartbeat(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String currentTaskId,
            @RequestParam(required = false) String currentStreamingId,
            @RequestParam(required = false) String version) {

        // 验证Agent身份
        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        // 更新心跳时间和状态
        instance.setLastHeartbeat(LocalDateTime.now());
        if (status != null) {
            instance.setStatus(status);
        }
        if (currentTaskId != null) {
            instance.setCurrentTaskId(currentTaskId);
        }
        if (currentStreamingId != null) {
            instance.setCurrentStreamingId(currentStreamingId);
        }
        if (version != null && !version.equals(instance.getVersion())) {
            instance.setVersion(version);
        }

        agentInstanceService.updateByAgentId(instance);

        Map<String, Object> response = new HashMap<>();
        response.put("heartbeat", "ok");

        return ApiResponse.success(response);
    }

    /**
     * Agent状态上报接口
     *
     * 功能说明：
     * - 接收Agent主动上报的状态信息
     * - 支持附加元数据
     * - 离线时记录最后在线时间
     *
     * 请求参数：
     * - status: Agent状态（如online、offline、error等）
     * - metadata: 附加的元数据信息（可选）
     */
    @PostMapping("/status")
    public ApiResponse<Void> reportStatus(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam String status,
            @RequestParam(required = false) Map<String, Object> metadata) {

        // 验证Agent身份
        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        // 更新状态
        instance.setStatus(status);
        instance.setLastHeartbeat(LocalDateTime.now());

        // 离线时记录最后在线时间
        if ("offline".equals(status)) {
            instance.setLastOnlineTime(LocalDateTime.now());
        }

        agentInstanceService.updateByAgentId(instance);
        log.info("Agent状态上报 - AgentID: {}, 状态: {}", agentId, status);

        return ApiResponse.success("状态更新成功", null);
    }

    /**
     * Agent卸载接口
     *
     * 功能说明：
     * - 处理Agent卸载请求
     * - 支持清除注册表（清除后需要重新注册）
     * - 记录卸载原因
     *
     * 请求参数：
     * - reason: 卸载原因（可选）
     * - clearRegistry: 是否清除注册表（默认false）
     *
     * 返回值：
     * - needReregister: 是否需要重新注册
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

        // 更新Agent状态为已卸载
        instance.setStatus("uninstalled");
        instance.setLastOnlineTime(LocalDateTime.now());
        instance.setUninstallReason(reason != null ? reason : "用户主动卸载");

        Map<String, Object> response = new HashMap<>();
        response.put("message", "卸载成功");
        response.put("needReregister", clearRegistry != null && clearRegistry);

        if (clearRegistry != null && clearRegistry) {
            response.put("warning", "注册表已清除，需要重新注册");
            log.info("Agent注册表已清除 - AgentID: {}, 需要重新注册", agentId);
        }

        agentInstanceService.updateByAgentId(instance);

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

        // 验证Agent身份
        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent未注册");
        }

        if (!agentSecret.equals(instance.getAgentSecret())) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        // 更新为离线状态
        instance.setStatus("offline");
        instance.setLastOnlineTime(LocalDateTime.now());
        agentInstanceService.updateByAgentId(instance);

        log.info("Agent下线 - AgentID: {}", agentId);
        return ApiResponse.success("下线成功", null);
    }

    /**
     * 获取单个Agent信息
     *
     * 功能说明：
     * - 根据AgentID查询Agent详细信息
     *
     * 路径参数：
     * - agentId: Agent唯一标识符
     *
     * 返回值：
     * - Agent详细信息
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
     * 分页查询Agent列表
     *
     * 功能说明：
     * - 支持按状态和商户ID筛选
     * - 分页返回Agent列表
     *
     * @param request 分页请求参数
     *
     * 返回值：
     * - 分页的Agent列表
     */
    @GetMapping("/list")
    public ApiResponse<IPage<AgentInstance>> listAgents(AgentInstancePageRequest request) {

        IPage<AgentInstance> page = agentInstanceService.findPageWithFilters(request);
        return ApiResponse.success(page);
    }
}
