package com.bend.platform.aspect;

import com.bend.platform.annotation.AuditLog;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.stereotype.Component;

import java.lang.reflect.Method;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class AuditLogAspect {

    @Around("@annotation(com.bend.platform.annotation.AuditLog)")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        AuditLog auditLog = method.getAnnotation(AuditLog.class);

        String userId = UserContext.getUserId();
        String merchantId = UserContext.getMerchantId();
        String action = auditLog.action();
        String module = auditLog.module();

        long startTime = System.currentTimeMillis();
        Object result = null;
        boolean success = true;
        String errorMessage = null;

        try {
            result = joinPoint.proceed();
            return result;
        } catch (Throwable e) {
            success = false;
            errorMessage = e.getMessage();
            throw e;
        } finally {
            long duration = System.currentTimeMillis() - startTime;
            logAudit(userId, merchantId, module, action, auditLog.description(),
                    joinPoint.getTarget().getClass().getSimpleName(), method.getName(),
                    success, errorMessage, duration);
        }
    }

    private void logAudit(String userId, String merchantId, String module, String action,
                         String description, String className, String methodName,
                         boolean success, String errorMessage, long duration) {
        Map<String, Object> auditEntry = new HashMap<>();
        auditEntry.put("timestamp", LocalDateTime.now().toString());
        auditEntry.put("userId", userId);
        auditEntry.put("merchantId", merchantId);
        auditEntry.put("module", module);
        auditEntry.put("action", action);
        auditEntry.put("description", description);
        auditEntry.put("className", className);
        auditEntry.put("methodName", methodName);
        auditEntry.put("success", success);
        auditEntry.put("errorMessage", errorMessage);
        auditEntry.put("durationMs", duration);

        log.info("[AUDIT] {}", auditEntry);
    }
}