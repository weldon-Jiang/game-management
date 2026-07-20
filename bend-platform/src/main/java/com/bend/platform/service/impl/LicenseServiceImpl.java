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
import com.bend.platform.repository.MerchantLicenseMapper;
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
        license.setStatus(request.getMachineFingerprint() != null ? "active" : "pending");
        license.setExpireAt(request.getExpireAt());
        license.setMaxAgents(request.getMaxAgents() != null ? request.getMaxAgents() : 5);
        license.setMaxTasks(request.getMaxTasks() != null ? request.getMaxTasks() : 50);
        license.setFeatures(request.getFeatures());
        license.setOfflineGraceHours(request.getOfflineGraceHours() != null ? request.getOfflineGraceHours() : 24);
        if (request.getMachineFingerprint() != null) {
            license.setBoundMachineFingerprint(request.getMachineFingerprint());
            license.setActivatedAt(LocalDateTime.now());
        }
        licenseMapper.insert(license);

        log.info("签发License成功 - ID: {}, 商户: {}, 到期: {}", license.getId(), request.getMerchantId(), request.getExpireAt());

        LicenseIssueResponse resp = new LicenseIssueResponse();
        resp.setId(license.getId());
        resp.setMerchantId(license.getMerchantId());
        resp.setMerchantName(merchant.getName());
        resp.setLicenseKey(licenseKey);
        resp.setLicenseSecret(licenseSecret);
        resp.setStatus(license.getStatus());
        resp.setExpireAt(formatTime(license.getExpireAt()));
        resp.setMaxAgents(license.getMaxAgents());
        resp.setMaxTasks(license.getMaxTasks());
        resp.setFeatures(license.getFeatures());
        resp.setOfflineGraceHours(license.getOfflineGraceHours());
        return resp;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LicenseVerifyResponse verify(LicenseVerifyRequest request, String clientIp) {
        MerchantLicense license = licenseMapper.selectByLicenseKey(request.getLicenseKey());
        if (license == null) {
            return buildInvalid(null, "授权不存在", "LICENSE_NOT_FOUND");
        }

        // 校验 secret 明文
        if (!signUtil.verifySecret(request.getLicenseSecret(), license.getLicenseSecret())) {
            log.warn("License校验失败-密钥不匹配 licenseKey={}", request.getLicenseKey());
            return buildInvalid(license, "授权密钥不匹配", "SECRET_MISMATCH");
        }

        // 状态校验
        if ("revoked".equals(license.getStatus())) {
            return buildInvalid(license, "授权已吊销", "REVOKED");
        }
        // 到期校验
        if (license.getExpireAt() != null && LocalDateTime.now().isAfter(license.getExpireAt())) {
            if (!"expired".equals(license.getStatus())) {
                license.setStatus("expired");
            }
            return buildInvalid(license, "授权已到期", "EXPIRED");
        }

        // 机器指纹绑定(首次激活)/一致性校验
        if (request.getMachineFingerprint() != null && !request.getMachineFingerprint().isEmpty()) {
            if (license.getBoundMachineFingerprint() == null) {
                license.setBoundMachineFingerprint(request.getMachineFingerprint());
                license.setActivatedAt(LocalDateTime.now());
                log.info("License首次激活绑定机器 licenseKey={} fingerprint={}", request.getLicenseKey(), request.getMachineFingerprint());
            } else if (!license.getBoundMachineFingerprint().equals(request.getMachineFingerprint())) {
                log.warn("License机器指纹不匹配 licenseKey={} bound={} current={}", request.getLicenseKey(), license.getBoundMachineFingerprint(), request.getMachineFingerprint());
                return buildInvalid(license, "授权与当前机器不匹配", "MACHINE_MISMATCH");
            }
        }

        // 更新校验记录
        license.setStatus("active");
        license.setLastVerifiedAt(LocalDateTime.now());
        license.setLastVerifyIp(clientIp);
        licenseMapper.updateById(license);

        // 构造有效响应并签名
        Merchant merchant = merchantService.findById(license.getMerchantId());
        LicenseVerifyResponse resp = new LicenseVerifyResponse();
        resp.setValid(true);
        resp.setMerchantId(license.getMerchantId());
        resp.setMerchantName(merchant != null ? merchant.getName() : null);
        resp.setStatus(license.getStatus());
        resp.setExpireAt(license.getExpireAt());
        resp.setMaxAgents(license.getMaxAgents());
        resp.setMaxTasks(license.getMaxTasks());
        resp.setFeatures(license.getFeatures());
        resp.setOfflineGraceHours(license.getOfflineGraceHours());
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

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void renew(String licenseId, LocalDateTime newExpireAt) {
        MerchantLicense license = licenseMapper.selectById(licenseId);
        if (license == null) {
            throw new BusinessException(ResultCode.License.NOT_FOUND);
        }
        license.setExpireAt(newExpireAt);
        if ("expired".equals(license.getStatus())) {
            license.setStatus("active");
        }
        licenseMapper.updateById(license);
        log.info("续期License - ID: {}, 新到期: {}", licenseId, newExpireAt);
    }

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

    /** 构造无效响应(不写 last_verified_at,避免被无效请求刷时间) */
    private LicenseVerifyResponse buildInvalid(MerchantLicense license, String reason, String code) {
        LicenseVerifyResponse resp = new LicenseVerifyResponse();
        resp.setValid(false);
        resp.setInvalidReason(code + ":" + reason);
        resp.setVerifiedAt(LocalDateTime.now());
        if (license != null) {
            resp.setMerchantId(license.getMerchantId());
            resp.setStatus(license.getStatus());
            resp.setExpireAt(license.getExpireAt());
            resp.setOfflineGraceHours(license.getOfflineGraceHours());
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
