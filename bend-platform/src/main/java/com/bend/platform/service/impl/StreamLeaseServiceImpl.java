package com.bend.platform.service.impl;

import com.bend.platform.service.StreamLeaseService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Xbox 串流租约：Redis 为主，Redis 不可用时降级 JVM 内 Map（不跨 Agent）。
 */
@Service
public class StreamLeaseServiceImpl implements StreamLeaseService {

    private static final Logger log = LoggerFactory.getLogger(StreamLeaseServiceImpl.class);
    private static final String KEY_PREFIX = "stream:lease:";

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    /** serverId -> agentId|taskId|expiresAtMs */
    private final Map<String, String> localLeases = new ConcurrentHashMap<>();

    @Override
    public boolean tryAcquire(String serverId, String agentId, String taskId, int ttlSeconds) {
        if (serverId == null || serverId.isBlank() || agentId == null || taskId == null) {
            return false;
        }
        String value = encode(agentId, taskId);
        int ttl = Math.max(30, ttlSeconds);

        if (useRedis()) {
            try {
                String key = KEY_PREFIX + serverId;
                String existing = redisTemplate.opsForValue().get(key);
                if (value.equals(existing)) {
                    redisTemplate.expire(key, Duration.ofSeconds(ttl));
                    return true;
                }
                Boolean ok = redisTemplate.opsForValue().setIfAbsent(key, value, Duration.ofSeconds(ttl));
                if (Boolean.TRUE.equals(ok)) {
                    log.info("Stream lease acquired (Redis) serverId={} agentId={} taskId={} ttl={}s",
                            serverId, agentId, taskId, ttl);
                    return true;
                }
                log.debug("Stream lease denied (Redis) serverId={} holder={}", serverId, existing);
                return false;
            } catch (Exception e) {
                log.warn("Redis stream lease acquire failed, fallback local: {}", e.getMessage());
            }
        }

        long expiresAt = System.currentTimeMillis() + ttl * 1000L;
        String localValue = value + "|" + expiresAt;
        String existing = localLeases.get(serverId);
        if (existing != null) {
            if (isExpired(existing)) {
                localLeases.remove(serverId);
            } else if (existing.startsWith(value + "|")) {
                localLeases.put(serverId, localValue);
                return true;
            } else {
                return false;
            }
        }
        String prior = localLeases.putIfAbsent(serverId, localValue);
        if (prior == null || prior.startsWith(value + "|")) {
            localLeases.put(serverId, localValue);
            log.info("Stream lease acquired (local) serverId={} agentId={} taskId={}", serverId, agentId, taskId);
            return true;
        }
        if (isExpired(prior)) {
            localLeases.put(serverId, localValue);
            return true;
        }
        return false;
    }

    @Override
    public boolean release(String serverId, String agentId, String taskId) {
        if (serverId == null || serverId.isBlank()) {
            return false;
        }
        String value = encode(agentId, taskId);

        if (useRedis()) {
            try {
                String key = KEY_PREFIX + serverId;
                String existing = redisTemplate.opsForValue().get(key);
                if (value.equals(existing)) {
                    redisTemplate.delete(key);
                    log.info("Stream lease released (Redis) serverId={} taskId={}", serverId, taskId);
                    return true;
                }
                return false;
            } catch (Exception e) {
                log.warn("Redis stream lease release failed, fallback local: {}", e.getMessage());
            }
        }

        String existing = localLeases.get(serverId);
        if (existing != null && existing.startsWith(value + "|")) {
            localLeases.remove(serverId);
            return true;
        }
        return false;
    }

    @Override
    public Optional<Map<String, Object>> getLease(String serverId) {
        if (serverId == null || serverId.isBlank()) {
            return Optional.empty();
        }

        if (useRedis()) {
            try {
                String key = KEY_PREFIX + serverId;
                String raw = redisTemplate.opsForValue().get(key);
                if (raw == null) {
                    return Optional.empty();
                }
                Long ttl = redisTemplate.getExpire(key);
                return Optional.of(buildLeaseMap(raw, ttl != null ? ttl : 0L));
            } catch (Exception e) {
                log.debug("Redis getLease failed: {}", e.getMessage());
            }
        }

        String existing = localLeases.get(serverId);
        if (existing == null || isExpired(existing)) {
            if (existing != null) {
                localLeases.remove(serverId);
            }
            return Optional.empty();
        }
        int sep = existing.lastIndexOf('|');
        String holder = sep > 0 ? existing.substring(0, sep) : existing;
        long expiresAt = sep > 0 ? Long.parseLong(existing.substring(sep + 1)) : 0L;
        long ttlSec = Math.max(0, (expiresAt - System.currentTimeMillis()) / 1000);
        return Optional.of(buildLeaseMap(holder, ttlSec));
    }

    @Override
    public boolean isClusterSafe() {
        return useRedis();
    }

    private Map<String, Object> buildLeaseMap(String holderValue, long ttlSeconds) {
        Map<String, Object> map = new HashMap<>();
        String[] parts = holderValue.split("\\|", 2);
        map.put("leaseActive", true);
        map.put("leaseHolderAgentId", parts.length > 0 ? parts[0] : null);
        map.put("leaseHolderTaskId", parts.length > 1 ? parts[1] : null);
        map.put("leaseTtlSec", ttlSeconds);
        map.put("leaseExpiresAt", System.currentTimeMillis() + ttlSeconds * 1000L);
        return map;
    }

    private static String encode(String agentId, String taskId) {
        return agentId + "|" + taskId;
    }

    private static boolean isExpired(String localValue) {
        int sep = localValue.lastIndexOf('|');
        if (sep <= 0) {
            return true;
        }
        try {
            return Long.parseLong(localValue.substring(sep + 1)) < System.currentTimeMillis();
        } catch (NumberFormatException e) {
            return true;
        }
    }

    private boolean useRedis() {
        return redisTemplate != null;
    }
}
