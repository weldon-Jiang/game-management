package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentVersionPageRequest;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.AgentVersion;
import com.bend.platform.service.AgentVersionService;
import com.bend.platform.util.UserContext;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import jakarta.websocket.Session;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Agent版本管理控制器（平台端）
 *
 * 功能说明：
 * - 平台管理员管理Agent版本
 * - 发布和撤销Agent版本更新
 *
 * 主要功能：
 * - 创建/编辑/删除Agent版本
 * - 发布版本（设为可用更新版本）
 * - 撤销发布版本
 * - 批量通知Agent更新
 * - 通知指定Agent更新
 */
@Slf4j
@RestController
@RequestMapping("/api/admin/agent-versions")
@RequiredArgsConstructor
public class AgentVersionController {

    private final AgentVersionService agentVersionService;

    /**
     * 创建Agent版本
     * 仅平台管理员可操作
     *
     * @param version 版本信息
     * @return 创建的版本
     */
    @PostMapping
    public ApiResponse<AgentVersion> create(@RequestBody AgentVersion version) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }
        AgentVersion created = agentVersionService.create(version);
        return ApiResponse.success("创建成功", created);
    }

    /**
     * 获取所有Agent版本
     *
     * @return 版本列表
     */
    @GetMapping
    public ApiResponse<List<AgentVersion>> list() {
        List<AgentVersion> versions = agentVersionService.findAll();
        return ApiResponse.success(versions);
    }

    /**
     * 分页查询Agent版本
     *
     * @param request 分页请求参数
     * @return 版本分页列表
     */
    @GetMapping("/page")
    public ApiResponse<IPage<AgentVersion>> page(AgentVersionPageRequest request) {
        IPage<AgentVersion> page = agentVersionService.findPage(request);
        return ApiResponse.success(page);
    }

    /**
     * 获取版本详情
     *
     * @param id 版本ID
     * @return 版本信息
     */
    @GetMapping("/{id}")
    public ApiResponse<AgentVersion> getById(@PathVariable String id) {
        AgentVersion version = agentVersionService.findById(id);
        if (version == null) {
            return ApiResponse.error(404, "版本不存在");
        }
        return ApiResponse.success(version);
    }

    /**
     * 更新Agent版本
     * 仅平台管理员可操作
     *
     * @param id      版本ID
     * @param version 更新后的版本信息
     * @return 更新后的版本
     */
    @PutMapping("/{id}")
    public ApiResponse<AgentVersion> update(@PathVariable String id, @RequestBody AgentVersion version) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }
        version.setId(id);
        AgentVersion updated = agentVersionService.publish(version);
        return ApiResponse.success("更新成功", updated);
    }

    /**
     * 发布版本
     * 将版本设为可用更新版本
     *
     * @param id 版本ID
     * @return 操作结果
     */
    @PostMapping("/{id}/publish")
    public ApiResponse<Void> publish(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }
        agentVersionService.publish(agentVersionService.findById(id));
        return ApiResponse.success("发布成功", null);
    }

    /**
     * 取消发布版本
     *
     * @param id 版本ID
     * @return 操作结果
     */
    @PostMapping("/{id}/unpublish")
    public ApiResponse<Void> unpublish(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }
        agentVersionService.unpublish(id);
        return ApiResponse.success("取消发布成功", null);
    }

    /**
     * 删除Agent版本
     * 仅平台管理员可操作
     *
     * @param id 版本ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }
        agentVersionService.delete(id);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 批量通知所有在线Agent更新
     * 仅平台管理员可操作
     *
     * @param id 版本ID
     * @return 通知结果统计
     */
    @PostMapping("/{id}/notify-all")
    public ApiResponse<Map<String, Object>> notifyAllAgents(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }

        AgentVersion version = agentVersionService.findById(id);
        if (version == null) {
            return ApiResponse.error(404, "版本不存在");
        }

        if (version.getStatus() == null || version.getStatus() != 1) {
            return ApiResponse.error(400, "请先发布该版本");
        }

        int successCount = 0;
        int failCount = 0;

        Map<String, Session> onlineAgents = AgentWebSocketEndpoint.getOnlineAgents();
        for (Map.Entry<String, Session> entry : onlineAgents.entrySet()) {
            String agentId = entry.getKey();
            try {
                AgentWebSocketEndpoint.sendVersionUpdate(agentId, version);
                successCount++;
            } catch (Exception e) {
                log.error("通知Agent失败 - AgentID: {}", agentId, e);
                failCount++;
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("successCount", successCount);
        result.put("failCount", failCount);
        result.put("total", onlineAgents.size());
        result.put("version", version.getVersion());

        log.info("批量通知Agent更新 - 版本: {}, 成功: {}, 失败: {}",
            version.getVersion(), successCount, failCount);

        return ApiResponse.success("已通知" + successCount + "个Agent", result);
    }

    /**
     * 通知指定Agent更新
     * 仅平台管理员可操作
     *
     * @param id     版本ID
     * @param agentId 目标AgentID
     * @return 操作结果
     */
    @PostMapping("/{id}/notify/{agentId}")
    public ApiResponse<Void> notifyAgent(@PathVariable String id, @PathVariable String agentId) {
        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }

        AgentVersion version = agentVersionService.findById(id);
        if (version == null) {
            return ApiResponse.error(404, "版本不存在");
        }

        if (!AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            return ApiResponse.error(400, "Agent不在线");
        }

        AgentWebSocketEndpoint.sendVersionUpdate(agentId, version);
        log.info("通知指定Agent更新 - AgentID: {}, 版本: {}", agentId, version.getVersion());

        return ApiResponse.success("已通知Agent更新", null);
    }

    /**
     * 获取版本统计信息
     *
     * @return 统计信息（总版本数、已发布版本数、在线Agent数）
     */
    @GetMapping("/statistics")
    public ApiResponse<Map<String, Object>> getStatistics() {
        List<AgentVersion> versions = agentVersionService.findAll();
        Map<String, Object> stats = new HashMap<>();
        stats.put("totalVersions", versions.size());
        stats.put("publishedVersions", versions.stream().filter(v -> v.getStatus() != null && v.getStatus() == 1).count());
        stats.put("onlineAgents", AgentWebSocketEndpoint.getOnlineAgentCount());
        return ApiResponse.success(stats);
    }
}