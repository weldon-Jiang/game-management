package com.bend.platform.util;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * Agent HTTP header secret decoding (matches AgentAuthFilter and bend-agent client).
 */
public final class AgentAuthUtils {

    private AgentAuthUtils() {
    }

    /**
     * Decode Base64 X-Agent-Secret header to plain secret for DB comparison.
     */
    public static String decodeSecretHeader(String agentSecretHeader) {
        if (agentSecretHeader == null || agentSecretHeader.isEmpty()) {
            return agentSecretHeader;
        }
        try {
            return new String(Base64.getDecoder().decode(agentSecretHeader), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            return agentSecretHeader;
        }
    }
}
