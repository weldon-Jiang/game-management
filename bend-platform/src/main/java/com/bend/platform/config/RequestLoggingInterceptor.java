package com.bend.platform.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.ModelAndView;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * HTTP 请求日志拦截器
 * 记录所有 API 请求的调用日志
 */
@Slf4j
@Component
public class RequestLoggingInterceptor implements HandlerInterceptor {

    private static final String START_TIME = "requestStartTime";

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        long startTime = System.currentTimeMillis();
        request.setAttribute(START_TIME, startTime);

        String requestId = request.getHeader("X-Request-ID");
        if (requestId == null) {
            requestId = generateRequestId();
        }

        log.info("[{}] {} {} - Started", requestId, request.getMethod(), request.getRequestURI());
        return true;
    }

    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response, Object handler, ModelAndView modelAndView) {
        // Post-processing if needed
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        Long startTime = (Long) request.getAttribute(START_TIME);
        if (startTime == null) {
            startTime = System.currentTimeMillis();
        }

        long duration = System.currentTimeMillis() - startTime;
        int status = response.getStatus();

        String logLevel = status >= 500 ? "ERROR" : status >= 400 ? "WARN" : "INFO";
        String logMessage = String.format("[%s] %s %s - Completed with status %d in %dms",
                request.getMethod(),
                request.getRequestURI(),
                status,
                duration);

        if ("ERROR".equals(logLevel)) {
            log.error(logMessage);
            if (ex != null) {
                log.error("Exception: ", ex);
            }
        } else if ("WARN".equals(logLevel)) {
            log.warn(logMessage);
        } else {
            log.info(logMessage);
        }
    }

    private String generateRequestId() {
        return String.format("%d-%04d",
                System.currentTimeMillis(),
                (int) (Math.random() * 10000));
    }
}
