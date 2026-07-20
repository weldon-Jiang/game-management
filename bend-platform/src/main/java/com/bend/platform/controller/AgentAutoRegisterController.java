package com.bend.platform.controller;

import com.bend.platform.config.LicenseClientCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.entity.LicenseVerifyCache;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.AgentKeyboardMappingService;
import com.bend.platform.service.LicenseClientService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * Agent 免注册码自动注册(仅分控模式)
 *
 * <p>Agent 安装后启动,通过 UDP 广播发现局域网内分控地址,直接调本接口注册:
 * 分控从本地 license 缓存取出 merchantId,创建/更新 agent_instance,返回 agentId+secret。
 * 整个过程无需注册码,商户无需去分控后台生成注册码。
 *
 * <p>注册后 Agent 用 agentId+secret 走 X-Agent-Id/X-Agent-Secret 头 + WS 心跳通信,与原流程一致。
 *
 * <p>安全:依赖局域网信任边界(分控部署在商户内网)。如需收紧,可加 auto-register 开关或广播口令。
 */
@Slf4j
@RestController
@RequestMapping("/api/agents")
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class AgentAutoRegisterController {

    private final AgentInstanceService agentInstanceService;
    private final LicenseClientService licenseClientService;
    private final AgentKeyboardMappingService agentKeyboardMappingService;

    @Value("${agent.auto-register.enabled:${AGENT_AUTO_REGISTER_ENABLED:true}}")
    private boolean autoRegisterEnabled;

    @PostMapping("/auto-register")
    public ApiResponse<Map<String, Object>> autoRegister(@RequestBody Map<String, Object> req) {
        if (!autoRegisterEnabled) {
            return ApiResponse.error(403, "分控未开启 Agent 自动注册");
        }
        String agentId = (String) req.get("agentId");
        String agentSecret = (String) req.get("agentSecret");
        if (agentId == null || agentId.isEmpty() || agentSecret == null || agentSecret.isEmpty()) {
            return ApiResponse.error(400, "agentId/agentSecret 不能为空");
        }

        // 分控 merchantId 来自本地 license 校验缓存(走 Service 层，不直连 Mapper)
        LicenseVerifyCache cache = licenseClientService.getCache();
        if (cache == null || cache.getMerchantId() == null) {
            return ApiResponse.error(503, "分控尚未完成 license 校验,请稍后再试或检查分控与总控连通性");
        }
        String merchantId = cache.getMerchantId();

        String host = (String) req.get("host");
        Object portObj = req.get("port");
        Integer port = portObj instanceof Number ? ((Number) portObj).intValue() : 8888;
        String version = (String) req.get("version");
        String osType = (String) req.get("osType");
        String osVersion = (String) req.get("osVersion");
        Object cpuObj = req.get("cpuCount");
        Integer cpuCount = cpuObj instanceof Number ? ((Number) cpuObj).intValue() : null;
        Object maxObj = req.get("maxConcurrentTasks");
        Integer maxConcurrentTasks = maxObj instanceof Number ? ((Number) maxObj).intValue() : null;
        String agentName = (String) req.get("agentName");

        AgentInstance existing = agentInstanceService.findByAgentId(agentId);
        if (existing != null && !Boolean.TRUE.equals(existing.getDeleted())) {
            // 已注册过(重启/升级),以 Agent 端 secret 为准更新,刷新在线状态
            existing.setAgentSecret(agentSecret);
            existing.setMerchantId(merchantId);
            existing.setHost(host);
            existing.setPort(port);
            existing.setVersion(version);
            existing.setOsType(osType);
            existing.setOsVersion(osVersion);
            existing.setCpuCount(cpuCount);
            existing.setMaxConcurrentTasks(maxConcurrentTasks);
            existing.setStatus("online");
            existing.setLastHeartbeat(LocalDateTime.now());
            existing.setLastOnlineTime(LocalDateTime.now());
            existing.setUninstallReason(null);
            if (agentName != null && !agentName.isEmpty()) {
                existing.setAgentName(agentName);
            }
            agentInstanceService.updateByAgentId(existing);
            log.info("Agent 自动重新注册(已存在) - AgentID: {}, 商户: {}", agentId, merchantId);
        } else {
            AgentInstance inst = new AgentInstance();
            inst.setAgentId(agentId);
            inst.setAgentSecret(agentSecret);
            inst.setMerchantId(merchantId);
            inst.setHost(host);
            inst.setPort(port);
            inst.setVersion(version);
            inst.setOsType(osType);
            inst.setOsVersion(osVersion);
            inst.setCpuCount(cpuCount);
            inst.setMaxConcurrentTasks(maxConcurrentTasks);
            inst.setAgentName(agentName != null && !agentName.isEmpty() ? agentName : ("Agent-" + agentId.substring(Math.min(6, agentId.length()))));
            inst.setStatus("online");
            inst.setLastHeartbeat(LocalDateTime.now());
            inst.setLastOnlineTime(LocalDateTime.now());
            agentInstanceService.create(inst);
            log.info("Agent 自动注册成功 - AgentID: {}, 商户: {}", agentId, merchantId);
        }

        Map<String, Object> resp = new HashMap<>();
        resp.put("agentId", agentId);
        resp.put("agentSecret", agentSecret);
        resp.put("merchantId", merchantId);
        resp.put("keyboardMapping", agentKeyboardMappingService.getEffectiveBindingsForAgent(agentId));
        return ApiResponse.success("自动注册成功", resp);
    }
}
