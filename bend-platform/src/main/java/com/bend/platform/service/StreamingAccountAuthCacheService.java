package com.bend.platform.service;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 串流账号 xblive Token 平台缓存读写。
 */
public interface StreamingAccountAuthCacheService {

    /**
     * 读取解密后的 token 缓存；不存在时 {@code found=false}。
     */
    Map<String, Object> getAuthCache(String streamingAccountId, String merchantId);

    /**
     * 写入 token 缓存；{@code expectedTokenVersion} 与库中不一致时抛出 409。
     *
     * @return 含 saved、tokenVersion
     */
    Map<String, Object> saveAuthCache(
            String streamingAccountId,
            String merchantId,
            String agentId,
            Map<String, Object> tokenDoc,
            Integer expectedTokenVersion,
            String authState,
            LocalDateTime xhomeExpiresAt);

    /**
     * 清除串流账号 Token 缓存（refresh 作废或认证不可恢复失败时）。
     */
    void deleteAuthCache(String streamingAccountId, String merchantId);
}
