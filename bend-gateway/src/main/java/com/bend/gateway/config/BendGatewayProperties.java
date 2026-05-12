package com.bend.gateway.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Data
@Component
@ConfigurationProperties(prefix = "bend.gateway")
public class BendGatewayProperties {

    private RateLimit rateLimit = new RateLimit();
    private IpFilter ipFilter = new IpFilter();
    private CircuitBreaker circuitBreaker = new CircuitBreaker();

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
}
