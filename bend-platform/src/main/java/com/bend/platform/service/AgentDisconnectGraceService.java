package com.bend.platform.service;

import java.util.List;

/**
 * Agent WebSocket 断线宽限期：闪断仅标记 reconnecting，超时后才允许清理任务。
 */
public interface AgentDisconnectGraceService {

    /** WS 断开时记录断线时间并标记 reconnecting。 */
    void markWsDisconnected(String agentId);

    /** WS 重连成功时清除宽限期标记。 */
    void clearOnWsReconnect(String agentId);

    /**
     * 返回满足清理条件的 Agent：宽限期已过、WS 仍离线、HTTP 心跳也已超时。
     */
    List<String> findAgentsReadyForCleanup();
}
