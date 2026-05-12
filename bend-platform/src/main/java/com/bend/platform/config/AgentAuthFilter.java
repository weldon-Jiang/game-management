package com.bend.platform.config;

import com.bend.platform.service.AgentInstanceService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.context.WebApplicationContext;
import org.springframework.web.context.support.WebApplicationContextUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

/**
 * Agent API 认证过滤器
 *
 * 功能说明：
 * - 验证请求头中的 X-Agent-Id 和 X-Agent-Secret
 * - 仅对 /api/agents/** 和 /api/agent-callback/** 路径生效
 * - 每个请求都需要验证 AgentSecret，防止未授权访问
 *
 * 请求头要求：
 * - X-Agent-Id: Agent唯一标识
 * - X-Agent-Secret: Agent密钥（Base64编码）
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AgentAuthFilter implements Filter {

    private static final String HEADER_AGENT_ID = "X-Agent-Id";
    private static final String HEADER_AGENT_SECRET = "X-Agent-Secret";

    private AgentInstanceService agentInstanceService;

    @Override
    public void init(FilterConfig filterConfig) throws ServletException {
        ServletContext context = filterConfig.getServletContext();
        WebApplicationContext ctx = WebApplicationContextUtils.getWebApplicationContext(context);
        if (ctx != null) {
            agentInstanceService = ctx.getBean(AgentInstanceService.class);
        }
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String path = httpRequest.getRequestURI();

        // 仅对 Agent API 路径进行认证
        if (!requiresAgentAuth(path)) {
            chain.doFilter(request, response);
            return;
        }

        String agentId = httpRequest.getHeader(HEADER_AGENT_ID);
        String agentSecret = httpRequest.getHeader(HEADER_AGENT_SECRET);

        // 验证请求头完整性
        if (agentId == null || agentId.isEmpty() || agentSecret == null || agentSecret.isEmpty()) {
            log.warn("Agent认证失败 - 路径: {}, 原因: 缺少认证信息, IP: {}",
                    path, getClientIp(httpRequest));
            sendError(httpResponse, HttpServletResponse.SC_UNAUTHORIZED, "Missing Agent credentials");
            return;
        }

        // Base64 解码 Secret
        String decodedSecret;
        try {
            decodedSecret = new String(Base64.getDecoder().decode(agentSecret), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            log.warn("Agent认证失败 - AgentID: {}, 原因: Secret格式错误, IP: {}",
                    agentId, getClientIp(httpRequest));
            sendError(httpResponse, HttpServletResponse.SC_UNAUTHORIZED, "Invalid Secret format");
            return;
        }

        // 验证 Agent 凭证
        if (agentInstanceService == null) {
            log.error("AgentInstanceService未初始化");
            sendError(httpResponse, HttpServletResponse.SC_INTERNAL_SERVER_ERROR, "Service unavailable");
            return;
        }

        boolean isValid = agentInstanceService.validateCredentials(agentId, decodedSecret);
        if (!isValid) {
            log.warn("Agent认证失败 - AgentID: {}, 原因: 无效的认证信息, IP: {}",
                    agentId, getClientIp(httpRequest));
            sendError(httpResponse, HttpServletResponse.SC_UNAUTHORIZED, "Invalid credentials");
            return;
        }

        // 将 AgentId 放入请求属性，供后续使用
        httpRequest.setAttribute("agentId", agentId);

        log.debug("Agent认证成功 - AgentID: {}, 路径: {}", agentId, path);
        chain.doFilter(request, response);
    }

    /**
     * 判断路径是否需要 Agent 认证
     * 
     * 平台调用接口（使用 JWT 认证，不需要 Agent 凭证）：
     * - GET /api/agents/page - 分页查询
     * - GET /api/agents/{agentId} - 查询详情
     * - POST /api/agents/register - 注册（使用注册码，无需认证）
     * 
     * Agent 服务调用接口（需要 Agent 凭证）：
     * - POST /api/agents/heartbeat - 心跳
     * - POST /api/agents/offline - 下线
     * - POST /api/agents/uninstall - 卸载
     * - POST /api/agents/status - 状态更新
     */
    private boolean requiresAgentAuth(String path) {
        // 平台调用接口或注册接口，不需要 Agent 凭证
        if (path.equals("/api/agents/register") ||
            path.equals("/api/agents/page") ||
            path.matches("/api/agents/[a-zA-Z0-9-]+$")) {
            return false;
        }
        
        // Agent 服务调用的接口需要凭证
        return path.startsWith("/api/agent-callback/") ||
               path.equals("/ws/agents") ||
               isAgentServiceEndpoint(path);
    }
    
    /**
     * 判断是否是 Agent 服务端点（需要 X-Agent-Id 和 X-Agent-Secret）
     */
    private boolean isAgentServiceEndpoint(String path) {
        return path.equals("/api/agents/heartbeat") ||
               path.equals("/api/agents/offline") ||
               path.equals("/api/agents/uninstall") ||
               path.equals("/api/agents/status");
    }

    /**
     * 获取客户端 IP 地址
     */
    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("Proxy-Client-IP");
        }
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("WL-Proxy-Client-IP");
        }
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        // 多级代理时取第一个 IP
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }

    /**
     * 发送错误响应
     */
    private void sendError(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        Map<String, Object> error = new HashMap<>();
        error.put("code", status);
        error.put("message", message);
        error.put("success", false);
        response.getWriter().write(new ObjectMapper().writeValueAsString(error));
    }

    @Override
    public void destroy() {
    }
}
