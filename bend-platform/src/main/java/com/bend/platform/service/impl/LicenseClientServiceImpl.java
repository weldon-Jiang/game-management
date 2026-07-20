package com.bend.platform.service.impl;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.LicenseVerifyRequest;
import com.bend.platform.dto.LicenseVerifyResponse;
import com.bend.platform.entity.LicenseVerifyCache;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.LicenseVerifyCacheMapper;
import com.bend.platform.service.LicenseClientService;
import com.bend.platform.util.LicenseSignUtil;
import com.bend.platform.util.MachineFingerprintUtil;
import com.bend.platform.config.LicenseClientCondition;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Conditional;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 分控侧 License 客户端实现
 *
 * <p>仅在 license.mode=tenant 时由 {@link com.bend.platform.config.LicenseClientCondition} 装配。
 * <p>licenseKey/licenseSecret 从环境变量 LICENSE_KEY/LICENSE_SECRET 读取(打包时内嵌)。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class LicenseClientServiceImpl implements LicenseClientService {

    @Value("${license.master-url:}")
    private String masterUrl;

    @Value("${license.verify-interval-minutes:30}")
    private int verifyIntervalMinutes;

    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;

    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

    private final LicenseVerifyCacheMapper cacheMapper;
    private final LicenseSignUtil signUtil;
    private final MachineFingerprintUtil fingerprintUtil;
    private final ObjectMapper objectMapper;

    private RestTemplate restTemplate;
    private volatile boolean lastVerifySuccess = false;
    private volatile String lastError = null;

    @PostConstruct
    public void init() {
        this.restTemplate = new RestTemplate();
        // 启动时立即校验一次
        try {
            verifyNow();
        } catch (Exception e) {
            log.warn("启动License校验异常,稍后靠定时重试: {}", e.getMessage());
        }
    }

    @Override
    public synchronized boolean verifyNow() {
        if (masterUrl == null || masterUrl.isEmpty()) {
            log.warn("分控未配置 license.master-url,跳过在线校验");
            lastVerifySuccess = false;
            lastError = "MASTER_URL_NOT_CONFIGURED";
            return isWithinOfflineGrace();
        }
        try {
            LicenseVerifyRequest req = new LicenseVerifyRequest();
            req.setLicenseKey(licenseKey);
            req.setLicenseSecret(licenseSecret);
            req.setMachineFingerprint(fingerprintUtil.getFingerprint());

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<LicenseVerifyRequest> entity = new HttpEntity<>(req, headers);

            String url = masterUrl.replaceAll("/+$", "") + "/api/licenses/verify";
            ResponseEntity<ApiResponse> resp = restTemplate.postForEntity(url, entity, ApiResponse.class);

            if (resp.getBody() == null || resp.getBody().getData() == null) {
                throw new IllegalStateException("总控返回空结果");
            }
            LicenseVerifyResponse data = objectMapper.convertValue(resp.getBody().getData(), LicenseVerifyResponse.class);

            // 验签(防伪造)
            if (!verifySignature(data)) {
                log.error("License校验返回签名无效,拒绝接受");
                lastVerifySuccess = false;
                lastError = "SIGNATURE_INVALID";
                return false;
            }

            // 写本地缓存(无论有效无效都写,无效时缓存 invalidReason)
            upsertCache(data);

            lastVerifySuccess = true;
            lastError = data.getValid() ? null : data.getInvalidReason();
            log.info("License在线校验完成 valid={} status={} expireAt={}",
                    data.getValid(), data.getStatus(), data.getExpireAt());
            return data.getValid();
        } catch (Exception e) {
            log.warn("License在线校验失败(总控不可达),转入离线宽限判断: {}", e.getMessage());
            lastVerifySuccess = false;
            lastError = "MASTER_UNREACHABLE:" + e.getMessage();
            return isWithinOfflineGrace();
        }
    }

    @Override
    public boolean isAuthorized() {
        LicenseStatus s = getStatus();
        return s.authorized();
    }

    @Override
    public LicenseStatus getStatus() {
        LicenseVerifyCache cache = getCache();
        if (cache == null) {
            return new LicenseStatus(false, "NONE", lastVerifySuccess, lastError, null, null, null);
        }
        boolean onlineValid = Boolean.TRUE.equals(cache.getValid());
        if (onlineValid) {
            // 在线有效,但也要看是否已到期
            if (cache.getExpireAt() != null && LocalDateTime.now().isAfter(cache.getExpireAt())) {
                return new LicenseStatus(false, "EXPIRED", lastVerifySuccess, "EXPIRED", cache.getExpireAt(), cache.getVerifiedAt(), null);
            }
            return new LicenseStatus(true, "ONLINE", lastVerifySuccess, null, cache.getExpireAt(), cache.getVerifiedAt(), computeOfflineDeadline(cache));
        }
        // 缓存为无效: 看离线宽限
        LocalDateTime deadline = computeOfflineDeadline(cache);
        if (deadline != null && LocalDateTime.now().isBefore(deadline)) {
            return new LicenseStatus(true, "OFFLINE_GRACE", lastVerifySuccess, lastError, cache.getExpireAt(), cache.getVerifiedAt(), deadline);
        }
        return new LicenseStatus(false, "EXPIRED_GRACE", lastVerifySuccess, lastError, cache.getExpireAt(), cache.getVerifiedAt(), deadline);
    }

    @Override
    public LicenseVerifyCache getCache() {
        if (licenseKey == null || licenseKey.isEmpty()) {
            return null;
        }
        return cacheMapper.selectByLicenseKey(licenseKey);
    }

    // ---------------- 内部 ----------------

    /**
     * 离线宽限判断: 若上次成功校验时间 + 宽限小时数 仍在当前时间之后,则仍可用。
     * 这里用 cache.verifiedAt(总控签名时间,不可伪造) 作为基准。
     */
    private boolean isWithinOfflineGrace() {
        LicenseVerifyCache cache = getCache();
        if (cache == null || !Boolean.TRUE.equals(cache.getValid())) {
            return false;
        }
        LocalDateTime deadline = computeOfflineDeadline(cache);
        return deadline != null && LocalDateTime.now().isBefore(deadline);
    }

    private LocalDateTime computeOfflineDeadline(LicenseVerifyCache cache) {
        if (cache == null || cache.getVerifiedAt() == null) {
            return null;
        }
        // 宽限期从总控签名时间起算;offlineGraceHours 在线校验时未单独返回,用默认24h
        // 若 cache 来自在线有效响应,verifiedAt 即最近成功时间
        int graceHours = 24;
        return cache.getVerifiedAt().plusHours(graceHours);
    }

    private boolean verifySignature(LicenseVerifyResponse data) {
        try {
            ObjectMapper sorted = objectMapper.copy()
                    .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
            Map<String, Object> payloadMap = new LinkedHashMap<>();
            payloadMap.put("valid", data.getValid());
            payloadMap.put("merchantId", data.getMerchantId());
            payloadMap.put("merchantName", data.getMerchantName());
            payloadMap.put("status", data.getStatus());
            payloadMap.put("expireAt", data.getExpireAt() != null ? data.getExpireAt().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME) : null);
            payloadMap.put("maxAgents", data.getMaxAgents());
            payloadMap.put("maxTasks", data.getMaxTasks());
            payloadMap.put("features", data.getFeatures());
            payloadMap.put("offlineGraceHours", data.getOfflineGraceHours());
            payloadMap.put("verifiedAt", data.getVerifiedAt() != null ? data.getVerifiedAt().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME) : null);
            payloadMap.put("invalidReason", data.getInvalidReason());
            String payload = sorted.writeValueAsString(payloadMap);
            return signUtil.verify(payload, data.getSignature());
        } catch (Exception e) {
            log.error("验签异常", e);
            return false;
        }
    }

    private void upsertCache(LicenseVerifyResponse data) {
        LicenseVerifyCache existing = (licenseKey != null && !licenseKey.isEmpty())
                ? cacheMapper.selectByLicenseKey(licenseKey) : null;
        LicenseVerifyCache cache = existing != null ? existing : new LicenseVerifyCache();
        cache.setLicenseKey(licenseKey);
        cache.setMerchantId(data.getMerchantId());
        cache.setValid(data.getValid());
        cache.setExpireAt(data.getExpireAt());
        cache.setFeatures(data.getFeatures());
        cache.setVerifiedAt(data.getVerifiedAt());
        cache.setSignature(data.getSignature());
        cache.setRawPayload(buildRawPayload(data));
        if (existing == null) {
            cacheMapper.insert(cache);
        } else {
            cacheMapper.updateById(cache);
        }
    }

    private String buildRawPayload(LicenseVerifyResponse data) {
        try {
            return objectMapper.writeValueAsString(data);
        } catch (Exception e) {
            return null;
        }
    }
}
