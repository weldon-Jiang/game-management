package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.XboxHostPageRequest;
import com.bend.platform.entity.StreamingAccountHostBinding;
import com.bend.platform.entity.StreamingAccountLoginRecord;
import com.bend.platform.entity.StreamingSession;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.enums.HostBindingStatus;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountHostBindingMapper;
import com.bend.platform.repository.StreamingAccountLoginRecordMapper;
import com.bend.platform.repository.StreamingSessionMapper;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.service.CredentialTokenService;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.StreamingAccountLoginRecordService;
import com.bend.platform.service.XboxHostService;
import com.bend.platform.util.DataSecurityUtil;
import com.bend.platform.util.PlatformTypeUtil;
import com.bend.platform.util.XboxIdUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
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
    private final StreamingAccountHostBindingMapper hostBindingMapper;
    private final StreamingAccountLoginRecordService loginRecordService;
    private final StreamingAccountLoginRecordMapper loginRecordMapper;
    private final TaskMapper taskMapper;
    private final StreamingSessionMapper streamingSessionMapper;
    private final MerchantService merchantService;
    private final DataSecurityUtil dataSecurityUtil;
    private final CredentialTokenService credentialTokenService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public XboxHost create(String merchantId, String xboxId, String name, String ipAddress, String platform) {
        // 校验商户是否有效
        merchantService.validateMerchantActive(merchantId);

        if (merchantId == null || xboxId == null) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "merchantId和xboxId不能为空");
        }

        String canonicalXboxId = XboxIdUtil.normalizeCanonical(xboxId);
        if (findByMerchantIdAndDeviceIdentity(merchantId, canonicalXboxId, ipAddress, null, null) != null) {
            throw new BusinessException(ResultCode.XboxHost.XBOX_ID_DUPLICATE);
        }

        XboxHost host = new XboxHost();
        host.setMerchantId(merchantId);
        host.setXboxId(canonicalXboxId);
        host.setName(name);
        host.setIpAddress(ipAddress);
        host.setPlatform(PlatformTypeUtil.requireValid(platform));
        host.setStatus("offline");

        xboxHostMapper.insert(host);
        log.info("创建Xbox主机成功 - ID: {}, XboxID: {}", host.getId(), canonicalXboxId);
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
    public XboxHost requireForMerchant(String hostId, String merchantId) {
        if (!StringUtils.isNotBlank(hostId) || !StringUtils.isNotBlank(merchantId)) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID);
        }
        XboxHost host = xboxHostMapper.selectById(hostId);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }
        if (!merchantId.equals(host.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return host;
    }

    @Override
    public XboxHost findByMerchantIdAndXboxId(String merchantId, String xboxId) {
        return findByMerchantIdAndDeviceIdentity(merchantId, xboxId, null, null, null);
    }

    @Override
    public XboxHost findByMerchantIdAndDeviceIdentity(
            String merchantId,
            String xboxId,
            String ipAddress,
            String liveId,
            String macAddress) {
        return resolveExistingHost(merchantId, xboxId, ipAddress, liveId, macAddress, null, false);
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
    public boolean tryLock(String merchantId, String xboxHostId, String agentId, String taskId, int leaseSeconds) {
        if (!StringUtils.isNotBlank(merchantId) || xboxHostId == null || agentId == null || taskId == null) {
            return false;
        }
        LocalDateTime expireTime = LocalDateTime.now().plusSeconds(Math.max(30, leaseSeconds));
        int updated = xboxHostMapper.casLock(merchantId, xboxHostId, agentId, taskId, expireTime);
        if (updated > 0) {
            log.info("CAS 锁定 Xbox 成功 - id={}, agentId={}, taskId={}, expire={}",
                    xboxHostId, agentId, taskId, expireTime);
            return true;
        }
        log.warn("CAS 锁定 Xbox 失败 - id={}, agentId={}, taskId={}", xboxHostId, agentId, taskId);
        return false;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean unlock(String merchantId, String xboxHostId, String agentId, String taskId) {
        if (xboxHostId == null) {
            return false;
        }
        if (!StringUtils.isNotBlank(merchantId) || agentId == null || taskId == null) {
            return false;
        }
        int updated = xboxHostMapper.casUnlock(merchantId, xboxHostId, agentId, taskId);
        if (updated > 0) {
            log.info("CAS 解锁 Xbox 成功 - id={}, agentId={}, taskId={}", xboxHostId, agentId, taskId);
            return true;
        }
        log.warn("CAS 解锁 Xbox 失败（非持有者或已释放）- id={}, agentId={}, taskId={}",
                xboxHostId, agentId, taskId);
        return false;
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

        xboxHostMapper.physicalDeleteById(id);
        log.info("物理删除Xbox主机 - ID: {}", id);
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

    @Override
    public List<XboxHost> findByBoundStreamingAccountId(String streamingAccountId) {
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountHostBinding::getStreamingAccountId, streamingAccountId)
                .eq(StreamingAccountHostBinding::getStatus, HostBindingStatus.ACTIVE.getCode());
        List<XboxHost> hosts = new ArrayList<>();
        for (StreamingAccountHostBinding binding : hostBindingMapper.selectList(wrapper)) {
            XboxHost host = xboxHostMapper.selectById(binding.getXboxHostId());
            if (host != null) {
                hosts.add(host);
            }
        }
        return hosts;
    }

    @Override
    public XboxHost findByMerchantIdAndIpAddress(String merchantId, String ipAddress) {
        if (!StringUtils.isNotBlank(merchantId) || ipAddress == null || ipAddress.isEmpty()) {
            return null;
        }
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(XboxHost::getMerchantId, merchantId);
        wrapper.eq(XboxHost::getIpAddress, ipAddress);
        return xboxHostMapper.selectOne(wrapper);
    }

    @Override
    @Deprecated
    public XboxHost findByIpAddress(String ipAddress) {
        if (ipAddress == null || ipAddress.isEmpty()) {
            return null;
        }
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(XboxHost::getIpAddress, ipAddress);
        return xboxHostMapper.selectOne(wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public XboxHost createOrUpdate(String merchantId, String xboxId, String name, String ipAddress,
                                   Integer port, String liveId, String consoleType,
                                   String firmwareVersion, String macAddress, String platform) {
        merchantService.validateMerchantActive(merchantId);
        String normalizedPlatform = PlatformTypeUtil.requireValid(platform);
        String canonicalXboxId = XboxIdUtil.normalizeCanonical(xboxId);
        if (!StringUtils.isNotBlank(canonicalXboxId)) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "xboxId 不能为空");
        }

        XboxHost host = resolveExistingHost(
                merchantId,
                canonicalXboxId,
                ipAddress,
                liveId,
                macAddress,
                normalizedPlatform,
                true);

        if (host != null) {
            host.setPlatform(normalizedPlatform);
            mergeAlternateIdentity(host, canonicalXboxId, liveId, macAddress);
            updateHostInfo(host, name, ipAddress, port, liveId, consoleType, firmwareVersion, macAddress);
            xboxHostMapper.updateById(host);
            log.info("更新已发现的主机 - ID: {}, XboxID: {}, platform={}",
                    host.getId(), host.getXboxId(), normalizedPlatform);
            return host;
        }

        host = new XboxHost();
        host.setMerchantId(merchantId);
        host.setXboxId(canonicalXboxId);
        host.setPlatform(normalizedPlatform);
        if (StringUtils.isNotBlank(name)) {
            host.setName(name.trim());
        }
        host.setIpAddress(ipAddress);
        host.setPort(port);
        host.setLiveId(liveId);
        host.setConsoleType(consoleType);
        host.setFirmwareVersion(firmwareVersion);
        host.setMacAddress(macAddress);
        host.setStatus("idle");
        host.setLastSeenTime(LocalDateTime.now());

        xboxHostMapper.insert(host);
        log.info("创建新发现的Xbox主机 - ID: {}, XboxID: {}", host.getId(), canonicalXboxId);
        return host;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public XboxHost mergeDuplicateHost(String canonicalHostId, String duplicateHostId) {
        if (!StringUtils.isNotBlank(canonicalHostId) || !StringUtils.isNotBlank(duplicateHostId)) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID);
        }
        if (canonicalHostId.equals(duplicateHostId)) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "不能合并同一主机");
        }

        XboxHost canonical = xboxHostMapper.selectById(canonicalHostId);
        XboxHost duplicate = xboxHostMapper.selectById(duplicateHostId);
        if (canonical == null || duplicate == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }
        if (!canonical.getMerchantId().equals(duplicate.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        mergeHostFields(canonical, duplicate);
        migrateHostReferences(canonical.getId(), duplicate.getId());
        xboxHostMapper.updateById(canonical);
        xboxHostMapper.physicalDeleteById(duplicate.getId());
        log.info("合并重复主机 - canonical={}, duplicate={}, xboxId={}",
                canonical.getId(), duplicate.getId(), canonical.getXboxId());
        return canonical;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public List<Map<String, Object>> dedupeForMerchant(String merchantId) {
        merchantService.validateMerchantActive(merchantId);
        List<XboxHost> hosts = findAllByMerchantId(merchantId);
        List<Map<String, Object>> merged = new ArrayList<>();
        Set<String> consumed = new HashSet<>();

        for (int i = 0; i < hosts.size(); i++) {
            XboxHost left = hosts.get(i);
            if (consumed.contains(left.getId())) {
                continue;
            }
            for (int j = i + 1; j < hosts.size(); j++) {
                XboxHost right = hosts.get(j);
                if (consumed.contains(right.getId())) {
                    continue;
                }
                if (!shouldMergeHosts(left, right)) {
                    continue;
                }
                XboxHost canonical = pickCanonicalHost(left, right);
                XboxHost duplicate = canonical.getId().equals(left.getId()) ? right : left;
                XboxHost result = mergeDuplicateHost(canonical.getId(), duplicate.getId());
                Map<String, Object> item = new HashMap<>();
                item.put("canonicalId", result.getId());
                item.put("canonicalXboxId", result.getXboxId());
                item.put("removedId", duplicate.getId());
                item.put("removedXboxId", duplicate.getXboxId());
                merged.add(item);
                consumed.add(duplicate.getId());
                if (canonical.getId().equals(left.getId())) {
                    left = result;
                } else {
                    right = result;
                }
            }
        }
        return merged;
    }

    /**
     * 多键解析已有主机：IP &gt; xboxId 别名 &gt; liveId/MAC 别名；
     * createOrUpdate 场景下额外尝试「同平台同名且仅一条无 IP 孤儿记录」合并。
     */
    private XboxHost resolveExistingHost(
            String merchantId,
            String xboxId,
            String ipAddress,
            String liveId,
            String macAddress,
            String platform,
            boolean allowOrphanNameMatch) {
        if (!StringUtils.isNotBlank(merchantId)) {
            return null;
        }

        if (StringUtils.isNotBlank(ipAddress)) {
            XboxHost byIp = findByMerchantIdAndIpAddress(merchantId, ipAddress);
            if (byIp != null) {
                return byIp;
            }
        }

        Set<String> identityKeys = collectIdentityKeys(xboxId, liveId, macAddress);
        if (!identityKeys.isEmpty()) {
            LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(XboxHost::getMerchantId, merchantId);
            List<XboxHost> candidates = xboxHostMapper.selectList(wrapper);
            for (XboxHost candidate : candidates) {
                if (matchesIdentityKeys(candidate, identityKeys)) {
                    return candidate;
                }
            }
        }

        if (allowOrphanNameMatch
                && StringUtils.isNotBlank(ipAddress)
                && StringUtils.isNotBlank(platform)) {
            return findSingleOrphanByName(merchantId, platform, xboxId, liveId, macAddress);
        }
        return null;
    }

    private XboxHost findSingleOrphanByName(
            String merchantId,
            String platform,
            String xboxId,
            String liveId,
            String macAddress) {
        LambdaQueryWrapper<XboxHost> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(XboxHost::getMerchantId, merchantId);
        wrapper.eq(XboxHost::getPlatform, platform);
        wrapper.and(w -> w.isNull(XboxHost::getIpAddress).or().eq(XboxHost::getIpAddress, ""));
        List<XboxHost> orphans = xboxHostMapper.selectList(wrapper);
        if (orphans.size() != 1) {
            return null;
        }
        XboxHost orphan = orphans.get(0);
        if (!isComplementaryIdentity(orphan, xboxId, liveId, macAddress)) {
            return null;
        }
        return orphan;
    }

    private boolean isComplementaryIdentity(
            XboxHost orphan,
            String xboxId,
            String liveId,
            String macAddress) {
        Set<String> incomingKeys = collectIdentityKeys(xboxId, liveId, macAddress);
        if (matchesIdentityKeys(orphan, incomingKeys)) {
            return true;
        }
        boolean orphanGssv = XboxIdUtil.isGssvShortId(orphan.getXboxId());
        boolean incomingUuid = XboxIdUtil.isHardwareUuid(xboxId)
                || XboxIdUtil.isHardwareUuid(liveId)
                || XboxIdUtil.isHardwareUuid(macAddress);
        boolean orphanUuid = XboxIdUtil.isHardwareUuid(orphan.getXboxId())
                || XboxIdUtil.isHardwareUuid(orphan.getLiveId());
        boolean incomingGssv = XboxIdUtil.isGssvShortId(xboxId)
                || XboxIdUtil.isGssvShortId(liveId);
        return (orphanGssv && incomingUuid) || (orphanUuid && incomingGssv);
    }

    private Set<String> collectIdentityKeys(String xboxId, String liveId, String macAddress) {
        Set<String> keys = new LinkedHashSet<>();
        if (StringUtils.isNotBlank(xboxId)) {
            keys.addAll(XboxIdUtil.expandAliasKeys(xboxId));
        }
        if (StringUtils.isNotBlank(liveId)) {
            keys.addAll(XboxIdUtil.expandAliasKeys(liveId));
        }
        if (StringUtils.isNotBlank(macAddress)) {
            keys.addAll(XboxIdUtil.expandAliasKeys(macAddress));
        }
        return keys;
    }

    private boolean matchesIdentityKeys(XboxHost host, Set<String> identityKeys) {
        for (String field : new String[] {host.getXboxId(), host.getLiveId(), host.getMacAddress()}) {
            if (!StringUtils.isNotBlank(field)) {
                continue;
            }
            for (String alias : XboxIdUtil.expandAliasKeys(field)) {
                if (identityKeys.contains(alias)) {
                    return true;
                }
            }
        }
        return false;
    }

    private void mergeAlternateIdentity(XboxHost host, String canonicalXboxId, String liveId, String macAddress) {
        if (XboxIdUtil.isGssvShortId(host.getXboxId()) && XboxIdUtil.isHardwareUuid(canonicalXboxId)) {
            if (!StringUtils.isNotBlank(host.getLiveId())) {
                host.setLiveId(canonicalXboxId);
            }
        } else if (XboxIdUtil.isHardwareUuid(host.getXboxId()) && XboxIdUtil.isGssvShortId(canonicalXboxId)) {
            if (!StringUtils.isNotBlank(host.getLiveId())) {
                host.setLiveId(host.getXboxId());
            }
            host.setXboxId(XboxIdUtil.normalizeCanonical(canonicalXboxId));
        }
        if (XboxIdUtil.isHardwareUuid(liveId) && !XboxIdUtil.areAliases(host.getLiveId(), liveId)) {
            host.setLiveId(liveId);
        }
        if (StringUtils.isNotBlank(macAddress) && !StringUtils.isNotBlank(host.getMacAddress())) {
            host.setMacAddress(macAddress);
        }
    }

    private boolean shouldMergeHosts(XboxHost left, XboxHost right) {
        if (!Objects.equals(left.getMerchantId(), right.getMerchantId())) {
            return false;
        }
        if (!Objects.equals(left.getPlatform(), right.getPlatform())) {
            return false;
        }
        if (StringUtils.isNotBlank(left.getIpAddress())
                && StringUtils.isNotBlank(right.getIpAddress())
                && left.getIpAddress().equals(right.getIpAddress())) {
            return true;
        }
        Set<String> leftKeys = collectIdentityKeys(left.getXboxId(), left.getLiveId(), left.getMacAddress());
        if (matchesIdentityKeys(right, leftKeys)) {
            return true;
        }
        boolean leftHasIp = StringUtils.isNotBlank(left.getIpAddress());
        boolean rightHasIp = StringUtils.isNotBlank(right.getIpAddress());
        if (leftHasIp != rightHasIp) {
            return isComplementaryIdentity(leftHasIp ? right : left,
                    leftHasIp ? left.getXboxId() : right.getXboxId(),
                    leftHasIp ? left.getLiveId() : right.getLiveId(),
                    leftHasIp ? left.getMacAddress() : right.getMacAddress());
        }
        return false;
    }

    private XboxHost pickCanonicalHost(XboxHost left, XboxHost right) {
        return canonicalScore(left) >= canonicalScore(right) ? left : right;
    }

    private int canonicalScore(XboxHost host) {
        int score = 0;
        if (StringUtils.isNotBlank(host.getIpAddress())) {
            score += 100;
        }
        if (XboxIdUtil.isGssvShortId(host.getXboxId())) {
            score += 50;
        }
        if (Boolean.TRUE.equals(host.getLocked())) {
            score += 20;
        }
        LambdaQueryWrapper<StreamingAccountHostBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(StreamingAccountHostBinding::getXboxHostId, host.getId())
                .eq(StreamingAccountHostBinding::getStatus, HostBindingStatus.ACTIVE.getCode());
        score += hostBindingMapper.selectCount(wrapper).intValue() * 10;
        return score;
    }

    private void mergeHostFields(XboxHost canonical, XboxHost duplicate) {
        if (!StringUtils.isNotBlank(canonical.getIpAddress()) && StringUtils.isNotBlank(duplicate.getIpAddress())) {
            canonical.setIpAddress(duplicate.getIpAddress());
        }
        if (canonical.getPort() == null && duplicate.getPort() != null) {
            canonical.setPort(duplicate.getPort());
        }
        if (!StringUtils.isNotBlank(canonical.getName()) && StringUtils.isNotBlank(duplicate.getName())) {
            canonical.setName(duplicate.getName());
        }
        if (!StringUtils.isNotBlank(canonical.getLiveId())) {
            if (StringUtils.isNotBlank(duplicate.getLiveId())) {
                canonical.setLiveId(duplicate.getLiveId());
            } else if (XboxIdUtil.isHardwareUuid(duplicate.getXboxId())
                    && !XboxIdUtil.areAliases(canonical.getXboxId(), duplicate.getXboxId())) {
                canonical.setLiveId(duplicate.getXboxId());
            }
        } else if (XboxIdUtil.isHardwareUuid(duplicate.getXboxId())
                && !XboxIdUtil.areAliases(canonical.getLiveId(), duplicate.getXboxId())) {
            canonical.setLiveId(duplicate.getXboxId());
        }
        if (!StringUtils.isNotBlank(canonical.getMacAddress()) && StringUtils.isNotBlank(duplicate.getMacAddress())) {
            canonical.setMacAddress(duplicate.getMacAddress());
        }
        if (!StringUtils.isNotBlank(canonical.getConsoleType()) && StringUtils.isNotBlank(duplicate.getConsoleType())) {
            canonical.setConsoleType(duplicate.getConsoleType());
        }
        if (!StringUtils.isNotBlank(canonical.getFirmwareVersion())
                && StringUtils.isNotBlank(duplicate.getFirmwareVersion())) {
            canonical.setFirmwareVersion(duplicate.getFirmwareVersion());
        }
        if (!StringUtils.isNotBlank(canonical.getBoundStreamingAccountId())
                && StringUtils.isNotBlank(duplicate.getBoundStreamingAccountId())) {
            canonical.setBoundStreamingAccountId(duplicate.getBoundStreamingAccountId());
            canonical.setBoundGamertag(duplicate.getBoundGamertag());
        }
        if (XboxIdUtil.isGssvShortId(duplicate.getXboxId())
                && XboxIdUtil.isHardwareUuid(canonical.getXboxId())) {
            canonical.setLiveId(canonical.getXboxId());
            canonical.setXboxId(XboxIdUtil.normalizeCanonical(duplicate.getXboxId()));
        }
        canonical.setLastSeenTime(LocalDateTime.now());
    }

    private void migrateHostReferences(String canonicalHostId, String duplicateHostId) {
        LambdaQueryWrapper<StreamingAccountHostBinding> bindingWrapper = new LambdaQueryWrapper<>();
        bindingWrapper.eq(StreamingAccountHostBinding::getXboxHostId, duplicateHostId);
        for (StreamingAccountHostBinding binding : hostBindingMapper.selectList(bindingWrapper)) {
            LambdaQueryWrapper<StreamingAccountHostBinding> existsWrapper = new LambdaQueryWrapper<>();
            existsWrapper.eq(StreamingAccountHostBinding::getStreamingAccountId, binding.getStreamingAccountId())
                    .eq(StreamingAccountHostBinding::getXboxHostId, canonicalHostId);
            if (hostBindingMapper.selectCount(existsWrapper) > 0) {
                hostBindingMapper.deleteById(binding.getId());
            } else {
                binding.setXboxHostId(canonicalHostId);
                hostBindingMapper.updateById(binding);
            }
        }

        UpdateWrapper<Task> taskUpdate = new UpdateWrapper<>();
        taskUpdate.eq("xbox_host_id", duplicateHostId).set("xbox_host_id", canonicalHostId);
        taskMapper.update(null, taskUpdate);

        UpdateWrapper<StreamingSession> sessionUpdate = new UpdateWrapper<>();
        sessionUpdate.eq("xbox_host_id", duplicateHostId).set("xbox_host_id", canonicalHostId);
        streamingSessionMapper.update(null, sessionUpdate);

        UpdateWrapper<StreamingAccountLoginRecord> loginUpdate = new UpdateWrapper<>();
        loginUpdate.eq("xbox_host_id", duplicateHostId).set("xbox_host_id", canonicalHostId);
        loginRecordMapper.update(null, loginUpdate);
    }

    private void updateHostInfo(XboxHost host, String name, String ipAddress, Integer port,
                                String liveId, String consoleType, String firmwareVersion, String macAddress) {
        if (StringUtils.isNotBlank(name)) {
            host.setName(name.trim());
        }
        if (ipAddress != null && !ipAddress.isEmpty()) {
            host.setIpAddress(ipAddress);
        }
        if (port != null) {
            host.setPort(port);
        }
        if (StringUtils.isNotBlank(liveId)) {
            host.setLiveId(liveId);
        }
        if (StringUtils.isNotBlank(consoleType)) {
            host.setConsoleType(consoleType);
        }
        if (StringUtils.isNotBlank(firmwareVersion)) {
            host.setFirmwareVersion(firmwareVersion);
        }
        if (StringUtils.isNotBlank(macAddress)) {
            host.setMacAddress(macAddress);
        }
        host.setStatus("idle");
        host.setLastSeenTime(LocalDateTime.now());
    }

    @Override
    public String getAndInvalidateCredential(String token) {
        log.info("凭证兑换 - Token: {}", token != null ? token.substring(0, Math.min(10, token.length())) + "..." : "null");
        return credentialTokenService.getAndInvalidate(token);
    }

}