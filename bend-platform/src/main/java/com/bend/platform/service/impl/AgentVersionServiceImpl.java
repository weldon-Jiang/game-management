package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.AgentVersionPageRequest;
import com.bend.platform.entity.AgentVersion;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.AgentVersionMapper;
import com.bend.platform.service.AgentVersionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Agent版本服务实现
 *
 * 功能说明：
 * - 管理Agent版本信息
 * - 支持版本发布和撤销
 *
 * 主要功能：
 * - 创建Agent版本
 * - 查询所有版本
 * - 分页查询版本
 * - 发布版本
 * - 撤销发布版本
 * - 删除版本
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentVersionServiceImpl implements AgentVersionService {

    private final AgentVersionMapper agentVersionMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentVersion create(AgentVersion version) {
        if (findByVersion(version.getVersion()) != null) {
            throw new BusinessException(ResultCode.AgentVersion.VERSION_EXISTS, "版本号已存在");
        }
        agentVersionMapper.insert(version);
        log.info("创建Agent版本 - 版本: {}", version.getVersion());
        return version;
    }

    @Override
    public AgentVersion findById(String id) {
        return agentVersionMapper.selectById(id);
    }

    @Override
    public AgentVersion findByVersion(String version) {
        LambdaQueryWrapper<AgentVersion> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentVersion::getVersion, version);
        wrapper.eq(AgentVersion::getDeleted, false);
        return agentVersionMapper.selectOne(wrapper);
    }

    @Override
    public List<AgentVersion> findAll() {
        LambdaQueryWrapper<AgentVersion> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentVersion::getDeleted, false);
        wrapper.orderByDesc(AgentVersion::getCreatedTime);
        return agentVersionMapper.selectList(wrapper);
    }

    @Override
    public List<AgentVersion> findActive() {
        LambdaQueryWrapper<AgentVersion> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentVersion::getDeleted, false);
        wrapper.eq(AgentVersion::getStatus, 1);
        wrapper.orderByDesc(AgentVersion::getCreatedTime);
        return agentVersionMapper.selectList(wrapper);
    }

    @Override
    public IPage<AgentVersion> findPage(AgentVersionPageRequest request) {
        LambdaQueryWrapper<AgentVersion> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentVersion::getDeleted, false);
        wrapper.orderByDesc(AgentVersion::getCreatedTime);
        Page<AgentVersion> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return agentVersionMapper.selectPage(page, wrapper);
    }

    @Override
    public AgentVersion findLatest() {
        LambdaQueryWrapper<AgentVersion> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentVersion::getDeleted, false);
        wrapper.eq(AgentVersion::getStatus, 1);
        wrapper.orderByDesc(AgentVersion::getCreatedTime);
        wrapper.last("LIMIT 1");
        return agentVersionMapper.selectOne(wrapper);
    }

    @Override
    public AgentVersion findLatestMandatory() {
        LambdaQueryWrapper<AgentVersion> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentVersion::getDeleted, false);
        wrapper.eq(AgentVersion::getStatus, 1);
        wrapper.eq(AgentVersion::getMandatory, 1);
        wrapper.orderByDesc(AgentVersion::getCreatedTime);
        wrapper.last("LIMIT 1");
        return agentVersionMapper.selectOne(wrapper);
    }

    @Override
    public AgentVersion findUpdate(String currentVersion) {
        AgentVersion latest = findLatest();
        if (latest == null) {
            return null;
        }

        String latestVersion = latest.getVersion();
        if (compareVersions(currentVersion, latestVersion) < 0) {
            if (latest.getMandatory() != null && latest.getMandatory() == 1) {
                latest.setMandatory(1);
            } else {
                latest.setMandatory(0);
            }
            return latest;
        }
        return null;
    }

    private int compareVersions(String v1, String v2) {
        String[] parts1 = v1.split("\\.");
        String[] parts2 = v2.split("\\.");
        int length = Math.max(parts1.length, parts2.length);
        for (int i = 0; i < length; i++) {
            int p1 = i < parts1.length ? Integer.parseInt(parts1[i]) : 0;
            int p2 = i < parts2.length ? Integer.parseInt(parts2[i]) : 0;
            if (p1 != p2) {
                return p1 - p2;
            }
        }
        return 0;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentVersion publish(AgentVersion version) {
        version.setStatus(1);
        if (version.getId() == null) {
            return create(version);
        }
        agentVersionMapper.updateById(version);
        log.info("发布Agent版本 - 版本: {}", version.getVersion());
        return version;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unpublish(String id) {
        AgentVersion version = findById(id);
        if (version == null) {
            throw new BusinessException(ResultCode.AgentVersion.NOT_FOUND, "版本不存在");
        }
        version.setStatus(0);
        agentVersionMapper.updateById(version);
        log.info("取消发布Agent版本 - 版本: {}", version.getVersion());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        AgentVersion version = findById(id);
        if (version == null) {
            throw new BusinessException(ResultCode.AgentVersion.NOT_FOUND, "版本不存在");
        }
        version.setDeleted(true);
        agentVersionMapper.updateById(version);
        log.info("删除Agent版本 - ID: {}", id);
    }
}
