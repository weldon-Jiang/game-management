package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentInstancePageRequest;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.AgentKeyboardMappingChartResponse;
import com.bend.platform.dto.AgentKeyboardMappingResponse;
import com.bend.platform.dto.UpdateAgentKeyboardMappingRequest;
import com.bend.platform.dto.UpdateAgentNameRequest;
import com.bend.platform.service.AgentKeyboardMappingService;
import jakarta.validation.Valid;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.entity.MerchantRegistrationCode;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.MerchantRegistrationCodeService;
import com.bend.platform.service.TaskService;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import com.bend.platform.service.MerchantRegistrationCodeService.ActivationResult;
import com.bend.platform.util.AgentAuthUtils;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
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
    private final TaskService taskService;
    private final AgentKeyboardMappingService agentKeyboardMappingService;

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
    public ApiResponse<Map<String, Object>> register(
            @RequestParam String registrationCode,
            @RequestParam String host,
            @RequestParam(defaultValue = "8888") Integer port,
            @RequestParam(required = false) String version,
            @RequestParam(required = false) String osType,
            @RequestParam(required = false) String osVersion,
            @RequestParam(required = false) Integer cpuCount,
            @RequestParam(required = false) Integer maxConcurrentTasks,
            @RequestParam(required = false) String agentId) {

        log.info("Agent注册请求 - 注册码: {}, 主机: {}, 操作系统: {}", registrationCode, host, osType);

        // 检查注册码
        MerchantRegistrationCode codeEntity = registrationCodeService.findByCode(registrationCode);
        if (codeEntity == null) {
            log.warn("Agent注册失败 - 注册码不存在: {}", registrationCode);
            return ApiResponse.error(400, "注册码不存在");
        }

        // 检查注册码是否已过期
        if (codeEntity.getExpireTime() != null && codeEntity.getExpireTime().isBefore(LocalDateTime.now())) {
            log.warn("Agent注册失败 - 注册码已过期: {}", registrationCode);
            return ApiResponse.error(400, "注册码已过期");
        }

        String merchantId = codeEntity.getMerchantId();

        // 优先使用传入的 agentId 查找（Agent 已经激活过，有 agentId 的情况）
        AgentInstance existing = null;
        if (agentId != null && !agentId.isEmpty()) {
            existing = agentInstanceService.findByAgentId(agentId);
        }
        
        // 如果没有通过 agentId 找到，再尝试通过注册码查找
        if (existing == null) {
            existing = agentInstanceService.findByRegistrationCode(registrationCode);
        }
        
        // 如果还是没找到，检查是否存在已删除的记录（deleted=1）
        if (existing == null && agentId != null && !agentId.isEmpty()) {
            existing = agentInstanceService.findByAgentIdIncludeDeleted(agentId);
            if (existing != null && Boolean.TRUE.equals(existing.getDeleted())) {
                log.info("发现已删除的Agent记录，将恢复 - AgentID: {}", agentId);
            }
        }
        
        // 统一处理凭证
        String finalAgentId;
        String finalAgentSecret;
        
        if (existing != null) {
            // 已存在的Agent，保留原有的agentSecret
            finalAgentId = existing.getAgentId();
            finalAgentSecret = existing.getAgentSecret();
            
            // 检查注册码是否被其他Agent使用（排除当前Agent）
            if ("used".equals(codeEntity.getStatus()) && 
                !finalAgentId.equals(agentId)) {
                log.warn("Agent注册失败 - 注册码已被其他Agent使用: {}", registrationCode);
                return ApiResponse.error(400, "注册码已被使用");
            }
            
            // 更新Agent信息
            existing.setHost(host);
            existing.setPort(port);
            existing.setVersion(version);
            existing.setOsType(osType);
            existing.setOsVersion(osVersion);
            existing.setCpuCount(cpuCount);
            existing.setMaxConcurrentTasks(maxConcurrentTasks);
            existing.setLastHeartbeat(LocalDateTime.now());
            
            if (Boolean.TRUE.equals(existing.getDeleted())) {
                // 恢复已删除的Agent
                existing.setDeleted(false);
                existing.setStatus("online");
                existing.setLastOnlineTime(LocalDateTime.now());
                existing.setUninstallReason(null);
                log.info("Agent已恢复 - AgentID: {}, 商户ID: {}", finalAgentId, merchantId);
            } else if ("uninstalled".equals(existing.getStatus())
                    || "offline".equals(existing.getStatus())
                    || "reconnecting".equals(existing.getStatus())) {
                // 重新上线 - 更新状态（含 WS 断线宽限中的 reconnecting）
                existing.setStatus("online");
                existing.setLastOnlineTime(LocalDateTime.now());
                existing.setUninstallReason(null);
                log.info("Agent重新上线 - AgentID: {}, 商户ID: {}", finalAgentId, merchantId);
            }
            
            agentInstanceService.updateByAgentId(existing);
            // 进程冷启动会丢失内存任务；注册时清理平台上仍标记活跃的孤儿任务
            taskService.cleanupIncompleteTasksAndRestoreAccounts(finalAgentId);
        } else {
            // 创建新的Agent实例 - 生成新的凭证
            finalAgentId = agentId != null && !agentId.isEmpty() ? agentId : "agent-" + UUID.randomUUID().toString().substring(0, 8);
            finalAgentSecret = generateSecureSecret();
            
            AgentInstance instance = new AgentInstance();
            instance.setAgentId(finalAgentId);
            instance.setAgentSecret(finalAgentSecret);
            instance.setMerchantId(merchantId);
            instance.setRegistrationCode(registrationCode);
            instance.setHost(host);
            instance.setPort(port);
            instance.setVersion(version);
            instance.setOsType(osType);
            instance.setOsVersion(osVersion);
            instance.setCpuCount(cpuCount);
            instance.setMaxConcurrentTasks(maxConcurrentTasks);
            instance.setStatus("online");
            instance.setLastHeartbeat(LocalDateTime.now());
            instance.setLastOnlineTime(LocalDateTime.now());

            agentInstanceService.create(instance);
            log.info("Agent注册成功 - AgentID: {}, 商户ID: {}", finalAgentId, merchantId);
        }

        // 返回凭证（Secret只返回这一次）
        Map<String, Object> response = new HashMap<>();
        response.put("agentId", finalAgentId);
        response.put("agentSecret", finalAgentSecret);
        response.put("merchantId", merchantId);
        response.put("osType", osType);
        response.put("osVersion", osVersion);
        response.put("cpuCount", cpuCount);
        response.put("maxConcurrentTasks", maxConcurrentTasks);
        response.put("keyboardMapping", agentKeyboardMappingService.getEffectiveBindingsForAgent(finalAgentId));

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
    public ApiResponse<Map<String, Object>> heartbeat(
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

        if (!agentInstanceService.validateCredentials(agentId, AgentAuthUtils.decodeSecretHeader(agentSecret))) {
            return ApiResponse.error(401, "Agent密钥验证失败");
        }

        agentInstanceService.updateHeartbeat(agentId, status, currentTaskId, currentStreamingId, version);
        Map<String, Object> payload = new HashMap<>();
        payload.put("keyboardMapping", agentKeyboardMappingService.getEffectiveBindingsForAgent(agentId));
        return ApiResponse.success("心跳接收成功", payload);
    }

    /**
     * 平台默认键盘映射模板（未配置 Agent 时使用）。
     */
    @GetMapping("/keyboard-mapping/default")
    public ApiResponse<AgentKeyboardMappingResponse> getDefaultKeyboardMapping() {
        return ApiResponse.success(agentKeyboardMappingService.buildDefaultResponse());
    }

    /**
     * 查询指定 Agent 的键盘映射（含默认/自定义与生效键位）。
     */
    @GetMapping("/{agentId}/keyboard-mapping")
    public ApiResponse<AgentKeyboardMappingResponse> getAgentKeyboardMapping(@PathVariable String agentId) {
        return ApiResponse.success(agentKeyboardMappingService.getMappingForAgent(agentId));
    }

    /**
     * F8 人工接管键盘映射图（只读，含 Agent 扩展键位与调试热键说明）。
     */
    @GetMapping("/{agentId}/keyboard-mapping/chart")
    public ApiResponse<AgentKeyboardMappingChartResponse> getAgentKeyboardMappingChart(
            @PathVariable String agentId) {
        return ApiResponse.success(agentKeyboardMappingService.getChartForAgent(agentId));
    }

    /**
     * 更新 Agent 键盘映射；resetToDefault=true 或 bindings=null 恢复默认。
     * 保存后通过 WebSocket 通知在线 Agent 热更新。
     */
    @PutMapping("/{agentId}/keyboard-mapping")
    public ApiResponse<AgentKeyboardMappingResponse> updateAgentKeyboardMapping(
            @PathVariable String agentId,
            @RequestBody UpdateAgentKeyboardMappingRequest request) {
        AgentKeyboardMappingResponse response = agentKeyboardMappingService.updateMapping(agentId, request);
        Map<String, Object> command = new HashMap<>();
        command.put("command", "update_keyboard_mapping");
        command.put("params", Map.of(
                "bindings", response.getEffectiveBindings(),
                "usingDefault", response.isUsingDefault()
        ));
        AgentWebSocketEndpoint.sendMessageToAgent(agentId, "command", command);
        return ApiResponse.success("键盘映射已更新", response);
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
     * 更新 Agent 显示名称（同一商户下不可重复）
     */
    @PutMapping("/{agentId}/name")
    public ApiResponse<AgentInstance> updateAgentName(
            @PathVariable String agentId,
            @Valid @RequestBody UpdateAgentNameRequest request) {
        AgentInstance instance = agentInstanceService.findByAgentId(agentId);
        if (instance == null) {
            return ApiResponse.error(404, "Agent不存在");
        }
        if (!UserContext.isPlatformAdmin()) {
            String merchantId = UserContext.getMerchantId();
            if (merchantId == null || !merchantId.equals(instance.getMerchantId())) {
                return ApiResponse.error(403, "无权修改该Agent");
            }
        }
        AgentInstance updated = agentInstanceService.updateAgentName(agentId, request.getAgentName());
        return ApiResponse.success("更新成功", updated);
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

        if (!agentInstanceService.validateCredentials(agentId, AgentAuthUtils.decodeSecretHeader(agentSecret))) {
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

        if (!agentInstanceService.validateCredentials(agentId, AgentAuthUtils.decodeSecretHeader(agentSecret))) {
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

        if (!agentInstanceService.validateCredentials(agentId, AgentAuthUtils.decodeSecretHeader(agentSecret))) {
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

    /**
     * 清理已卸载状态的Agent
     *
     * 权限说明：
     * - 平台管理员：清理所有商户的已卸载Agent
     * - 商户用户：只清理自己商户的已卸载Agent
     *
     * @return 清理的数量
     */
    @DeleteMapping("/cleanup/uninstalled")
    public ApiResponse<Map<String, Object>> cleanupUninstalled() {
        String merchantId = null;
        if (!UserContext.isPlatformAdmin()) {
            merchantId = UserContext.getMerchantId();
        }

        int count = agentInstanceService.cleanupUninstalled(merchantId);
        log.info("清理已卸载Agent完成 - 商户ID: {}, 清理数量: {}", merchantId, count);

        Map<String, Object> response = new HashMap<>();
        response.put("cleanedCount", count);
        return ApiResponse.success("清理完成", response);
    }

    /**
     * 清理离线超过指定时间的Agent
     *
     * 权限说明：
     * - 平台管理员：清理所有商户的离线Agent
     * - 商户用户：只清理自己商户的离线Agent
     *
     * @param offlineMinutes 离线分钟数阈值（默认30分钟）
     * @return 清理的数量
     */
    @DeleteMapping("/cleanup/offline")
    public ApiResponse<Map<String, Object>> cleanupOffline(
            @RequestParam(defaultValue = "30") Integer offlineMinutes) {
        String merchantId = null;
        if (!UserContext.isPlatformAdmin()) {
            merchantId = UserContext.getMerchantId();
        }

        int count = agentInstanceService.cleanupOffline(offlineMinutes, merchantId);
        log.info("清理离线Agent完成 - 商户ID: {}, 离线阈值: {}分钟, 清理数量: {}", 
                merchantId, offlineMinutes, count);

        Map<String, Object> response = new HashMap<>();
        response.put("offlineMinutes", offlineMinutes);
        response.put("cleanedCount", count);
        return ApiResponse.success("清理完成", response);
    }

    /**
     * 批量删除Agent
     *
     * 权限说明：
     * - 平台管理员：删除任意Agent
     * - 商户用户：只能删除自己商户的Agent
     *
     * @param agentIds AgentID列表
     * @return 删除的数量
     */
    @DeleteMapping("/batch")
    public ApiResponse<Map<String, Object>> batchDelete(@RequestBody List<String> agentIds) {
        if (agentIds == null || agentIds.isEmpty()) {
            return ApiResponse.error(400, "AgentID列表不能为空");
        }

        int count = agentInstanceService.batchDelete(agentIds);
        log.info("批量删除Agent完成 - 删除数量: {}", count);

        Map<String, Object> response = new HashMap<>();
        response.put("deletedCount", count);
        return ApiResponse.success("删除完成", response);
    }

    /**
     * 删除单个Agent
     *
     * 权限说明：
     * - 平台管理员：删除任意Agent
     * - 商户用户：只能删除自己商户的Agent
     *
     * @param agentId AgentID
     * @return 删除结果
     */
    @DeleteMapping("/{agentId}")
    public ApiResponse<Void> deleteAgent(@PathVariable String agentId) {
        agentInstanceService.deleteByAgentId(agentId);
        log.info("删除Agent完成 - AgentID: {}", agentId);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 获取在线Agent列表
     *
     * 功能说明：
     * - 查询当前WebSocket连接在线的Agent实例
     * - 返回Agent基本信息（ID、商户、状态等）
     *
     * 权限说明：
     * - 平台管理员：查询所有在线Agent
     * - 商户用户：只查询自己商户下的在线Agent
     *
     * @return 在线Agent列表
     */
    @GetMapping("/online")
    public ApiResponse<List<AgentInstance>> listOnline() {
        List<AgentInstance> allAgents = agentInstanceService.findAllOnline();
        
        if (UserContext.getUserInfo() == null) {
            return ApiResponse.error(401, "未登录");
        }
        
        if (!UserContext.isPlatformAdmin()) {
            String merchantId = UserContext.getMerchantId();
            if (merchantId == null) {
                return ApiResponse.error(403, "无权访问");
            }
            allAgents = allAgents.stream()
                    .filter(agent -> merchantId.equals(agent.getMerchantId()))
                    .toList();
        }
        
        return ApiResponse.success(allAgents);
    }
}
