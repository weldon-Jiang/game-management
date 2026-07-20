package com.bend.platform.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Iterator;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 凭证令牌服务
 *
 * <p>用于自动化任务启动时的短期一次性凭据传递(5分钟过期,消费一次即失效)。
 *
 * <p>存储策略:
 * <ul>
 *   <li>Redis 可用(总控多实例): 用 Redis,跨实例共享</li>
 *   <li>Redis 不可用(分控单实例): 用进程内 {@link ConcurrentHashMap} + 懒过期清理,
 *       语义等价(getAndDelete / 5min TTL / 单次消费)。分控单实例,无需跨进程共享。</li>
 * </ul>
 *
 * <p>无论哪种存储,token 服务始终就绪 —— 这点对分控(无 Redis)启动自动化任务至关重要,
 * 上层 {@code AutomationServiceImpl} 通过 {@link #isReady()} 判断是否可启动。
 */
@Slf4j
@Service
public class CredentialTokenService {

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    private static final String TOKEN_PREFIX = "cred_token:";
    private static final long TOKEN_EXPIRE_SECONDS = 300;

    /** 本地 fallback 存储: token -> [加密值, 过期时间戳ms] */
    private final ConcurrentHashMap<String, long[]> localExpiry = new ConcurrentHashMap<>();
    /** 本地存储 token -> 加密值(独立 map 以便 getAndDelete 原子取删) */
    private final ConcurrentHashMap<String, String> localStore = new ConcurrentHashMap<>();
    /** 上次清理时间戳,避免每次写入都扫全表 */
    private final AtomicLong lastSweepAt = new AtomicLong(0);

    private boolean isRedisAvailable() {
        return redisTemplate != null;
    }

    /**
     * token 服务是否就绪(可否启动自动化任务)。
     * Redis 可用 -> 就绪;Redis 不可用 -> 本地缓存就绪(始终为 true)。
     * 替代原 isRedisEnabled() 的硬性 503 拦截,使分控无 Redis 也可启动任务。
     */
    public boolean isReady() {
        return true;
    }

    /** 兼容旧调用方,语义=服务就绪 */
    public boolean isRedisEnabled() {
        return isReady();
    }

    public String generateToken(String credentialKey, String encryptedValue) {
        if (encryptedValue == null) {
            log.warn("加密值为空，无法生成凭证令牌 - key: {}", credentialKey);
            return "NULL_VALUE";
        }
        String token = UUID.randomUUID().toString().replace("-", "");

        if (isRedisAvailable()) {
            String redisKey = TOKEN_PREFIX + token;
            redisTemplate.opsForValue().set(redisKey, encryptedValue, TOKEN_EXPIRE_SECONDS, TimeUnit.SECONDS);
        } else {
            sweepExpired();
            localStore.put(token, encryptedValue);
            localExpiry.put(token, new long[]{System.currentTimeMillis() + TOKEN_EXPIRE_SECONDS * 1000});
        }
        log.debug("生成凭证令牌 - key: {}, 存储方式: {}, expire: {}s", credentialKey,
                isRedisAvailable() ? "redis" : "local", TOKEN_EXPIRE_SECONDS);
        return token;
    }

    public String getAndInvalidate(String token) {
        if (isRedisAvailable()) {
            String redisKey = TOKEN_PREFIX + token;
            String value = redisTemplate.opsForValue().getAndDelete(redisKey);
            if (value == null) {
                log.warn("凭证令牌不存在或已过期 - token: {}", token);
            }
            return value;
        }
        // 本地: 先检查过期,再原子取删
        long[] exp = localExpiry.get(token);
        if (exp == null || System.currentTimeMillis() > exp[0]) {
            localStore.remove(token);
            localExpiry.remove(token);
            if (exp != null) {
                log.warn("凭证令牌已过期 - token: {}", token);
            } else {
                log.warn("凭证令牌不存在 - token: {}", token);
            }
            return null;
        }
        localExpiry.remove(token);
        return localStore.remove(token);
    }

    public boolean isValid(String token) {
        if (isRedisAvailable()) {
            String redisKey = TOKEN_PREFIX + token;
            return Boolean.TRUE.equals(redisTemplate.hasKey(redisKey));
        }
        long[] exp = localExpiry.get(token);
        return exp != null && System.currentTimeMillis() <= exp[0];
    }

    /** 懒清理: 每 60s 最多扫一次,移除已过期条目,避免内存泄漏 */
    private void sweepExpired() {
        long now = System.currentTimeMillis();
        long last = lastSweepAt.get();
        if (now - last < 60_000) {
            return;
        }
        if (!lastSweepAt.compareAndSet(last, now)) {
            return;
        }
        Iterator<Map.Entry<String, long[]>> it = localExpiry.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<String, long[]> e = it.next();
            if (now > e.getValue()[0]) {
                it.remove();
                localStore.remove(e.getKey());
            }
        }
    }
}
