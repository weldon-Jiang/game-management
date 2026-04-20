package com.bend.platform.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 登录用户信息
 * 从JWT token解析后存储到上下文，供整个请求周期使用
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginUserInfo {

    /**
     * 用户ID
     */
    private String userId;

    /**
     * 用户名
     */
    private String username;

    /**
     * 商户ID
     */
    private String merchantId;

    /**
     * 角色
     */
    private String role;

    /**
     * 判断是否为平台管理员
     */
    public boolean isPlatformAdmin() {
        return "platform_admin".equals(role);
    }

    /**
     * 判断是否为商户所有者
     */
    public boolean isOwner() {
        return "owner".equals(role);
    }

    /**
     * 判断是否为商户管理员
     */
    public boolean isAdmin() {
        return "admin".equals(role);
    }

    /**
     * 判断是否为操作员
     */
    public boolean isOperator() {
        return "operator".equals(role);
    }

    /**
     * 判断是否有管理权限（平台管理员、商户所有者、商户管理员）
     */
    public boolean hasManagementPermission() {
        return isPlatformAdmin() || isOwner() || isAdmin();
    }
}