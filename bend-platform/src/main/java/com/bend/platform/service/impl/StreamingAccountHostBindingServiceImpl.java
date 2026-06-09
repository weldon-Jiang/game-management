package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.StreamingAccountHostBinding;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.enums.HostBindingSource;
import com.bend.platform.enums.HostBindingStatus;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountHostBindingMapper;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.StreamingAccountHostBindingService;
import com.bend.platform.service.XboxHostService;
import com.bend.platform.util.PlatformTypeUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * 流媒体账号与主机 M:N 绑定服务实现。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StreamingAccountHostBindingServiceImpl implements StreamingAccountHostBindingService {

    private final StreamingAccountHostBindingMapper bindingMapper;
    private final XboxHostMapper xboxHostMapper;
    private final StreamingAccountMapper streamingAccountMapper;
    private final XboxHostService xboxHostService;
    private final MerchantService merchantService;

    @Override
    public List<XboxHost> findActiveHostsByAccount(String streamingAccountId) {
        List<String> hostIds = findActiveHostIds(streamingAccountId);
        List<XboxHost> hosts = new ArrayList<>();
        for (String hostId : hostIds) {
            XboxHost host = xboxHostMapper.selectById(hostId);
            if (host != null) {
                hosts.add(host);
            }
        }
        return hosts;
    }

    @Override
    public boolean hasActiveBinding(String streamingAccountId, String xboxHostId) {
        if (!StringUtils.hasText(streamingAccountId) || !StringUtils.hasText(xboxHostId)) {
            return false;
        }
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = activeBindingWrapper()
                .eq(StreamingAccountHostBinding::getStreamingAccountId, streamingAccountId)
                .eq(StreamingAccountHostBinding::getXboxHostId, xboxHostId);
        return bindingMapper.selectCount(wrapper) > 0;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindManual(String hostId, String streamingAccountId, String gamertag) {
        XboxHost host = requireHost(hostId);
        StreamingAccount account = requireStreamingAccount(streamingAccountId);
        validateSameMerchant(host, account);
        PlatformTypeUtil.requireSamePlatform(host.getPlatform(), account.getPlatform(),
                "主机平台与流媒体账号不一致，无法绑定");
        merchantService.validateMerchantActive(host.getMerchantId());

        upsertActiveBinding(
                host.getMerchantId(),
                streamingAccountId,
                hostId,
                HostBindingSource.MANUAL.getCode());
        syncLegacyHostBinding(host, streamingAccountId, gamertag);
        log.info("手动绑定主机 - hostId={}, streamingAccountId={}", hostId, streamingAccountId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindAllForHost(String hostId) {
        XboxHost host = requireHost(hostId);
        merchantService.validateMerchantActive(host.getMerchantId());

        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = activeBindingWrapper()
                .eq(StreamingAccountHostBinding::getXboxHostId, hostId);
        List<StreamingAccountHostBinding> bindings = bindingMapper.selectList(wrapper);
        for (StreamingAccountHostBinding binding : bindings) {
            binding.setStatus(HostBindingStatus.INACTIVE.getCode());
            bindingMapper.updateById(binding);
        }

        host.setBoundStreamingAccountId(null);
        host.setBoundGamertag(null);
        xboxHostMapper.updateById(host);
        log.info("解绑主机全部绑定 - hostId={}, count={}", hostId, bindings.size());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbind(String hostId, String streamingAccountId) {
        XboxHost host = requireHost(hostId);
        StreamingAccount account = requireStreamingAccount(streamingAccountId);
        validateSameMerchant(host, account);
        merchantService.validateMerchantActive(host.getMerchantId());

        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = activeBindingWrapper()
                .eq(StreamingAccountHostBinding::getXboxHostId, hostId)
                .eq(StreamingAccountHostBinding::getStreamingAccountId, streamingAccountId);
        StreamingAccountHostBinding binding = bindingMapper.selectOne(wrapper);
        if (binding == null) {
            throw new BusinessException(400, "该主机未绑定到此串流账号");
        }
        binding.setStatus(HostBindingStatus.INACTIVE.getCode());
        bindingMapper.updateById(binding);

        String primaryId = getPrimaryBoundStreamingAccountId(hostId);
        host.setBoundStreamingAccountId(primaryId);
        if (primaryId == null) {
            host.setBoundGamertag(null);
        }
        xboxHostMapper.updateById(host);
        log.info("解绑账号与主机 - hostId={}, streamingAccountId={}", hostId, streamingAccountId);
    }

    @Override
    public String getPrimaryBoundStreamingAccountId(String hostId) {
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = activeBindingWrapper()
                .eq(StreamingAccountHostBinding::getXboxHostId, hostId)
                .orderByAsc(StreamingAccountHostBinding::getCreatedTime)
                .last("LIMIT 1");
        StreamingAccountHostBinding binding = bindingMapper.selectOne(wrapper);
        if (binding != null) {
            return binding.getStreamingAccountId();
        }
        XboxHost host = xboxHostMapper.selectById(hostId);
        return host != null ? host.getBoundStreamingAccountId() : null;
    }

    @Override
    public boolean isHostBound(String hostId) {
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = activeBindingWrapper()
                .eq(StreamingAccountHostBinding::getXboxHostId, hostId);
        if (bindingMapper.selectCount(wrapper) > 0) {
            return true;
        }
        XboxHost host = xboxHostMapper.selectById(hostId);
        return host != null && StringUtils.hasText(host.getBoundStreamingAccountId());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public XboxHost ensureBinding(
            String merchantId,
            String streamingAccountId,
            String hostId,
            String serverId,
            String platform,
            String source,
            String name,
            String ipAddress,
            String gamertag) {
        StreamingAccount account = requireStreamingAccount(streamingAccountId);
        if (!merchantId.equals(account.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        String normalizedPlatform = PlatformTypeUtil.requireValid(
                StringUtils.hasText(platform) ? platform : account.getPlatform());
        PlatformTypeUtil.requireSamePlatform(normalizedPlatform, account.getPlatform(),
                "主机平台与流媒体账号不一致");

        XboxHost host = resolveHost(merchantId, hostId, serverId, normalizedPlatform, name, ipAddress);
        upsertActiveBinding(host.getMerchantId(), streamingAccountId, host.getId(),
                HostBindingSource.fromCode(source).getCode());
        syncLegacyHostBinding(host, streamingAccountId, gamertag);
        log.info("确保主机绑定 - hostId={}, streamingAccountId={}, source={}",
                host.getId(), streamingAccountId, source);
        return host;
    }

    private XboxHost resolveHost(
            String merchantId,
            String hostId,
            String serverId,
            String platform,
            String name,
            String ipAddress) {
        if (StringUtils.hasText(hostId)) {
            XboxHost host = requireHost(hostId);
            if (!merchantId.equals(host.getMerchantId())) {
                throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
            }
            return host;
        }
        if (!StringUtils.hasText(serverId)) {
            throw new BusinessException(400, "hostId 与 serverId 至少提供一个");
        }
        XboxHost host = xboxHostService.findByMerchantIdAndXboxId(merchantId, serverId);
        if (host == null) {
            host = xboxHostService.createOrUpdate(
                    merchantId,
                    serverId,
                    name,
                    ipAddress,
                    5050,
                    null,
                    null,
                    null,
                    null,
                    platform);
        }
        return host;
    }

    private void upsertActiveBinding(
            String merchantId,
            String streamingAccountId,
            String hostId,
            String source) {
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountHostBinding::getStreamingAccountId, streamingAccountId)
                .eq(StreamingAccountHostBinding::getXboxHostId, hostId);
        StreamingAccountHostBinding existing = bindingMapper.selectOne(wrapper);
        if (existing == null) {
            StreamingAccountHostBinding binding = new StreamingAccountHostBinding();
            binding.setMerchantId(merchantId);
            binding.setStreamingAccountId(streamingAccountId);
            binding.setXboxHostId(hostId);
            binding.setSource(source);
            binding.setStatus(HostBindingStatus.ACTIVE.getCode());
            bindingMapper.insert(binding);
            return;
        }
        boolean changed = false;
        if (!HostBindingStatus.ACTIVE.getCode().equals(existing.getStatus())) {
            existing.setStatus(HostBindingStatus.ACTIVE.getCode());
            changed = true;
        }
        if (StringUtils.hasText(source) && !source.equals(existing.getSource())) {
            existing.setSource(source);
            changed = true;
        }
        if (changed) {
            bindingMapper.updateById(existing);
        }
    }

    private void syncLegacyHostBinding(XboxHost host, String streamingAccountId, String gamertag) {
        if (!Objects.equals(host.getBoundStreamingAccountId(), streamingAccountId)) {
            host.setBoundStreamingAccountId(streamingAccountId);
        }
        if (StringUtils.hasText(gamertag)) {
            host.setBoundGamertag(gamertag);
        }
        xboxHostMapper.updateById(host);
    }

    private List<String> findActiveHostIds(String streamingAccountId) {
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = activeBindingWrapper()
                .eq(StreamingAccountHostBinding::getStreamingAccountId, streamingAccountId);
        return bindingMapper.selectList(wrapper).stream()
                .map(StreamingAccountHostBinding::getXboxHostId)
                .toList();
    }

    private LambdaQueryWrapper<StreamingAccountHostBinding> activeBindingWrapper() {
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountHostBinding::getStatus, HostBindingStatus.ACTIVE.getCode());
        return wrapper;
    }

    private XboxHost requireHost(String hostId) {
        XboxHost host = xboxHostMapper.selectById(hostId);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }
        return host;
    }

    private StreamingAccount requireStreamingAccount(String streamingAccountId) {
        StreamingAccount account = streamingAccountMapper.selectById(streamingAccountId);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }
        return account;
    }

    private void validateSameMerchant(XboxHost host, StreamingAccount account) {
        if (!host.getMerchantId().equals(account.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }
}
