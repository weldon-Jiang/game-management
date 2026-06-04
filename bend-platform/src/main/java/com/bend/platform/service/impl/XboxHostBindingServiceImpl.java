package com.bend.platform.service.impl;

import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.XboxHostBindingService;
import com.bend.platform.util.PlatformTypeUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Xbox主机绑定服务实现
 * 
 * 功能说明：
 * - 封装主机绑定逻辑，与自动化任务解耦
 * - 提供独立的绑定管理能力
 * - 便于未来扩展为中间表实现
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class XboxHostBindingServiceImpl implements XboxHostBindingService {

    private final XboxHostMapper xboxHostMapper;
    private final StreamingAccountMapper streamingAccountMapper;
    private final MerchantService merchantService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bind(String hostId, String streamingAccountId, String gamertag) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        StreamingAccount streamingAccount = streamingAccountMapper.selectById(streamingAccountId);
        if (streamingAccount == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        PlatformTypeUtil.requireSamePlatform(host.getPlatform(), streamingAccount.getPlatform(),
                "主机平台与流媒体账号不一致，无法绑定");

        merchantService.validateMerchantActive(host.getMerchantId());

        if (host.getBoundStreamingAccountId() != null) {
            throw new BusinessException(ResultCode.XboxHost.ALREADY_BOUND);
        }

        host.setBoundStreamingAccountId(streamingAccountId);
        host.setBoundGamertag(gamertag);
        xboxHostMapper.updateById(host);
        log.info("绑定流媒体账号 - Xbox主机ID: {}, 流媒体账号ID: {}", hostId, streamingAccountId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbind(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        merchantService.validateMerchantActive(host.getMerchantId());

        host.setBoundStreamingAccountId(null);
        host.setBoundGamertag(null);
        xboxHostMapper.updateById(host);
        log.info("解绑流媒体账号 - Xbox主机ID: {}", hostId);
    }

    @Override
    public String getBoundStreamingAccountId(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        return host != null ? host.getBoundStreamingAccountId() : null;
    }

    @Override
    public String getBoundGamertag(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        return host != null ? host.getBoundGamertag() : null;
    }

    @Override
    public boolean isBound(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        return host != null && host.getBoundStreamingAccountId() != null;
    }

    @Override
    public XboxHost getHostWithBindingInfo(String hostId) {
        return xboxHostMapper.selectById(hostId);
    }
}
