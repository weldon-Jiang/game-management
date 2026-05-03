package com.bend.platform.util;

import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import org.springframework.stereotype.Component;

/**
 * 数据安全检查工具类
 * 用于验证资源是否属于当前商户，防止越权访问
 */
@Component
public class DataSecurityUtil {

    /**
     * 验证资源是否属于当前商户
     *
     * @param resourceMerchantId 资源的商户ID
     * @param resourceName 资源名称（用于错误信息）
     */
    public void validateMerchantAccess(String resourceMerchantId, String resourceName) {
        if (resourceMerchantId == null) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        String currentMerchantId = UserContext.getMerchantId();
        String currentRole = UserContext.getRole();

        if (currentRole == null) {
            throw new BusinessException(ResultCode.Auth.TOKEN_INVALID);
        }

        if ("platform_admin".equals(currentRole)) {
            return;
        }

        if (!resourceMerchantId.equals(currentMerchantId)) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }

    /**
     * 验证资源是否属于当前商户（带自定义错误码）
     */
    public void validateMerchantAccess(String resourceMerchantId, String resourceName, ResultCode errorCode) {
        if (resourceMerchantId == null) {
            throw new BusinessException(errorCode);
        }

        String currentMerchantId = UserContext.getMerchantId();
        String currentRole = UserContext.getRole();

        if (currentRole == null) {
            throw new BusinessException(ResultCode.Auth.TOKEN_INVALID);
        }

        if ("platform_admin".equals(currentRole)) {
            return;
        }

        if (!resourceMerchantId.equals(currentMerchantId)) {
            throw new BusinessException(errorCode);
        }
    }

    /**
     * 检查当前用户是否为平台管理员
     */
    public boolean isPlatformAdmin() {
        String role = UserContext.getRole();
        return "platform_admin".equals(role);
    }

    /**
     * 检查当前用户是否有权访问指定商户的数据
     */
    public boolean canAccessMerchant(String targetMerchantId) {
        if (targetMerchantId == null) {
            return false;
        }

        String currentRole = UserContext.getRole();
        if ("platform_admin".equals(currentRole)) {
            return true;
        }

        String currentMerchantId = UserContext.getMerchantId();
        return targetMerchantId.equals(currentMerchantId);
    }
}
