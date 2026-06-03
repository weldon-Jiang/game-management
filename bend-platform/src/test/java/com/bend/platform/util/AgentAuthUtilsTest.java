package com.bend.platform.util;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AgentAuthUtilsTest {

    @Test
    void decodesBase64SecretHeader() {
        String plain = "test-secret-123";
        String encoded = Base64.getEncoder().encodeToString(plain.getBytes(StandardCharsets.UTF_8));
        assertEquals(plain, AgentAuthUtils.decodeSecretHeader(encoded));
    }

    @Test
    void plainSecretPassthroughWhenNotBase64() {
        String plain = "already-plain";
        assertEquals(plain, AgentAuthUtils.decodeSecretHeader(plain));
    }
}
