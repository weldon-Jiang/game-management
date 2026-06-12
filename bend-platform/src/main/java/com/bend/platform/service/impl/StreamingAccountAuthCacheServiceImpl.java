package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.StreamingAccountAuthCache;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountAuthCacheMapper;
import com.bend.platform.service.StreamingAccountAuthCacheService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.util.AesUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 串流账号 xblive Token 平台缓存：AES 落库 + 乐观锁写入。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StreamingAccountAuthCacheServiceImpl implements StreamingAccountAuthCacheService {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private final StreamingAccountAuthCacheMapper authCacheMapper;
    private final StreamingAccountService streamingAccountService;
    private final AesUtil aesUtil;

    @Override
    public Map<String, Object> getAuthCache(String streamingAccountId, String merchantId) {
        requireAccountInMerchant(streamingAccountId, merchantId);

        StreamingAccountAuthCache row = authCacheMapper.selectById(streamingAccountId);
        Map<String, Object> result = new HashMap<>();
        if (row == null || !StringUtils.hasText(row.getTokenDocEncrypted())) {
            result.put("found", false);
            return result;
        }

        Map<String, Object> tokenDoc;
        try {
            String plain = aesUtil.decrypt(row.getTokenDocEncrypted());
            tokenDoc = OBJECT_MAPPER.readValue(plain, new TypeReference<>() {});
        } catch (Exception e) {
            log.error("解密串流账号 Token 缓存失败 accountId={}", streamingAccountId, e);
            throw new BusinessException(500, "Token 缓存解密失败");
        }

        result.put("found", true);
        result.put("tokenDoc", tokenDoc);
        result.put("tokenVersion", row.getTokenVersion() != null ? row.getTokenVersion() : 0);
        result.put("authState", row.getAuthState());
        result.put("lastAuthTime", row.getLastAuthTime());
        result.put("xhomeExpiresAt", row.getXhomeExpiresAt());
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> saveAuthCache(
            String streamingAccountId,
            String merchantId,
            String agentId,
            Map<String, Object> tokenDoc,
            Integer expectedTokenVersion,
            String authState,
            LocalDateTime xhomeExpiresAt) {
        if (tokenDoc == null || tokenDoc.isEmpty()) {
            throw new BusinessException(400, "tokenDoc 不能为空");
        }

        StreamingAccount account = requireAccountInMerchant(streamingAccountId, merchantId);
        String normalizedState = normalizeAuthState(authState);
        String encrypted;
        try {
            encrypted = aesUtil.encrypt(OBJECT_MAPPER.writeValueAsString(tokenDoc));
        } catch (Exception e) {
            log.error("加密串流账号 Token 缓存失败 accountId={}", streamingAccountId, e);
            throw new BusinessException(500, "Token 缓存加密失败");
        }

        LocalDateTime now = LocalDateTime.now();
        StreamingAccountAuthCache existing = authCacheMapper.selectById(streamingAccountId);
        int expected = expectedTokenVersion != null ? expectedTokenVersion : 0;

        if (existing == null) {
            if (expected > 0) {
                throw new BusinessException(409, "Token 版本冲突，请重新读取后保存");
            }
            StreamingAccountAuthCache insert = new StreamingAccountAuthCache();
            insert.setStreamingAccountId(streamingAccountId);
            insert.setMerchantId(account.getMerchantId());
            insert.setTokenDocEncrypted(encrypted);
            insert.setTokenVersion(1);
            insert.setAuthState(normalizedState);
            insert.setLastAuthAgentId(agentId);
            insert.setLastAuthTime(now);
            insert.setXhomeExpiresAt(xhomeExpiresAt);
            authCacheMapper.insert(insert);
            log.info("创建串流账号 Token 缓存 accountId={} version=1 agent={}", streamingAccountId, agentId);
            return Map.of("saved", true, "tokenVersion", 1);
        }

        int currentVersion = existing.getTokenVersion() != null ? existing.getTokenVersion() : 0;
        if (expected != currentVersion) {
            throw new BusinessException(409, "Token 版本冲突，请重新读取后保存");
        }

        int nextVersion = currentVersion + 1;
        LambdaUpdateWrapper<StreamingAccountAuthCache> update = new LambdaUpdateWrapper<>();
        update.eq(StreamingAccountAuthCache::getStreamingAccountId, streamingAccountId)
                .eq(StreamingAccountAuthCache::getTokenVersion, currentVersion)
                .set(StreamingAccountAuthCache::getTokenDocEncrypted, encrypted)
                .set(StreamingAccountAuthCache::getTokenVersion, nextVersion)
                .set(StreamingAccountAuthCache::getAuthState, normalizedState)
                .set(StreamingAccountAuthCache::getLastAuthAgentId, agentId)
                .set(StreamingAccountAuthCache::getLastAuthTime, now)
                .set(StreamingAccountAuthCache::getXhomeExpiresAt, xhomeExpiresAt);

        int rows = authCacheMapper.update(null, update);
        if (rows == 0) {
            throw new BusinessException(409, "Token 版本冲突，请重新读取后保存");
        }

        log.info(
                "更新串流账号 Token 缓存 accountId={} version={} agent={} state={}",
                streamingAccountId,
                nextVersion,
                agentId,
                normalizedState);
        return Map.of("saved", true, "tokenVersion", nextVersion);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteAuthCache(String streamingAccountId, String merchantId) {
        requireAccountInMerchant(streamingAccountId, merchantId);
        authCacheMapper.deleteById(streamingAccountId);
        log.info("已清除串流账号 Token 缓存 accountId={}", streamingAccountId);
    }

    private StreamingAccount requireAccountInMerchant(String streamingAccountId, String merchantId) {
        if (!StringUtils.hasText(streamingAccountId)) {
            throw new BusinessException(400, "streamingAccountId 不能为空");
        }
        StreamingAccount account = streamingAccountService.findById(streamingAccountId);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }
        if (StringUtils.hasText(merchantId) && !merchantId.equals(account.getMerchantId())) {
            throw new BusinessException(403, "串流账号不属于当前商户");
        }
        return account;
    }

    private static String normalizeAuthState(String authState) {
        if (!StringUtils.hasText(authState)) {
            return "valid";
        }
        String normalized = authState.trim().toLowerCase();
        return switch (normalized) {
            case "valid", "refresh_needed", "expired" -> normalized;
            default -> "valid";
        };
    }
}
