package com.bend.platform.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class CredentialTokenService {

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    private static final String TOKEN_PREFIX = "cred_token:";
    private static final long TOKEN_EXPIRE_SECONDS = 300;

    private boolean isRedisAvailable() {
        return redisTemplate != null;
    }

    public String generateToken(String credentialKey, String encryptedValue) {
        if (!isRedisAvailable()) {
            log.warn("Redis未启用，无法生成凭证令牌 - key: {}", credentialKey);
            return "DISABLED:" + UUID.randomUUID().toString();
        }
        String token = UUID.randomUUID().toString().replace("-", "");
        String redisKey = TOKEN_PREFIX + token;

        redisTemplate.opsForValue().set(redisKey, encryptedValue, TOKEN_EXPIRE_SECONDS, TimeUnit.SECONDS);

        log.debug("生成凭证令牌 - key: {}, expire: {}s", credentialKey, TOKEN_EXPIRE_SECONDS);
        return token;
    }

    public String getAndInvalidate(String token) {
        if (!isRedisAvailable()) {
            log.warn("Redis未启用，无法获取凭证令牌 - token: {}", token);
            return null;
        }
        String redisKey = TOKEN_PREFIX + token;
        String value = redisTemplate.opsForValue().getAndDelete(redisKey);

        if (value == null) {
            log.warn("凭证令牌不存在或已过期 - token: {}", token);
        } else {
            log.debug("凭证令牌已使用并删除 - token: {}", token);
        }

        return value;
    }

    public boolean isValid(String token) {
        if (!isRedisAvailable()) {
            return false;
        }
        String redisKey = TOKEN_PREFIX + token;
        return Boolean.TRUE.equals(redisTemplate.hasKey(redisKey));
    }
}