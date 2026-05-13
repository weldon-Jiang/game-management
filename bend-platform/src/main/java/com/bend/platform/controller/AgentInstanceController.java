package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentInstancePageRequest;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Agent实例控制器
 *
 * 功能说明：
 * - 提供Agent实例的查询和管理功能
 * - Agent实例是注册到系统的Agent进程
 *
 * 主要功能：
 * - 查询Agent列表
 * - 分页查询Agent列表
 * - 获取Agent详情
 * - 更新Agent状态
 */
@RestController
@RequestMapping("/api/agent-instances")
@RequiredArgsConstructor
public class AgentInstanceController {

    private final AgentInstanceService agentInstanceService;
    private final AgentLoadControlService loadControlService;

    /**
     * 查询Agent列表
     * 平台管理员返回所有Agent，商户用户返回本商户Agent
     *
     * @return Agent列表
     */
    @GetMapping
    public ApiResponse<List<AgentInstance>> list() {
        if (UserContext.isPlatformAdmin()) {
            return ApiResponse.success(agentInstanceService.findAll());
        }
        String merchantId = UserContext.getMerchantId();
        return ApiResponse.success(agentInstanceService.findAllByMerchantId(merchantId));
    }

    /**
     * 分页查询Agent列表
     *
     * @param request 分页请求参数
     * @return Agent分页列表
     */
    @GetMapping("/page")
    public ApiResponse<IPage<AgentInstance>> listPage(AgentInstancePageRequest request) {
        if (UserContext.isPlatformAdmin()) {
            return ApiResponse.success(agentInstanceService.findAll(request));
        }
        String merchantId = UserContext.getMerchantId();
        return ApiResponse.success(agentInstanceService.findPageByMerchantId(merchantId, request));
    }

    /**
     * 获取Agent详情
     *
     * @param id Agent实例ID
     * @return Agent信息
     */
    @GetMapping("/{id}")
    public ApiResponse<AgentInstance> getById(@PathVariable String id) {
        AgentInstance instance = agentInstanceService.findById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }
        return ApiResponse.success(instance);
    }

    /**
     * 更新Agent状态
     *
     * @param id     Agent实例ID
     * @param status 新状态
     * @return 操作结果
     */
    @PutMapping("/{id}/status")
    public ApiResponse<Void> updateStatus(
            @PathVariable String id,
            @RequestParam String status) {
        agentInstanceService.updateStatus(id, status);
        return ApiResponse.success("状态更新成功", null);
    }

    @GetMapping("/{id}/load")
    public ApiResponse<AgentLoadInfo> getAgentLoad(@PathVariable String id) {
        AgentInstance instance = agentInstanceService.findById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }
        int currentTasks = loadControlService.getCurrentTaskCount(instance.getAgentId());
        int maxTasks = instance.getMaxConcurrentTasks() != null ? instance.getMaxConcurrentTasks() : 5;
        String loadStatus;
        if (currentTasks == 0) {
            loadStatus = "idle";
        } else if (currentTasks < maxTasks) {
            loadStatus = "busy";
        } else {
            loadStatus = "full";
        }
        AgentLoadInfo info = new AgentLoadInfo();
        info.setCurrentTasks(currentTasks);
        info.setMaxTasks(maxTasks);
        info.setLoadStatus(loadStatus);
        return ApiResponse.success(info);
    }

    public static class AgentLoadInfo {
        private int currentTasks;
        private int maxTasks;
        private String loadStatus;

        public int getCurrentTasks() { return currentTasks; }
        public void setCurrentTasks(int currentTasks) { this.currentTasks = currentTasks; }
        public int getMaxTasks() { return maxTasks; }
        public void setMaxTasks(int maxTasks) { this.maxTasks = maxTasks; }
        public String getLoadStatus() { return loadStatus; }
        public void setLoadStatus(String loadStatus) { this.loadStatus = loadStatus; }
    }
}