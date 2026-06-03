package com.bend.platform.config;

import com.bend.platform.service.AgentInstanceService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AgentAuthFilterDoFilterTest {

    @Mock
    private AgentInstanceService agentInstanceService;
    @Mock
    private HttpServletRequest request;
    @Mock
    private HttpServletResponse response;
    @Mock
    private FilterChain chain;

    private AgentAuthFilter filter;

    @BeforeEach
    void setUp() throws Exception {
        filter = new AgentAuthFilter();
        Field field = AgentAuthFilter.class.getDeclaredField("agentInstanceService");
        field.setAccessible(true);
        field.set(filter, agentInstanceService);
    }

    @Test
    void heartbeatWithBase64SecretPassesFilter() throws Exception {
        String plain = "agent-secret-plain";
        String encoded = Base64.getEncoder().encodeToString(plain.getBytes(StandardCharsets.UTF_8));

        when(request.getRequestURI()).thenReturn("/api/agents/heartbeat");
        when(request.getHeader("X-Agent-Id")).thenReturn("agent-uuid-1");
        when(request.getHeader("X-Agent-Secret")).thenReturn(encoded);
        when(agentInstanceService.validateCredentials("agent-uuid-1", plain)).thenReturn(true);

        filter.doFilter(request, response, chain);

        verify(chain).doFilter(request, response);
        verify(response, never()).setStatus(HttpServletResponse.SC_UNAUTHORIZED);
    }

    @Test
    void heartbeatWithPlainSecretPassesFilter() throws Exception {
        String plain = "plain-secret-no-base64";

        when(request.getRequestURI()).thenReturn("/api/agents/heartbeat");
        when(request.getHeader("X-Agent-Id")).thenReturn("agent-uuid-2");
        when(request.getHeader("X-Agent-Secret")).thenReturn(plain);
        when(agentInstanceService.validateCredentials("agent-uuid-2", plain)).thenReturn(true);

        filter.doFilter(request, response, chain);

        verify(chain).doFilter(request, response);
    }

    @Test
    void heartbeatWithoutCredentialsReturns401() throws Exception {
        when(request.getRequestURI()).thenReturn("/api/agents/heartbeat");
        when(request.getHeader("X-Agent-Id")).thenReturn(null);
        when(request.getHeader("X-Agent-Secret")).thenReturn(null);
        when(response.getWriter()).thenReturn(new PrintWriter(new StringWriter()));

        filter.doFilter(request, response, chain);

        verify(response).setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        verify(chain, never()).doFilter(request, response);
        verify(agentInstanceService, never()).validateCredentials(anyString(), anyString());
    }

    @Test
    void invalidCredentialsReturns401() throws Exception {
        String plain = "wrong";
        String encoded = Base64.getEncoder().encodeToString(plain.getBytes(StandardCharsets.UTF_8));

        when(request.getRequestURI()).thenReturn("/api/agents/heartbeat");
        when(request.getHeader("X-Agent-Id")).thenReturn("agent-uuid-3");
        when(request.getHeader("X-Agent-Secret")).thenReturn(encoded);
        when(agentInstanceService.validateCredentials(eq("agent-uuid-3"), eq(plain))).thenReturn(false);
        when(response.getWriter()).thenReturn(new PrintWriter(new StringWriter()));

        filter.doFilter(request, response, chain);

        verify(response).setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        verify(chain, never()).doFilter(request, response);
    }
}
