package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.AgentInstancePageRequest;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.entity.Merchant;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.util.DataSecurityUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import com.bend.platform.websocket.AgentWebSocketEndpoint;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Agent实例服务实现类
 *
 * 功能说明：
 * - 管理Agent实例的CRUD操作
 * - Agent实例是注册到系统的Agent进程
 *
 * 主要功能：
 * - 创建Agent实例
 * - 查询所有实例
 * - 分页查询实例
 * - 根据商户ID查询实例
 * - 更新实例状态
 * - 删除实例
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentInstanceServiceImpl implements AgentInstanceService {

    private final AgentInstanceMapper agentInstanceMapper;
    private final MerchantMapper merchantMapper;
    private final DataSecurityUtil dataSecurityUtil;

    private static final Map<String, String> merchantNameCache = new HashMap<>();

    private void populateMerchantNames(List<AgentInstance> instances) {
        if (instances == null || instances.isEmpty()) {
            return;
        }
        for (AgentInstance instance : instances) {
            if (instance.getMerchantId() != null) {
                String merchantName = merchantNameCache.get(instance.getMerchantId());
                if (merchantName == null) {
                    Merchant merchant = merchantMapper.selectById(instance.getMerchantId());
                    merchantName = merchant != null ? merchant.getName() : instance.getMerchantId();
                    merchantNameCache.put(instance.getMerchantId(), merchantName);
                }
                instance.setMerchantName(merchantName);
            }
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentInstance create(AgentInstance instance) {
        AgentInstance existing = findByAgentId(instance.getAgentId());
        
        if (existing != null) {
            throw new BusinessException(ResultCode.AgentInstance.AGENT_ID_DUPLICATE);
        }

        AgentInstance deletedInstance = findByAgentIdIncludeDeleted(instance.getAgentId());
        if (deletedInstance != null && Boolean.TRUE.equals(deletedInstance.getDeleted())) {
            log.info("恢复已删除的Agent实例 - AgentID: {}", instance.getAgentId());
            deletedInstance.setDeleted(false);
            deletedInstance.setStatus("online");
            deletedInstance.setLastHeartbeat(LocalDateTime.now());
            deletedInstance.setLastOnlineTime(LocalDateTime.now());
            deletedInstance.setHost(instance.getHost());
            deletedInstance.setPort(instance.getPort());
            deletedInstance.setVersion(instance.getVersion());
            deletedInstance.setOsType(instance.getOsType());
            deletedInstance.setOsVersion(instance.getOsVersion());
            deletedInstance.setCpuCount(instance.getCpuCount());
            deletedInstance.setMaxConcurrentTasks(instance.getMaxConcurrentTasks());
            deletedInstance.setUninstallReason(null);
            agentInstanceMapper.updateById(deletedInstance);
            log.info("Agent实例已恢复 - ID: {}, AgentID: {}", deletedInstance.getId(), deletedInstance.getAgentId());
            return deletedInstance;
        }

        instance.setStatus("online");
        if (instance.getLastHeartbeat() == null) {
            instance.setLastHeartbeat(LocalDateTime.now());
        }
        if (instance.getLastOnlineTime() == null) {
            instance.setLastOnlineTime(LocalDateTime.now());
        }

        agentInstanceMapper.insert(instance);
        log.info("创建Agent实例 - ID: {}, AgentID: {}", instance.getId(), instance.getAgentId());
        return instance;
    }

    @Override
    public AgentInstance findById(String id) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance != null) {
            dataSecurityUtil.validateMerchantAccess(instance.getMerchantId(), "AgentInstance");
        }
        return instance;
    }

    @Override
    public AgentInstance findByAgentId(String agentId) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getAgentId, agentId);
        return agentInstanceMapper.selectOne(wrapper);
    }

    @Override
    public AgentInstance findByAgentIdIncludeDeleted(String agentId) {
        return agentInstanceMapper.selectByAgentIdIncludeDeleted(agentId);
    }

    @Override
    public AgentInstance findByRegistrationCode(String registrationCode) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getRegistrationCode, registrationCode);
        return agentInstanceMapper.selectOne(wrapper);
    }

    @Override
    public List<AgentInstance> findAll() {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        List<AgentInstance> instances = agentInstanceMapper.selectList(wrapper);
        populateMerchantNames(instances);
        return instances;
    }

    @Override
    public List<AgentInstance> findAllOnline() {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getStatus, "online");
        wrapper.orderByDesc(AgentInstance::getLastHeartbeat);
        List<AgentInstance> instances = agentInstanceMapper.selectList(wrapper);
        
        LocalDateTime fiveMinutesAgo = LocalDateTime.now().minusMinutes(5);
        List<AgentInstance> trulyOnline = new ArrayList<>();
        for (AgentInstance instance : instances) {
            // 检查条件：WebSocket连接已建立 并且 最近5分钟内有心跳
            // 只有WebSocket连接正常的Agent才能接收任务指令
            boolean hasWebSocket = AgentWebSocketEndpoint.isAgentOnline(instance.getAgentId());
            boolean hasRecentHeartbeat = instance.getLastHeartbeat() != null && 
                                        instance.getLastHeartbeat().isAfter(fiveMinutesAgo);
            
            if (hasWebSocket && hasRecentHeartbeat) {
                trulyOnline.add(instance);
            }
        }
        
        populateMerchantNames(trulyOnline);
        return trulyOnline;
    }

    @Override
    public IPage<AgentInstance> findAll(AgentInstancePageRequest request) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        Page<AgentInstance> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        IPage<AgentInstance> result = agentInstanceMapper.selectPage(page, wrapper);
        populateMerchantNames(result.getRecords());
        return result;
    }

    @Override
    public List<AgentInstance> findAllByMerchantId(String merchantId) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getMerchantId, merchantId);
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        return agentInstanceMapper.selectList(wrapper);
    }

    @Override
    public IPage<AgentInstance> findPageByMerchantId(String merchantId, AgentInstancePageRequest request) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getMerchantId, merchantId);
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        Page<AgentInstance> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return agentInstanceMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<AgentInstance> findPageWithFilters(AgentInstancePageRequest request) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(AgentInstance::getStatus, request.getStatus());
        }
        if (StringUtils.hasText(request.getMerchantId())) {
            wrapper.eq(AgentInstance::getMerchantId, request.getMerchantId());
        }
        wrapper.orderByDesc(AgentInstance::getLastHeartbeat);
        Page<AgentInstance> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        IPage<AgentInstance> result = agentInstanceMapper.selectPage(page, wrapper);
        populateMerchantNames(result.getRecords());
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateStatus(String id, String status) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setStatus(status);
        if ("offline".equals(status)) {
            instance.setLastOnlineTime(LocalDateTime.now());
        }
        agentInstanceMapper.updateById(instance);
        log.info("更新Agent实例状态 - ID: {}, 新状态: {}", id, status);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateByAgentId(AgentInstance instance) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getAgentId, instance.getAgentId());
        int updated = agentInstanceMapper.update(instance, wrapper);
        
        if (updated == 0) {
            AgentInstance deletedInstance = findByAgentIdIncludeDeleted(instance.getAgentId());
            if (deletedInstance != null) {
                deletedInstance.setDeleted(false);
                deletedInstance.setStatus("online");
                deletedInstance.setLastHeartbeat(LocalDateTime.now());
                deletedInstance.setLastOnlineTime(LocalDateTime.now());
                deletedInstance.setHost(instance.getHost());
                deletedInstance.setPort(instance.getPort());
                deletedInstance.setVersion(instance.getVersion());
                deletedInstance.setOsType(instance.getOsType());
                deletedInstance.setOsVersion(instance.getOsVersion());
                deletedInstance.setCpuCount(instance.getCpuCount());
                deletedInstance.setMaxConcurrentTasks(instance.getMaxConcurrentTasks());
                deletedInstance.setUninstallReason(null);
                agentInstanceMapper.updateById(deletedInstance);
                log.info("已删除的Agent实例已恢复并更新 - AgentID: {}", instance.getAgentId());
            }
        }
        log.debug("更新Agent实例 - AgentID: {}", instance.getAgentId());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateHeartbeat(String id) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setLastHeartbeat(LocalDateTime.now());
        agentInstanceMapper.updateById(instance);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean validateCredentials(String agentId, String agentSecret) {
        AgentInstance instance = findByAgentId(agentId);
        if (instance == null || instance.getAgentSecret() == null) {
            return false;
        }
        return MessageDigest.isEqual(
            agentSecret.getBytes(StandardCharsets.UTF_8),
            instance.getAgentSecret().getBytes(StandardCharsets.UTF_8)
        );
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateHeartbeat(String agentId, String status, String currentTaskId, String currentStreamingId, String version) {
        AgentInstance instance = findByAgentId(agentId);
        if (instance == null) {
            return;
        }

        instance.setLastHeartbeat(LocalDateTime.now());
        
        if (status != null) {
            instance.setStatus(status);
        } else if (!"online".equals(instance.getStatus())) {
            instance.setStatus("online");
            instance.setLastOnlineTime(LocalDateTime.now());
        }
        
        if (version != null) {
            instance.setVersion(version);
        }
        agentInstanceMapper.updateById(instance);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindStreaming(String id, String streamingId) {
        log.info("Agent绑定流媒体账号已废弃 - AgentID: {}, StreamingID: {} (任务状态请通过task表查询)", id, streamingId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindStreaming(String id) {
        log.info("Agent解绑流媒体账号已废弃 - AgentID: {} (任务状态请通过task表查询)", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindTask(String id, String taskId) {
        log.info("Agent绑定任务已废弃 - AgentID: {}, TaskID: {} (任务状态请通过task表查询)", id, taskId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindTask(String id) {
        log.info("Agent解绑任务已废弃 - AgentID: {} (任务状态请通过task表查询)", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        agentInstanceMapper.deleteById(id);
        log.info("物理删除Agent实例 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteByAgentId(String agentId) {
        AgentInstance instance = findByAgentId(agentId);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getAgentId, agentId);
        agentInstanceMapper.delete(wrapper);
        log.info("物理删除Agent实例 - AgentID: {}", agentId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int cleanupUninstalled(String merchantId) {
        LambdaQueryWrapper<AgentInstance> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(AgentInstance::getStatus, "uninstalled");

        if (StringUtils.hasText(merchantId)) {
            queryWrapper.eq(AgentInstance::getMerchantId, merchantId);
        }

        List<AgentInstance> uninstalledAgents = agentInstanceMapper.selectList(queryWrapper);
        if (uninstalledAgents.isEmpty()) {
            return 0;
        }

        agentInstanceMapper.delete(queryWrapper);

        log.info("物理清理已卸载Agent - 商户ID: {}, 数量: {}", merchantId, uninstalledAgents.size());
        return uninstalledAgents.size();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int cleanupOffline(int offlineMinutes, String merchantId) {
        LocalDateTime cutoffTime = LocalDateTime.now().minusMinutes(offlineMinutes);

        LambdaQueryWrapper<AgentInstance> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(AgentInstance::getStatus, "offline")
               .lt(AgentInstance::getLastHeartbeat, cutoffTime);

        if (StringUtils.hasText(merchantId)) {
            queryWrapper.eq(AgentInstance::getMerchantId, merchantId);
        }

        List<AgentInstance> offlineAgents = agentInstanceMapper.selectList(queryWrapper);
        if (offlineAgents.isEmpty()) {
            return 0;
        }

        agentInstanceMapper.delete(queryWrapper);

        log.info("物理清理离线Agent - 商户ID: {}, 离线阈值: {}分钟, 数量: {}", 
                merchantId, offlineMinutes, offlineAgents.size());
        return offlineAgents.size();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int batchDelete(List<String> agentIds) {
        if (agentIds == null || agentIds.isEmpty()) {
            return 0;
        }

        LambdaQueryWrapper<AgentInstance> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(AgentInstance::getAgentId, agentIds);

        List<AgentInstance> agents = agentInstanceMapper.selectList(queryWrapper);
        if (agents.isEmpty()) {
            return 0;
        }

        agentInstanceMapper.delete(queryWrapper);

        log.info("物理批量删除Agent - 数量: {}", agents.size());
        return agents.size();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void offlineByTimeout(int minutes) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getStatus, "online")
               .lt(AgentInstance::getLastHeartbeat, LocalDateTime.now().minusMinutes(minutes));

        List<AgentInstance> timeoutAgents = agentInstanceMapper.selectList(wrapper);
        if (timeoutAgents.isEmpty()) {
            return;
        }

        for (AgentInstance agent : timeoutAgents) {
            agent.setStatus("offline");
            agent.setLastOnlineTime(LocalDateTime.now());
            agentInstanceMapper.updateById(agent);
        }

        log.info("批量下线超时Agent - 数量: {}", timeoutAgents.size());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentInstance updateAgentName(String agentId, String agentName) {
        String normalizedName = agentName == null ? null : agentName.trim();
        if (!StringUtils.hasText(normalizedName)) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "Agent名称不能为空");
        }

        AgentInstance instance = findByAgentId(agentId);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        if (existsAgentNameInMerchant(instance.getMerchantId(), normalizedName, instance.getId())) {
            throw new BusinessException(ResultCode.AgentInstance.AGENT_NAME_DUPLICATE);
        }

        instance.setAgentName(normalizedName);
        agentInstanceMapper.updateById(instance);
        populateMerchantNames(List.of(instance));
        log.info("更新Agent名称 - AgentID: {}, AgentName: {}", agentId, normalizedName);
        return instance;
    }

    @Override
    public Map<String, String> resolveDisplayNames(Collection<String> agentIds) {
        if (agentIds == null || agentIds.isEmpty()) {
            return Collections.emptyMap();
        }

        List<String> ids = agentIds.stream()
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());
        if (ids.isEmpty()) {
            return Collections.emptyMap();
        }

        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(AgentInstance::getAgentId, ids);
        List<AgentInstance> agents = agentInstanceMapper.selectList(wrapper);

        Map<String, String> result = new HashMap<>();
        for (AgentInstance agent : agents) {
            result.put(agent.getAgentId(), toDisplayName(agent));
        }
        for (String id : ids) {
            result.putIfAbsent(id, id);
        }
        return result;
    }

    @Override
    public String resolveDisplayName(String agentId) {
        if (!StringUtils.hasText(agentId)) {
            return agentId;
        }
        AgentInstance agent = findByAgentId(agentId);
        return agent == null ? agentId : toDisplayName(agent);
    }

    private boolean existsAgentNameInMerchant(String merchantId, String agentName, String excludeId) {
        if (!StringUtils.hasText(merchantId) || !StringUtils.hasText(agentName)) {
            return false;
        }
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getMerchantId, merchantId)
                .eq(AgentInstance::getAgentName, agentName)
                .ne(StringUtils.hasText(excludeId), AgentInstance::getId, excludeId);
        return agentInstanceMapper.selectCount(wrapper) > 0;
    }

    private String toDisplayName(AgentInstance agent) {
        if (agent == null) {
            return null;
        }
        if (StringUtils.hasText(agent.getAgentName())) {
            return agent.getAgentName();
        }
        if (StringUtils.hasText(agent.getHost())) {
            return agent.getHost();
        }
        return agent.getAgentId();
    }
}
