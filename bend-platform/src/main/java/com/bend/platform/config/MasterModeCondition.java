package com.bend.platform.config;

import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.core.type.AnnotatedTypeMetadata;

/**
 * 判断当前是否总控(master)模式。
 * 用于限制总控专属功能(商户入驻、license签发、发卡等)仅在总控装配。
 */
public class MasterModeCondition implements Condition {
    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String mode = context.getEnvironment().getProperty("license.mode", "master");
        return !"tenant".equalsIgnoreCase(mode);
    }
}
