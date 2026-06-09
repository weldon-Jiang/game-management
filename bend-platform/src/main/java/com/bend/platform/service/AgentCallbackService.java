package com.bend.platform.service;

import java.util.List;
import java.util.Map;

/**
 * Agent HTTP callback business logic (progress, Xbox lock, task info).
 */
public interface AgentCallbackService {

    Map<String, Object> reportProgress(Map<String, Object> payload);

    Map<String, Object> getTaskInfo(String taskId);

    Map<String, Object> lockXboxHost(String xboxHostId, Map<String, Object> payload);

    Map<String, Object> unlockXboxHost(String xboxHostId, Map<String, Object> payload);

    Map<String, Object> getXboxHostStatus(String xboxHostId);

    /** 按 GSSV serverId（xbox_host.xbox_id）锁定/查询，供 Agent 无平台 UUID 时使用。 */
    Map<String, Object> lockXboxHostByXboxId(String xboxId, Map<String, Object> payload);

    Map<String, Object> unlockXboxHostByXboxId(String xboxId, Map<String, Object> payload);

    Map<String, Object> getXboxHostStatusByXboxId(String xboxId);

    /** 读取同商户、同 platform、同 /24 网段的 LAN 发现缓存。 */
    Map<String, Object> getLanDiscoveryCache(String localIp, String platform);

    /** 上报 LAN 发现结果并写入 Redis + upsert xbox_host。 */
    Map<String, Object> reportLanDiscovery(Map<String, Object> payload);

    Map<String, Object> exchangeCredential(Map<String, Object> payload);

    Map<String, Object> updateProfileBinding(String gameAccountId, Map<String, Object> payload);

    Map<String, Object> reportBillingEvent(Map<String, Object> payload);

    void reportTaskStatusLegacy(String taskId, Map<String, String> payload);

    void updateGameAccountStatusLegacy(String taskId, String gameAccountId, Map<String, Object> payload);

    List<Map<String, Object>> getGameAccountsStatusLegacy(String taskId);
}
