package com.bend.platform.aspect;

import com.bend.platform.annotation.Idempotent;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.lang.reflect.Method;
import java.util.concurrent.TimeUnit;

@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class IdempotentInterceptor {

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    private static final String IDEMPOTENT_PREFIX = "idempotent:";

    @Around("@annotation(com.bend.platform.annotation.Idempotent)")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        if (redisTemplate == null) {
            return joinPoint.proceed();
        }

        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        Idempotent idempotent = method.getAnnotation(Idempotent.class);

        String userId = UserContext.getUserId();
        String className = joinPoint.getTarget().getClass().getSimpleName();
        String methodName = method.getName();

        String redisKey = buildKey(userId, className, methodName, idempotent.key());

        Boolean acquired = redisTemplate.opsForValue()
                .setIfAbsent(redisKey, "1", idempotent.expireSeconds(), TimeUnit.SECONDS);

        if (Boolean.FALSE.equals(acquired)) {
            log.warn("幂等性校验失败 - userId: {}, key: {}", userId, redisKey);
            throw new BusinessException(400, idempotent.message());
        }

        try {
            return joinPoint.proceed();
        } finally {
            redisTemplate.delete(redisKey);
        }
    }

    private String buildKey(String userId, String className, String methodName, String customKey) {
        if (customKey != null && !customKey.isEmpty()) {
            return IDEMPOTENT_PREFIX + userId + ":" + className + ":" + methodName + ":" + customKey;
        }
        return IDEMPOTENT_PREFIX + userId + ":" + className + ":" + methodName;
    }
}