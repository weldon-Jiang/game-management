package com.bend.platform.config;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentAuthFilterTest {

    private AgentAuthFilter filter;
    private Method requiresAgentAuth;

    @BeforeEach
    void setUp() throws Exception {
        filter = new AgentAuthFilter();
        requiresAgentAuth = AgentAuthFilter.class.getDeclaredMethod("requiresAgentAuth", String.class);
        requiresAgentAuth.setAccessible(true);
    }

    private boolean requiresAuth(String path) throws Exception {
        return (boolean) requiresAgentAuth.invoke(filter, path);
    }

    @Test
    void heartbeatRequiresAgentCredentials() throws Exception {
        assertTrue(requiresAuth("/api/agents/heartbeat"));
        assertTrue(requiresAuth("/api/agents/offline"));
        assertTrue(requiresAuth("/api/agents/status"));
        assertTrue(requiresAuth("/api/agents/uninstall"));
    }

    @Test
    void platformJwtPathsDoNotRequireAgentCredentials() throws Exception {
        assertFalse(requiresAuth("/api/agents/register"));
        assertFalse(requiresAuth("/api/agents/page"));
        assertFalse(requiresAuth("/api/agents/online"));
        assertFalse(requiresAuth("/api/agents/a1b2c3d4-e5f6-7890-abcd-ef1234567890"));
    }

    @Test
    void agentCallbackRequiresCredentials() throws Exception {
        assertTrue(requiresAuth("/api/v1/agent-callback/progress"));
    }
}
