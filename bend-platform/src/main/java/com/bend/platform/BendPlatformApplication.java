package com.bend.platform;

import com.bend.platform.websocket.AgentWebSocketEndpoint;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Bend平台后端应用启动类
 */
@SpringBootApplication
@MapperScan("com.bend.platform.repository")
@EnableScheduling
public class BendPlatformApplication {
    public static void main(String[] args) {
        ConfigurableApplicationContext context = SpringApplication.run(BendPlatformApplication.class, args);
        AgentWebSocketEndpoint.setApplicationContext(context);
    }
}