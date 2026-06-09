package com.bend.platform.service;

import java.util.Map;
import java.util.Optional;

/**
 * 跨 Agent 的 Xbox 串流租约（Redis SET NX + TTL）。
 *
 * <p>以 GSSV serverId（xbox_host.xbox_id）为键，在 SmartGlass 握手前互斥占用物理主机。
 */
public interface StreamLeaseService {

    /** 连接阶段默认租约秒数（握手 + 首帧预算）。 */
    int DEFAULT_CONNECT_LEASE_SEC = 120;

    /** 串流稳定后续期秒数。 */
    int DEFAULT_STREAMING_LEASE_SEC = 3600;

    /**
     * 原子申请租约；同一 agentId+taskId 可重入并刷新 TTL。
     *
     * @return true 表示当前调用方持有租约
     */
    boolean tryAcquire(String serverId, String agentId, String taskId, int ttlSeconds);

    /**
     * 释放租约；仅持有者可释放。
     */
    boolean release(String serverId, String agentId, String taskId);

    /** 读取当前租约快照（供占用查询）。 */
    Optional<Map<String, Object>> getLease(String serverId);

    /** Redis 是否可用（不可用时会降级进程内 Map，仅单 JVM 有效）。 */
    boolean isClusterSafe();
}
