package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.PermissionCreateRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantPermission;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantPermissionMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.PermissionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * 商户使用权限服务实现（总控侧）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PermissionServiceImpl implements PermissionService {

    private final MerchantPermissionMapper permissionMapper;
    private final MerchantService merchantService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public MerchantPermission createOrRenew(PermissionCreateRequest request) {
        if (request.getExpireAt() == null) {
            throw new BusinessException(ResultCode.System.BAD_REQUEST);
        }
        Merchant merchant = merchantService.findById(request.getMerchantId());
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        MerchantPermission existing = permissionMapper.selectByMerchantId(request.getMerchantId());
        if (existing != null) {
            // 续期/更新: 覆盖到期时间和配额
            existing.setExpireAt(request.getExpireAt());
            existing.setMaxAgents(request.getMaxAgents() != null ? request.getMaxAgents() : existing.getMaxAgents());
            existing.setMaxTasks(request.getMaxTasks() != null ? request.getMaxTasks() : existing.getMaxTasks());
            if (request.getFeatures() != null) {
                existing.setFeatures(request.getFeatures());
            }
            if (request.getOfflineGraceHours() != null) {
                existing.setOfflineGraceHours(request.getOfflineGraceHours());
            }
            existing.setStatus("active");
            permissionMapper.updateById(existing);
            log.info("更新商户使用权限 merchantId={} expireAt={}", request.getMerchantId(), request.getExpireAt());
            return existing;
        } else {
            // 新建
            MerchantPermission perm = new MerchantPermission();
            perm.setMerchantId(request.getMerchantId());
            perm.setStatus("active");
            perm.setExpireAt(request.getExpireAt());
            perm.setMaxAgents(request.getMaxAgents() != null ? request.getMaxAgents() : 5);
            perm.setMaxTasks(request.getMaxTasks() != null ? request.getMaxTasks() : 50);
            perm.setFeatures(request.getFeatures());
            perm.setOfflineGraceHours(request.getOfflineGraceHours() != null ? request.getOfflineGraceHours() : 24);
            permissionMapper.insert(perm);
            log.info("创建商户使用权限 merchantId={} expireAt={}", request.getMerchantId(), request.getExpireAt());
            return perm;
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void renew(String permissionId, LocalDateTime newExpireAt) {
        MerchantPermission perm = permissionMapper.selectById(permissionId);
        if (perm == null) {
            throw new BusinessException(ResultCode.License.NOT_FOUND);
        }
        perm.setExpireAt(newExpireAt);
        // 续期只恢复"已到期"状态；"已停用"需显式 resume()，避免续期意外解除停用
        if ("expired".equals(perm.getStatus())) {
            perm.setStatus("active");
        }
        permissionMapper.updateById(perm);
        log.info("续期商户使用权限 permissionId={} newExpireAt={} status={}", permissionId, newExpireAt, perm.getStatus());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void suspend(String permissionId) {
        MerchantPermission perm = permissionMapper.selectById(permissionId);
        if (perm == null) {
            throw new BusinessException(ResultCode.License.NOT_FOUND);
        }
        if (!"active".equals(perm.getStatus())) {
            throw new BusinessException(ResultCode.License.UPDATE_FAILED);
        }
        perm.setStatus("suspended");
        permissionMapper.updateById(perm);
        log.info("停用商户使用权限 permissionId={}", permissionId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void resume(String permissionId) {
        MerchantPermission perm = permissionMapper.selectById(permissionId);
        if (perm == null) {
            throw new BusinessException(ResultCode.License.NOT_FOUND);
        }
        if (!"suspended".equals(perm.getStatus())) {
            throw new BusinessException(ResultCode.License.UPDATE_FAILED);
        }
        // 恢复时检查是否已到期
        if (perm.getExpireAt() != null && LocalDateTime.now().isAfter(perm.getExpireAt())) {
            perm.setStatus("expired");
        } else {
            perm.setStatus("active");
        }
        permissionMapper.updateById(perm);
        log.info("启用商户使用权限 permissionId={} status={}", permissionId, perm.getStatus());
    }

    @Override
    public MerchantPermission findByMerchantId(String merchantId) {
        return permissionMapper.selectByMerchantId(merchantId);
    }

    @Override
    public MerchantPermission findById(String id) {
        return permissionMapper.selectById(id);
    }

    @Override
    public IPage<MerchantPermission> page(int pageNum, int pageSize, String merchantId, String status) {
        LambdaQueryWrapper<MerchantPermission> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null && !merchantId.isEmpty()) {
            wrapper.eq(MerchantPermission::getMerchantId, merchantId);
        }
        if (status != null && !status.isEmpty()) {
            wrapper.eq(MerchantPermission::getStatus, status);
        }
        wrapper.orderByDesc(MerchantPermission::getCreatedTime);
        return permissionMapper.selectPage(new Page<>(pageNum, pageSize), wrapper);
    }
}
