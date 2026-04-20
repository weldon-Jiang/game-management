package com.bend.platform;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Bend平台后端应用启动类
 */
@SpringBootApplication
@MapperScan("com.bend.platform.repository")
public class BendPlatformApplication {
    public static void main(String[] args) {
        SpringApplication.run(BendPlatformApplication.class, args);
    }
}