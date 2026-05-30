package com.bend.platform.service;

import com.bend.platform.entity.XboxHost;

/**
 * Xbox主机绑定服务接口
 * 
 * 功能说明：
 * - 管理Xbox主机与流媒体账号的绑定关系
 * - 提供独立的绑定/解绑操作
 * - 与自动化任务解耦，便于未来扩展
 */
public interface XboxHostBindingService {

    /**
     * 绑定流媒体账号到Xbox主机
     *
     * @param hostId            主机ID
     * @param streamingAccountId 流媒体账号ID
     * @param gamertag          Gamertag
     */
    void bind(String hostId, String streamingAccountId, String gamertag);

    /**
     * 解绑流媒体账号
     *
     * @param hostId 主机ID
     */
    void unbind(String hostId);

    /**
     * 获取主机绑定的流媒体账号ID
     *
     * @param hostId 主机ID
     * @return 流媒体账号ID，未绑定返回null
     */
    String getBoundStreamingAccountId(String hostId);

    /**
     * 获取主机绑定的Gamertag
     *
     * @param hostId 主机ID
     * @return Gamertag，未绑定返回null
     */
    String getBoundGamertag(String hostId);

    /**
     * 检查主机是否已绑定流媒体账号
     *
     * @param hostId 主机ID
     * @return true-已绑定，false-未绑定
     */
    boolean isBound(String hostId);

    /**
     * 获取主机绑定信息
     *
     * @param hostId 主机ID
     * @return XboxHost实体，包含绑定信息
     */
    XboxHost getHostWithBindingInfo(String hostId);
}