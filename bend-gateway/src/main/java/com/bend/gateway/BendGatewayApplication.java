package com.bend.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Bend API 网关入口（Spring Cloud Gateway WebFlux，对外端口 8060）。
 * 路由 /api/**、/ws/**、/actuator/** 转发至 backend:8061。
 */
@SpringBootApplication
public class BendGatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(BendGatewayApplication.class, args);
    }
}
