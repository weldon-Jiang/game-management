package com.bend.platform.service;

import com.bend.platform.entity.XboxHost;

import java.util.List;

/**
 * 流媒体账号与主机 M:N 绑定服务。
 */
public interface StreamingAccountHostBindingService {

    /**
     * 查询账号下 active 绑定对应的主机列表（仅 online 状态主机）。
     */
    List<XboxHost> findActiveHostsByAccount(String streamingAccountId);

    /**
     * 判断账号与主机是否存在 active 绑定。
     */
    boolean hasActiveBinding(String streamingAccountId, String xboxHostId);

    /**
     * 手动绑定（管理端）；同对重复绑定幂等。
     */
    void bindManual(String hostId, String streamingAccountId, String gamertag);

    /**
     * 解绑主机上全部 active 绑定，并同步清理 xbox_host 遗留字段。
     */
    void unbindAllForHost(String hostId);

    /**
     * 解绑指定账号与主机的 active 绑定（账号视角）。
     */
    void unbind(String hostId, String streamingAccountId);

    /**
     * 获取主机首个 active 绑定的流媒体账号 ID（兼容旧 UI 单字段展示）。
     */
    String getPrimaryBoundStreamingAccountId(String hostId);

    /**
     * 主机是否存在任意 active 绑定。
     */
    boolean isHostBound(String hostId);

    /**
     * Agent 串流成功后确保绑定：必要时 upsert 主机并插入 binding（source=stream_success）。
     *
     * @return 平台主机实体
     */
    XboxHost ensureBinding(
            String merchantId,
            String streamingAccountId,
            String hostId,
            String serverId,
            String platform,
            String source,
            String name,
            String ipAddress,
            String gamertag);
}
