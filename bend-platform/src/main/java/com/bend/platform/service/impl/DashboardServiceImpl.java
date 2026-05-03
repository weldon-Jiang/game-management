package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.dto.DashboardStatsResponse;
import com.bend.platform.entity.*;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.MerchantUserMapper;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.service.DashboardService;
import com.bend.platform.util.DataSecurityUtil;
import com.bend.platform.util.UserContext;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class DashboardServiceImpl implements DashboardService {

    private final MerchantMapper merchantMapper;
    private final MerchantUserMapper merchantUserMapper;
    private final StreamingAccountMapper streamingAccountMapper;
    private final GameAccountMapper gameAccountMapper;
    private final XboxHostMapper xboxHostMapper;
    private final TaskMapper taskMapper;
    private final AgentInstanceMapper agentInstanceMapper;
    private final DataSecurityUtil dataSecurityUtil;

    @Override
    public DashboardStatsResponse getStats() {
        DashboardStatsResponse stats = new DashboardStatsResponse();

        if (dataSecurityUtil.isPlatformAdmin()) {
            stats.setMerchantCount(getMerchantCount());
            stats.setMerchantUserCount(getMerchantUserCount());
            stats.setStreamingAccountCount(getStreamingAccountCount());
            stats.setGameAccountCount(getGameAccountCount());
            stats.setXboxHostCount(getXboxHostCount());
            stats.setTaskCount(getTaskCount());
            stats.setRunningTaskCount(getRunningTaskCount());
            stats.setAgentCount(getAgentCount());
            stats.setOnlineAgentCount(getOnlineAgentCount());
        } else {
            String merchantId = UserContext.getMerchantId();
            stats.setMerchantUserCount(getMerchantUserCountByMerchant(merchantId));
            stats.setStreamingAccountCount(getStreamingAccountCountByMerchant(merchantId));
            stats.setGameAccountCount(getGameAccountCountByMerchant(merchantId));
            stats.setXboxHostCount(getXboxHostCountByMerchant(merchantId));
            stats.setTaskCount(getTaskCountByMerchant(merchantId));
            stats.setRunningTaskCount(getRunningTaskCountByMerchant(merchantId));
            stats.setAgentCount(getAgentCountByMerchant(merchantId));
            stats.setOnlineAgentCount(getOnlineAgentCountByMerchant(merchantId));
        }

        return stats;
    }

    private Long getMerchantCount() {
        return merchantMapper.selectCount(null);
    }

    private Long getMerchantUserCount() {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.ne(MerchantUser::getRole, "platform_admin");
        return merchantUserMapper.selectCount(wrapper);
    }

    private Long getStreamingAccountCount() {
        return streamingAccountMapper.selectCount(null);
    }

    private Long getGameAccountCount() {
        return gameAccountMapper.selectCount(null);
    }

    private Long getXboxHostCount() {
        return xboxHostMapper.selectCount(null);
    }

    private Long getTaskCount() {
        return taskMapper.selectCount(null);
    }

    private Long getRunningTaskCount() {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getStatus, "running");
        return taskMapper.selectCount(wrapper);
    }

    private Long getAgentCount() {
        return agentInstanceMapper.selectCount(null);
    }

    private Long getOnlineAgentCount() {
        return (long) AgentWebSocketEndpoint.getOnlineAgentCount();
    }

    private Long getMerchantUserCountByMerchant(String merchantId) {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantUser::getMerchantId, merchantId);
        return merchantUserMapper.selectCount(wrapper);
    }

    private Long getStreamingAccountCountByMerchant(String merchantId) {
        LambdaQueryWrapper<StreamingAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccount::getMerchantId, merchantId);
        return streamingAccountMapper.selectCount(wrapper);
    }

    private Long getGameAccountCountByMerchant(String merchantId) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getMerchantId, merchantId);
        return gameAccountMapper.selectCount(wrapper);
    }

    private Long getXboxHostCountByMerchant(String merchantId) {
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(XboxHost::getMerchantId, merchantId);
        return xboxHostMapper.selectCount(wrapper);
    }

    private Long getTaskCountByMerchant(String merchantId) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getMerchantId, merchantId);
        return taskMapper.selectCount(wrapper);
    }

    private Long getRunningTaskCountByMerchant(String merchantId) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getMerchantId, merchantId)
                .eq(Task::getStatus, "running");
        return taskMapper.selectCount(wrapper);
    }

    private Long getAgentCountByMerchant(String merchantId) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getMerchantId, merchantId);
        return agentInstanceMapper.selectCount(wrapper);
    }

    private Long getOnlineAgentCountByMerchant(String merchantId) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getMerchantId, merchantId)
                .eq(AgentInstance::getStatus, "online");
        return agentInstanceMapper.selectCount(wrapper);
    }
}
