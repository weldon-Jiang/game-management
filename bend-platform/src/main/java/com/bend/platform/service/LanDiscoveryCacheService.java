package com.bend.platform.service;

import java.util.List;
import java.util.Map;

/**
 * 商户维度 LAN 主机发现结果缓存（Redis）。
 *
 * <p>键按 {@code merchantId + platform + /24 网段} 隔离；仅同一局域网（相同网段 IP）的 Agent 可读取。
 */
public interface LanDiscoveryCacheService {

    int DEFAULT_TTL_SEC = 90;

    /**
     * 写入/刷新 LAN 发现缓存，并 upsert xbox_host（含 platform）。
     */
    Map<String, Object> report(
            String merchantId,
            String agentId,
            String platform,
            String localIp,
            List<Map<String, Object>> consoles,
            int ttlSeconds);

    /**
     * 读取缓存；请求方 localIp 必须与缓存网段一致，platform 必须匹配。
     */
    Map<String, Object> getForAgent(String merchantId, String agentId, String platform, String localIp);
}
