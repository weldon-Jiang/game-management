package com.bend.platform.config;

import com.bend.platform.service.LicenseClientService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 分控 License 闸门过滤器
 *
 * <p>仅 tenant 模式装配。拦截"启动串流 / 启动自动化任务"等关键写操作,
 * 当 license 失效(已过期/已吊销/超出离线宽限期)时直接返回 403,阻止新任务启动。
 *
 * <p>放行: 登录、查询、license 校验本身。
 *
 * <p>注意: Agent 回调(agent-callback)也在拦截范围——商户可能修改 Agent 代码跳过校验,
 * 因此分控侧每次收到 Agent 进度上报也重新验证 license,失效则拒绝接收。
 */
@Slf4j
@Configuration
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class LicenseGateFilter {

    private final LicenseClientService licenseClientService;
    private final ObjectMapper objectMapper;

    @Value("${license.gate.paths:streaming-sessions,start,tasks,agent-callback}")
    private String gateKeywordsCsv;

    @Bean
    public FilterRegistrationBean<Filter> licenseGateFilterRegistration() {
        FilterRegistrationBean<Filter> reg = new FilterRegistrationBean<>();
        reg.setFilter(new GateFilter(licenseClientService, objectMapper, gateKeywordsCsv));
        reg.addUrlPatterns("/api/*");
        reg.setName("licenseGateFilter");
        reg.setOrder(50); // 早于业务,晚于 IP 过滤
        return reg;
    }

    static class GateFilter implements Filter {
        private final LicenseClientService licenseClientService;
        private final ObjectMapper objectMapper;
        private final String[] keywords;

        GateFilter(LicenseClientService s, ObjectMapper om, String kwCsv) {
            this.licenseClientService = s;
            this.objectMapper = om;
            this.keywords = kwCsv == null ? new String[0] : kwCsv.split(",");
        }

        @Override
        public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain)
                throws IOException, ServletException {
            HttpServletRequest httpReq = (HttpServletRequest) req;
            HttpServletResponse httpResp = (HttpServletResponse) resp;

            String method = httpReq.getMethod();
            String uri = httpReq.getRequestURI();

            // 仅拦截会改变状态的写操作
            boolean isWrite = "POST".equalsIgnoreCase(method) || "PUT".equalsIgnoreCase(method)
                    || "DELETE".equalsIgnoreCase(method);
            if (!isWrite || !isGated(uri)) {
                chain.doFilter(req, resp);
                return;
            }

            if (!licenseClientService.isAuthorized()) {
                LicenseClientService.LicenseStatus st = licenseClientService.getStatus();
                log.warn("License失效,拒绝请求 {} {} source={} reason={}", method, uri, st.source(), st.invalidReason());
                writeForbidden(httpResp, st);
                return;
            }
            chain.doFilter(req, resp);
        }

        private boolean isGated(String uri) {
            if (uri == null) return false;
            String lower = uri.toLowerCase();
            for (String kw : keywords) {
                if (kw != null && !kw.isBlank() && lower.contains(kw.trim().toLowerCase())) {
                    return true;
                }
            }
            return false;
        }

        private void writeForbidden(HttpServletResponse resp, LicenseClientService.LicenseStatus st) throws IOException {
            resp.setStatus(HttpServletResponse.SC_FORBIDDEN);
            resp.setContentType(MediaType.APPLICATION_JSON_VALUE);
            resp.setCharacterEncoding("UTF-8");
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("code", 25003);
            body.put("message", "授权已失效,无法启动新任务:" + (st.invalidReason() == null ? "LICENSE_INVALID" : st.invalidReason()));
            body.put("data", null);
            resp.getWriter().write(objectMapper.writeValueAsString(body));
        }
    }
}
