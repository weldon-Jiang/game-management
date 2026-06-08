package com.bend.gateway.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 网关配置绑定（prefix=bend.gateway）：限流、IP 过滤、熔断开关。
 * 路径级限流见 {@link RateLimit#paths}，默认 qps/burst 见 {@link DefaultLimit}。
 */
@Data
@Component
@ConfigurationProperties(prefix = "bend.gateway")
public class BendGatewayProperties {

    private RateLimit rateLimit = new RateLimit();
    private IpFilter ipFilter = new IpFilter();
    private CircuitBreaker circuitBreaker = new CircuitBreaker();
    private Cors cors = new Cors();

    @Data
    public static class RateLimit {
        private boolean enabled = true;
        private DefaultLimit defaultLimit = new DefaultLimit();
        private List<PathLimit> paths = new ArrayList<>();
    }

    @Data
    public static class DefaultLimit {
        private int qps = 100;
        private int burst = 50;
    }

    @Data
    public static class PathLimit {
        private String path;
        private int qps;
        private int burst;
    }

    @Data
    public static class IpFilter {
        private boolean enabled = true;
        private List<String> blacklist = new ArrayList<>();
        private List<String> whitelist = new ArrayList<>();
    }

    @Data
    public static class CircuitBreaker {
        private boolean enabled = true;
    }

    /** 网关 CORS：生产环境应配置具体域名白名单。 */
    @Data
    public static class Cors {
        private List<String> allowedOriginPatterns = new ArrayList<>(List.of("*"));
        private boolean allowCredentials = true;
        private long maxAge = 3600L;
    }
}
