package com.bend.platform.util;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * Agent 认证工具类
 *
 * 提供 Agent 认证相关的辅助方法：
 * - 生成 Base64 编码的 Secret
 * - 验证认证头格式
 */
public class AgentAuthUtils {

    private static final String HEADER_AGENT_ID = "X-Agent-Id";
    private static final String HEADER_AGENT_SECRET = "X-Agent-Secret";

    /**
     * 编码 Agent Secret 为 Base64
     *
     * @param secret 原始 Secret
     * @return Base64 编码后的 Secret
     */
    public static String encodeSecret(String secret) {
        if (secret == null || secret.isEmpty()) {
            throw new IllegalArgumentException("Secret cannot be null or empty");
        }
        return Base64.getEncoder().encodeToString(secret.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * 解码 Base64 Secret
     *
     * @param encodedSecret Base64 编码的 Secret
     * @return 原始 Secret
     */
    public static String decodeSecret(String encodedSecret) {
        if (encodedSecret == null || encodedSecret.isEmpty()) {
            throw new IllegalArgumentException("Encoded secret cannot be null or empty");
        }
        return new String(Base64.getDecoder().decode(encodedSecret), StandardCharsets.UTF_8);
    }

    /**
     * 获取 Agent ID 请求头名称
     */
    public static String getAgentIdHeader() {
        return HEADER_AGENT_ID;
    }

    /**
     * 获取 Agent Secret 请求头名称
     */
    public static String getAgentSecretHeader() {
        return HEADER_AGENT_SECRET;
    }
}
