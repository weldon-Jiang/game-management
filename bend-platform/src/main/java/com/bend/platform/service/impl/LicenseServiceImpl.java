package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.LicenseCreateRequest;
import com.bend.platform.dto.LicenseIssueResponse;
import com.bend.platform.dto.LicenseVerifyRequest;
import com.bend.platform.dto.LicenseVerifyResponse;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantLicense;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.entity.MerchantPermission;
import com.bend.platform.repository.MerchantLicenseMapper;
import com.bend.platform.repository.MerchantPermissionMapper;
import com.bend.platform.service.LicenseService;
import com.bend.platform.service.MerchantService;
import com.bend.platform.util.LicenseSignUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * License 服务实现(总控侧)
 *
 * <p>签发: 生成 licenseKey + licenseSecret,secret 哈希存储,明文仅返回一次。
 * 校验: 分控上报 licenseKey + secret 明文,校验通过返回带签名结果。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LicenseServiceImpl implements LicenseService {

    private final MerchantLicenseMapper licenseMapper;
    private final MerchantPermissionMapper permissionMapper;
    private final MerchantService merchantService;
    private final LicenseSignUtil signUtil;
    private final ObjectMapper objectMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LicenseIssueResponse issueLicense(LicenseCreateRequest request) {
        // 校验商户存在
        Merchant merchant = merchantService.findById(request.getMerchantId());
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        String licenseKey = signUtil.generateLicenseKey();
        String licenseSecret = signUtil.generateLicenseSecret();

        MerchantLicense license = new MerchantLicense();
        license.setMerchantId(request.getMerchantId());
        license.setLicenseKey(licenseKey);
        license.setLicenseSecret(signUtil.hashSecret(licenseSecret));
        // License 不再承载 expireAt/maxAgents/maxTasks/features
        // 这些字段已迁移到 merchant_permission 表
        license.setStatus(request.getMachineFingerprint() != null ? "active" : "pending");
        license.setOfflineGraceHours(request.getOfflineGraceHours() != null ? request.getOfflineGraceHours() : 24);
        if (request.getMachineFingerprint() != null) {
            license.setBoundMachineFingerprint(request.getMachineFingerprint());
            license.setActivatedAt(LocalDateTime.now());
        }
        licenseMapper.insert(license);

        log.info("签发License成功 - ID: {}, 商户: {}, 状态: {}", license.getId(), request.getMerchantId(), license.getStatus());

        LicenseIssueResponse resp = new LicenseIssueResponse();
        resp.setId(license.getId());
        resp.setMerchantId(license.getMerchantId());
        resp.setMerchantName(merchant.getName());
        resp.setLicenseKey(licenseKey);
        resp.setLicenseSecret(licenseSecret);
        resp.setStatus(license.getStatus());
        resp.setExpireAt(null);
        resp.setMaxAgents(null);
        resp.setMaxTasks(null);
        resp.setFeatures(null);
        resp.setOfflineGraceHours(license.getOfflineGraceHours());
        return resp;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LicenseVerifyResponse verify(LicenseVerifyRequest request, String clientIp) {
        MerchantLicense license = licenseMapper.selectByLicenseKey(request.getLicenseKey());
        if (license == null) {
            return buildInvalid(null, null, "授权不存在", "LICENSE_NOT_FOUND");
        }

        // 校验 secret 明文
        if (!signUtil.verifySecret(request.getLicenseSecret(), license.getLicenseSecret())) {
            log.warn("License校验失败-密钥不匹配 licenseKey={}", request.getLicenseKey());
            return buildInvalid(license, null, "授权密钥不匹配", "SECRET_MISMATCH");
        }

        // 状态校验: License 本身不判断到期，只判断是否吊销
        if ("revoked".equals(license.getStatus())) {
            return buildInvalid(license, null, "授权已吊销", "REVOKED");
        }

        // 使用权限(Permission)校验: 到期/停用
        MerchantPermission permission = permissionMapper.selectByMerchantId(license.getMerchantId());
        if (permission == null) {
            return buildInvalid(license, null, "商户未配置使用权限", "NO_PERMISSION");
        }
        if ("suspended".equals(permission.getStatus())) {
            return buildInvalid(license, permission, "商户使用权限已停用", "SUSPENDED");
        }
        if ("expired".equals(permission.getStatus())) {
            return buildInvalid(license, permission, "商户使用权限已到期", "EXPIRED");
        }
        if (permission.getExpireAt() != null && LocalDateTime.now().isAfter(permission.getExpireAt())) {
            // 自动标记 permission 为 expired
            permission.setStatus("expired");
            permissionMapper.updateById(permission);
            return buildInvalid(license, permission, "商户使用权限已到期", "EXPIRED");
        }
        // 确保 permission 为 active（之前可能是 expired 但被续期了）
        if (!"active".equals(permission.getStatus())) {
            permission.setStatus("active");
            permissionMapper.updateById(permission);
        }

        // 机器指纹绑定(首次激活)/一致性校验
        if (request.getMachineFingerprint() != null && !request.getMachineFingerprint().isEmpty()) {
            if (license.getBoundMachineFingerprint() == null) {
                license.setBoundMachineFingerprint(request.getMachineFingerprint());
                license.setActivatedAt(LocalDateTime.now());
                log.info("License首次激活绑定机器 licenseKey={} fingerprint={}", request.getLicenseKey(), request.getMachineFingerprint());
            } else if (!license.getBoundMachineFingerprint().equals(request.getMachineFingerprint())) {
                log.warn("License机器指纹不匹配 licenseKey={} bound={} current={}", request.getLicenseKey(), license.getBoundMachineFingerprint(), request.getMachineFingerprint());
                return buildInvalid(license, permission, "授权与当前机器不匹配", "MACHINE_MISMATCH");
            }
        }

        // 更新校验记录
        license.setStatus("active");
        license.setLastVerifiedAt(LocalDateTime.now());
        license.setLastVerifyIp(clientIp);
        licenseMapper.updateById(license);

        // 构造有效响应并签名（使用 Permission 的能力字段）
        Merchant merchant = merchantService.findById(license.getMerchantId());
        LicenseVerifyResponse resp = new LicenseVerifyResponse();
        resp.setValid(true);
        resp.setMerchantId(license.getMerchantId());
        resp.setMerchantName(merchant != null ? merchant.getName() : null);
        resp.setStatus("active");
        resp.setExpireAt(permission.getExpireAt());
        resp.setMaxAgents(permission.getMaxAgents());
        resp.setMaxTasks(permission.getMaxTasks());
        resp.setFeatures(permission.getFeatures());
        resp.setOfflineGraceHours(permission.getOfflineGraceHours() != null ? permission.getOfflineGraceHours() : 24);
        resp.setVerifiedAt(LocalDateTime.now());
        resp.setInvalidReason(null);
        signResponse(resp);
        return resp;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void revoke(String licenseId, String reason) {
        MerchantLicense license = licenseMapper.selectById(licenseId);
        if (license == null) {
            throw new BusinessException(ResultCode.License.NOT_FOUND);
        }
        license.setStatus("revoked");
        license.setRevokedAt(LocalDateTime.now());
        license.setRevokeReason(reason);
        int rows = licenseMapper.updateById(license);
        if (rows <= 0) {
            throw new BusinessException(ResultCode.License.REVOKE_FAILED);
        }
        log.info("吊销License - ID: {}, 原因: {}", licenseId, reason);
    }

    // renew() 已迁移到 PermissionService（License 不负责到期管理）

    @Override
    public List<MerchantLicense> listByMerchant(String merchantId) {
        LambdaQueryWrapper<MerchantLicense> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantLicense::getMerchantId, merchantId)
                .orderByDesc(MerchantLicense::getCreatedTime);
        return licenseMapper.selectList(wrapper);
    }

    @Override
    public IPage<MerchantLicense> page(int pageNum, int pageSize, String merchantId, String status) {
        LambdaQueryWrapper<MerchantLicense> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null && !merchantId.isEmpty()) {
            wrapper.eq(MerchantLicense::getMerchantId, merchantId);
        }
        if (status != null && !status.isEmpty()) {
            wrapper.eq(MerchantLicense::getStatus, status);
        }
        wrapper.orderByDesc(MerchantLicense::getCreatedTime);
        return licenseMapper.selectPage(new Page<>(pageNum, pageSize), wrapper);
    }

    @Override
    public MerchantLicense findById(String id) {
        return licenseMapper.selectById(id);
    }

    // ---------------- 内部方法 ----------------

    /** 构造无效响应 */
    private LicenseVerifyResponse buildInvalid(MerchantLicense license, MerchantPermission permission,
                                                String reason, String code) {
        LicenseVerifyResponse resp = new LicenseVerifyResponse();
        resp.setValid(false);
        resp.setInvalidReason(code + ":" + reason);
        resp.setVerifiedAt(LocalDateTime.now());
        if (license != null) {
            resp.setMerchantId(license.getMerchantId());
            resp.setStatus(license.getStatus());
            resp.setOfflineGraceHours(license.getOfflineGraceHours());
        }
        if (permission != null) {
            resp.setExpireAt(permission.getExpireAt());
            resp.setMaxAgents(permission.getMaxAgents());
            resp.setMaxTasks(permission.getMaxTasks());
            resp.setFeatures(permission.getFeatures());
            if (permission.getOfflineGraceHours() != null) {
                resp.setOfflineGraceHours(permission.getOfflineGraceHours());
            }
        }
        signResponse(resp);
        return resp;
    }

    /**
     * 对响应签名: 把除 signature 外字段按固定顺序序列化为 JSON,做 HMAC-SHA256。
     */
    private void signResponse(LicenseVerifyResponse resp) {
        try {
            ObjectMapper sorted = objectMapper.copy()
                    .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
            Map<String, Object> payloadMap = new LinkedHashMap<>();
            payloadMap.put("valid", resp.getValid());
            payloadMap.put("merchantId", resp.getMerchantId());
            payloadMap.put("merchantName", resp.getMerchantName());
            payloadMap.put("status", resp.getStatus());
            payloadMap.put("expireAt", resp.getExpireAt() != null ? resp.getExpireAt().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME) : null);
            payloadMap.put("maxAgents", resp.getMaxAgents());
            payloadMap.put("maxTasks", resp.getMaxTasks());
            payloadMap.put("features", resp.getFeatures());
            payloadMap.put("offlineGraceHours", resp.getOfflineGraceHours());
            payloadMap.put("verifiedAt", resp.getVerifiedAt() != null ? resp.getVerifiedAt().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME) : null);
            payloadMap.put("invalidReason", resp.getInvalidReason());
            String payload = sorted.writeValueAsString(payloadMap);
            resp.setSignature(signUtil.sign(payload));
        } catch (Exception e) {
            log.error("License响应签名失败", e);
            throw new BusinessException(ResultCode.License.UPDATE_FAILED);
        }
    }

    private String formatTime(LocalDateTime time) {
        return time != null ? time.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")) : null;
    }
}
