package com.bend.platform.config;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.regex.Pattern;

/**
 * 全局 XSS 防护过滤器
 *
 * 功能说明：
 * - 过滤所有 HTTP 请求中的危险字符
 * - 防止 XSS 跨站脚本攻击
 * - 对 HTML 和 JavaScript 特殊字符进行转义
 *
 * 防护内容：
 * - <script> 标签
 * - JavaScript 事件处理器 (onclick, onerror 等)
 * - JavaScript URI (javascript:)
 * - HTML 特殊字符转义
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class XssFilter implements Filter {

    private static final Pattern[] DANGEROUS_PATTERNS = {
            Pattern.compile("<script[^>]*>.*?</script>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL),
            Pattern.compile("javascript:", Pattern.CASE_INSENSITIVE),
            Pattern.compile("on\\w+\\s*=", Pattern.CASE_INSENSITIVE),
            Pattern.compile("<[^>]+>", Pattern.CASE_INSENSITIVE),
            Pattern.compile("&lt;", Pattern.CASE_INSENSITIVE),
            Pattern.compile("&gt;", Pattern.CASE_INSENSITIVE),
            Pattern.compile("\"", Pattern.LITERAL),
            Pattern.compile("'", Pattern.LITERAL),
            Pattern.compile("<", Pattern.LITERAL),
            Pattern.compile(">", Pattern.LITERAL),
            Pattern.compile("eval\\s*\\(", Pattern.CASE_INSENSITIVE),
            Pattern.compile("expression\\s*\\(", Pattern.CASE_INSENSITIVE),
    };

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;

        if (isExcluded(httpRequest)) {
            chain.doFilter(request, response);
            return;
        }

        chain.doFilter(new XssRequestWrapper(httpRequest), response);
    }

    private boolean isExcluded(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.contains("/actuator/")
                || path.contains("/swagger-ui")
                || path.contains("/v3/api-docs")
                || path.contains("/websocket");
    }

    private static class XssRequestWrapper extends HttpServletRequestWrapper {

        public XssRequestWrapper(HttpServletRequest request) {
            super(request);
        }

        @Override
        public String[] getParameterValues(String name) {
            String[] values = super.getParameterValues(name);
            if (values == null) {
                return null;
            }
            String[] encodedValues = new String[values.length];
            for (int i = 0; i < values.length; i++) {
                encodedValues[i] = sanitize(values[i]);
            }
            return encodedValues;
        }

        @Override
        public String getParameter(String name) {
            String value = super.getParameter(name);
            return sanitize(value);
        }

        @Override
        public String getHeader(String name) {
            String value = super.getHeader(name);
            return sanitize(value);
        }

        private String sanitize(String value) {
            if (value == null) {
                return null;
            }
            String sanitized = value;
            for (Pattern pattern : DANGEROUS_PATTERNS) {
                sanitized = pattern.matcher(sanitized).replaceAll("");
            }
            return sanitized.trim();
        }
    }
}
