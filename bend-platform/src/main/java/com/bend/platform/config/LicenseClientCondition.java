package com.bend.platform.config;

import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.core.type.AnnotatedTypeMetadata;

/**
 * 仅当 license.mode=tenant(分控模式)时,装配分控侧 License 客户端相关 Bean。
 *
 * <p>总控模式不装配,避免总控启动时无意义地向自身校验。
 */
public class LicenseClientCondition implements Condition {

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String mode = context.getEnvironment().getProperty("license.mode", "master");
        return "tenant".equalsIgnoreCase(mode);
    }
}
