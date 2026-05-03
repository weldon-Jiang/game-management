package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

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
        if (findByAgentId(instance.getAgentId()) != null) {
            throw new BusinessException(ResultCode.AgentInstance.AGENT_ID_DUPLICATE);
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
        wrapper.eq(AgentInstance::getDeleted, false);
        return agentInstanceMapper.selectOne(wrapper);
    }

    @Override
    public List<AgentInstance> findAll() {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getDeleted, false);
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        List<AgentInstance> instances = agentInstanceMapper.selectList(wrapper);
        populateMerchantNames(instances);
        return instances;
    }

    @Override
    public IPage<AgentInstance> findAll(AgentInstancePageRequest request) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getDeleted, false);
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
        wrapper.eq(AgentInstance::getDeleted, false);
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        return agentInstanceMapper.selectList(wrapper);
    }

    @Override
    public IPage<AgentInstance> findPageByMerchantId(String merchantId, AgentInstancePageRequest request) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getMerchantId, merchantId);
        wrapper.eq(AgentInstance::getDeleted, false);
        wrapper.orderByDesc(AgentInstance::getCreatedTime);
        Page<AgentInstance> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return agentInstanceMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<AgentInstance> findPageWithFilters(AgentInstancePageRequest request) {
        LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentInstance::getDeleted, false);
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
        agentInstanceMapper.update(instance, wrapper);
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
        }
        if (currentTaskId != null) {
            instance.setCurrentTaskId(currentTaskId);
        }
        if (currentStreamingId != null) {
            instance.setCurrentStreamingId(currentStreamingId);
        }
        if (version != null) {
            instance.setVersion(version);
        }
        agentInstanceMapper.updateById(instance);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindStreaming(String id, String streamingId) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setCurrentStreamingId(streamingId);
        agentInstanceMapper.updateById(instance);
        log.info("Agent绑定流媒体账号 - AgentID: {}, StreamingID: {}", id, streamingId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindStreaming(String id) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setCurrentStreamingId(null);
        agentInstanceMapper.updateById(instance);
        log.info("Agent解绑流媒体账号 - AgentID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindTask(String id, String taskId) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setCurrentTaskId(taskId);
        agentInstanceMapper.updateById(instance);
        log.info("Agent绑定任务 - AgentID: {}, TaskID: {}", id, taskId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindTask(String id) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setCurrentTaskId(null);
        agentInstanceMapper.updateById(instance);
        log.info("Agent解绑任务 - AgentID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        AgentInstance instance = agentInstanceMapper.selectById(id);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }

        instance.setDeleted(true);
        instance.setStatus("deleted");
        agentInstanceMapper.updateById(instance);
        log.info("删除Agent实例 - ID: {}", id);
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
}
