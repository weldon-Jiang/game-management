package com.bend.platform.service.impl;

import com.bend.platform.service.LanDiscoveryCacheService;
import com.bend.platform.service.XboxHostService;
import com.bend.platform.util.LanSegmentUtil;
import com.bend.platform.util.PlatformTypeUtil;
import com.bend.platform.util.XboxIdUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * LAN 主机发现 Redis 缓存：同商户 + 同 platform + 同 /24 网段共享，TTL 默认 90s。
 */
@Service
public class LanDiscoveryCacheServiceImpl implements LanDiscoveryCacheService {

    private static final Logger log = LoggerFactory.getLogger(LanDiscoveryCacheServiceImpl.class);
    private static final String KEY_PREFIX = "lan:discovery:";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    private final XboxHostService xboxHostService;

    @Value("${discovery.lan-cache-ttl-sec:90}")
    private int defaultTtlSec;

    public LanDiscoveryCacheServiceImpl(XboxHostService xboxHostService) {
        this.xboxHostService = xboxHostService;
    }

    @Override
    public Map<String, Object> report(
            String merchantId,
            String agentId,
            String platform,
            String localIp,
            List<Map<String, Object>> consoles,
            int ttlSeconds) {
        Map<String, Object> result = new HashMap<>();
        result.put("accepted", false);

        String normalizedPlatform = PlatformTypeUtil.requireValid(platform);

        if (!LanSegmentUtil.isPrivateLanIp(localIp)) {
            result.put("reason", "INVALID_LOCAL_IP");
            result.put("message", "localIp 必须为 RFC1918 局域网地址");
            return result;
        }
        String lanSegment = LanSegmentUtil.segmentFromIp(localIp);
        if (lanSegment == null || consoles == null || consoles.isEmpty()) {
            result.put("reason", "EMPTY_CONSOLES");
            return result;
        }

        List<Map<String, Object>> normalized = new ArrayList<>();
        List<Map<String, Object>> upserted = new ArrayList<>();
        for (Map<String, Object> raw : consoles) {
            Map<String, Object> console = normalizeConsole(raw, lanSegment, normalizedPlatform);
            if (console == null) {
                continue;
            }
            normalized.add(console);
            String serverId = (String) console.get("serverId");
            var host = xboxHostService.createOrUpdate(
                    merchantId,
                    serverId,
                    (String) console.get("name"),
                    (String) console.get("ipAddress"),
                    (Integer) console.get("port"),
                    (String) console.get("liveId"),
                    (String) console.get("consoleType"),
                    null,
                    null,
                    normalizedPlatform);
            Map<String, Object> hostBrief = new HashMap<>();
            hostBrief.put("id", host.getId());
            hostBrief.put("serverId", serverId);
            hostBrief.put("ipAddress", host.getIpAddress());
            hostBrief.put("platform", host.getPlatform());
            upserted.add(hostBrief);
        }

        if (normalized.isEmpty()) {
            result.put("reason", "NO_VALID_CONSOLES");
            return result;
        }

        Map<String, Object> payload = new HashMap<>();
        payload.put("platform", normalizedPlatform);
        payload.put("lanSegment", lanSegment);
        payload.put("reporterAgentId", agentId);
        payload.put("reporterLocalIp", localIp);
        payload.put("discoveredAt", System.currentTimeMillis());
        payload.put("consoles", normalized);

        int ttl = Math.max(30, ttlSeconds > 0 ? ttlSeconds : defaultTtlSec);
        boolean cached = writeRedis(merchantId, normalizedPlatform, lanSegment, payload, ttl);

        result.put("accepted", true);
        result.put("cached", cached);
        result.put("platform", normalizedPlatform);
        result.put("lanSegment", lanSegment);
        result.put("consoleCount", normalized.size());
        result.put("ttlSec", ttl);
        result.put("upsertedHosts", upserted);
        log.info("LAN 发现已上报 merchant={} platform={} segment={} consoles={} cached={} agent={}",
                merchantId, normalizedPlatform, lanSegment, normalized.size(), cached, agentId);
        return result;
    }

    @Override
    public Map<String, Object> getForAgent(String merchantId, String agentId, String platform, String localIp) {
        Map<String, Object> result = new HashMap<>();
        result.put("hit", false);
        result.put("consoles", List.of());

        String normalizedPlatform = PlatformTypeUtil.requireValid(platform);

        if (!LanSegmentUtil.isPrivateLanIp(localIp)) {
            result.put("reason", "INVALID_LOCAL_IP");
            return result;
        }
        String lanSegment = LanSegmentUtil.segmentFromIp(localIp);
        if (lanSegment == null) {
            result.put("reason", "INVALID_SEGMENT");
            return result;
        }

        Map<String, Object> payload = readRedis(merchantId, normalizedPlatform, lanSegment);
        if (payload == null) {
            result.put("reason", "MISS");
            result.put("platform", normalizedPlatform);
            return result;
        }

        String cachedPlatform = (String) payload.get("platform");
        if (!normalizedPlatform.equals(cachedPlatform)) {
            result.put("reason", "PLATFORM_MISMATCH");
            return result;
        }

        String cachedSegment = (String) payload.get("lanSegment");
        if (!lanSegment.equals(cachedSegment)) {
            result.put("reason", "SEGMENT_MISMATCH");
            return result;
        }

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> consoles = (List<Map<String, Object>>) payload.get("consoles");
        if (consoles == null) {
            consoles = List.of();
        }

        List<Map<String, Object>> filtered = new ArrayList<>();
        for (Map<String, Object> c : consoles) {
            String ip = (String) c.get("ipAddress");
            if (ip != null && LanSegmentUtil.isSameSegment(localIp, ip)) {
                filtered.add(c);
            }
        }

        long discoveredAt = payload.get("discoveredAt") instanceof Number n
                ? n.longValue() : 0L;
        result.put("hit", !filtered.isEmpty());
        result.put("consoles", filtered);
        result.put("platform", normalizedPlatform);
        result.put("lanSegment", lanSegment);
        result.put("reporterAgentId", payload.get("reporterAgentId"));
        result.put("reporterLocalIp", payload.get("reporterLocalIp"));
        result.put("discoveredAt", discoveredAt);
        result.put("ageSec", discoveredAt > 0
                ? Math.max(0, (System.currentTimeMillis() - discoveredAt) / 1000) : null);
        result.put("sameLanRequired", true);
        log.debug("LAN 缓存查询 merchant={} platform={} segment={} hit={} requester={} count={}",
                merchantId, normalizedPlatform, lanSegment, !filtered.isEmpty(), agentId, filtered.size());
        return result;
    }

    private Map<String, Object> normalizeConsole(Map<String, Object> raw, String lanSegment, String platform) {
        if (raw == null) {
            return null;
        }
        String serverId = firstString(raw, "serverId", "deviceId", "device_id", "id");
        String ip = firstString(raw, "ipAddress", "ip_address", "ip");
        if (serverId == null || serverId.isBlank() || ip == null || ip.isBlank()) {
            return null;
        }
        if (!LanSegmentUtil.isSameSegment(lanSegment + ".1", ip)) {
            log.warn("忽略非本网段主机 serverId={} ip={} segment={}", serverId, ip, lanSegment);
            return null;
        }
        if ("xbox".equals(platform)) {
            serverId = XboxIdUtil.normalizeCanonical(serverId);
        }
        Map<String, Object> console = new HashMap<>();
        console.put("serverId", serverId);
        console.put("name", firstString(raw, "name", "consoleName"));
        console.put("ipAddress", ip);
        console.put("port", raw.get("port") != null ? raw.get("port") : 5050);
        console.put("liveId", firstString(raw, "liveId", "live_id", "serverId"));
        console.put("consoleType", firstString(raw, "consoleType", "console_type"));
        console.put("certificateB64", firstString(raw, "certificateB64", "certificate_b64"));
        console.put("platform", platform);
        return console;
    }

    private static String firstString(Map<String, Object> raw, String... keys) {
        for (String key : keys) {
            Object val = raw.get(key);
            if (val != null && !val.toString().isBlank()) {
                return val.toString();
            }
        }
        return null;
    }

    private boolean writeRedis(String merchantId, String platform, String lanSegment,
                               Map<String, Object> payload, int ttl) {
        if (redisTemplate == null) {
            log.warn("Redis 不可用，LAN 发现缓存未写入");
            return false;
        }
        try {
            String key = KEY_PREFIX + merchantId + ":" + platform + ":" + lanSegment;
            redisTemplate.opsForValue().set(key, MAPPER.writeValueAsString(payload), Duration.ofSeconds(ttl));
            return true;
        } catch (Exception e) {
            log.warn("写入 LAN 发现缓存失败: {}", e.getMessage());
            return false;
        }
    }

    private Map<String, Object> readRedis(String merchantId, String platform, String lanSegment) {
        if (redisTemplate == null) {
            return null;
        }
        try {
            String key = KEY_PREFIX + merchantId + ":" + platform + ":" + lanSegment;
            String json = redisTemplate.opsForValue().get(key);
            if (json == null || json.isBlank()) {
                return null;
            }
            return MAPPER.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            log.warn("读取 LAN 发现缓存失败: {}", e.getMessage());
            return null;
        }
    }
}
