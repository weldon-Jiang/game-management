package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.XboxHostPageRequest;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.StreamingAccountLoginRecordService;
import com.bend.platform.service.XboxHostService;
import com.bend.platform.util.DataSecurityUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Xbox主机服务实现类
 *
 * 功能说明：
 * - 管理Xbox主机设备的CRUD操作
 * - 提供主机与流媒体账号的绑定关系
 *
 * 主要功能：
 * - 创建Xbox主机
 * - 分页查询主机
 * - 根据商户ID查询主机
 * - 更新主机信息
 * - 绑定/解绑流媒体账号
 * - 获取主机可用的流媒体账号
 * - 删除主机
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class XboxHostServiceImpl implements XboxHostService {

    private final XboxHostMapper xboxHostMapper;
    private final StreamingAccountLoginRecordService loginRecordService;
    private final MerchantService merchantService;
    private final DataSecurityUtil dataSecurityUtil;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public XboxHost create(String merchantId, String xboxId, String name, String ipAddress) {
        // 校验商户是否有效
        merchantService.validateMerchantActive(merchantId);

        if (merchantId == null || xboxId == null) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "merchantId和xboxId不能为空");
        }

        if (findByXboxId(xboxId) != null) {
            throw new BusinessException(ResultCode.XboxHost.XBOX_ID_DUPLICATE);
        }

        XboxHost host = new XboxHost();
        host.setMerchantId(merchantId);
        host.setXboxId(xboxId);
        host.setName(name);
        host.setIpAddress(ipAddress);
        host.setStatus("offline");

        xboxHostMapper.insert(host);
        log.info("创建Xbox主机成功 - ID: {}, XboxID: {}", host.getId(), xboxId);
        return host;
    }

    @Override
    public XboxHost findById(String id) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host != null) {
            dataSecurityUtil.validateMerchantAccess(host.getMerchantId(), "XboxHost");
        }
        return host;
    }

    @Override
    public XboxHost findByXboxId(String xboxId) {
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(XboxHost::getXboxId, xboxId);
        return xboxHostMapper.selectOne(wrapper);
    }

    @Override
    public IPage<XboxHost> findByMerchantId(String merchantId, XboxHostPageRequest request) {
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(XboxHost::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(XboxHost::getCreatedTime);
        Page<XboxHost> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return xboxHostMapper.selectPage(page, wrapper);
    }

    @Override
    public List<XboxHost> findAllByMerchantId(String merchantId) {
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(XboxHost::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(XboxHost::getCreatedTime);
        return xboxHostMapper.selectList(wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String id, String name, String ipAddress) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(host.getMerchantId());

        if (name != null) {
            host.setName(name);
        }
        if (ipAddress != null) {
            host.setIpAddress(ipAddress);
        }

        xboxHostMapper.updateById(host);
        log.info("更新Xbox主机 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateStatus(String id, String status) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!isValidStatus(status)) {
            throw new BusinessException(ResultCode.XboxHost.POWER_STATE_INVALID);
        }

        host.setStatus(status);
        host.setLastSeenTime(LocalDateTime.now());
        xboxHostMapper.updateById(host);
        log.info("更新Xbox主机状态 - ID: {}, 新状态: {}", id, status);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindStreamingAccount(String id, String streamingAccountId, String gamertag) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(host.getMerchantId());

        if (host.getBoundStreamingAccountId() != null) {
            throw new BusinessException(ResultCode.XboxHost.ALREADY_BOUND);
        }

        host.setBoundStreamingAccountId(streamingAccountId);
        host.setBoundGamertag(gamertag);
        xboxHostMapper.updateById(host);
        log.info("绑定流媒体账号 - Xbox主机ID: {}, 流媒体账号ID: {}", id, streamingAccountId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindStreamingAccount(String id) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(host.getMerchantId());

        host.setBoundStreamingAccountId(null);
        host.setBoundGamertag(null);
        xboxHostMapper.updateById(host);
        log.info("解绑流媒体账号 - Xbox主机ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void lock(String id, String agentId, LocalDateTime expireTime) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(host.getMerchantId());

        host.setLockedByAgentId(agentId);
        host.setLockExpiresTime(expireTime);
        host.setLockedTime(LocalDateTime.now());
        xboxHostMapper.updateById(host);
        log.info("锁定Xbox主机 - ID: {}, AgentID: {}", id, agentId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unlock(String id) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(host.getMerchantId());

        host.setLockedByAgentId(null);
        host.setLockExpiresTime(null);
        host.setLockedTime(null);
        xboxHostMapper.updateById(host);
        log.info("解锁Xbox主机 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        XboxHost host = xboxHostMapper.selectById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        // 校验商户是否有效
        merchantService.validateMerchantActive(host.getMerchantId());

        xboxHostMapper.deleteById(id);
        log.info("删除Xbox主机 - ID: {}", id);
    }

    private boolean isValidStatus(String status) {
        return "online".equals(status) || "offline".equals(status) || "error".equals(status);
    }

    @Override
    public List<String> getAvailableStreamingAccounts(String id) {
        return loginRecordService.findByXboxHostId(id).stream()
                .map(r -> r.getStreamingAccountId())
                .collect(Collectors.toList());
    }
}