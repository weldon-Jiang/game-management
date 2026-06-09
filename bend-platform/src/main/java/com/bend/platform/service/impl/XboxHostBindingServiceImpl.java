package com.bend.platform.service.impl;

import com.bend.platform.entity.XboxHost;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.service.StreamingAccountHostBindingService;
import com.bend.platform.service.XboxHostBindingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Xbox主机绑定服务实现（M:N 绑定表）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class XboxHostBindingServiceImpl implements XboxHostBindingService {

    private final XboxHostMapper xboxHostMapper;
    private final StreamingAccountHostBindingService hostBindingService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bind(String hostId, String streamingAccountId, String gamertag) {
        hostBindingService.bindManual(hostId, streamingAccountId, gamertag);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbind(String hostId) {
        hostBindingService.unbindAllForHost(hostId);
    }

    @Override
    public String getBoundStreamingAccountId(String hostId) {
        return hostBindingService.getPrimaryBoundStreamingAccountId(hostId);
    }

    @Override
    public String getBoundGamertag(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        return host != null ? host.getBoundGamertag() : null;
    }

    @Override
    public boolean isBound(String hostId) {
        return hostBindingService.isHostBound(hostId);
    }

    @Override
    public XboxHost getHostWithBindingInfo(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        if (host == null) {
            return null;
        }
        host.setBoundStreamingAccountId(hostBindingService.getPrimaryBoundStreamingAccountId(hostId));
        return host;
    }
}
