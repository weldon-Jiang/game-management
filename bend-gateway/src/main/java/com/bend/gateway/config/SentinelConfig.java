package com.bend.gateway.config;

import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayFlowRule;
import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayRuleManager;
import com.alibaba.csp.sentinel.adapter.gateway.sc.callback.BlockRequestHandler;
import com.alibaba.csp.sentinel.slots.block.RuleConstant;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.server.ServerResponse;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.HashSet;
import java.util.Set;

@Configuration
@RequiredArgsConstructor
public class SentinelConfig {

    private final BendGatewayProperties gatewayProperties;

    @PostConstruct
    public void initRules() {
        if (!gatewayProperties.getCircuitBreaker().isEnabled()) {
            return;
        }

        Set<GatewayFlowRule> rules = new HashSet<>();

        GatewayFlowRule apiRule = new GatewayFlowRule("backend-service")
                .setGrade(RuleConstant.FLOW_GRADE_QPS)
                .setCount(200)
                .setIntervalSec(1);
        rules.add(apiRule);

        GatewayFlowRule wsRule = new GatewayFlowRule("websocket-service")
                .setGrade(RuleConstant.FLOW_GRADE_QPS)
                .setCount(100)
                .setIntervalSec(1);
        rules.add(wsRule);

        GatewayRuleManager.loadRules(rules);
    }

    @Bean
    @Order(Ordered.HIGHEST_PRECEDENCE)
    public BlockRequestHandler blockRequestHandler() {
        return (exchange, t) -> ServerResponse
                .status(HttpStatus.TOO_MANY_REQUESTS)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"code\":429,\"message\":\"服务繁忙，请稍后再试\"}");
    }
}
