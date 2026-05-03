package com.bend.platform.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 登录用户信息
 * 从JWT token解析后存储到上下文，供整个请求周期使用
 *
 * 角色说明：
 * - platform_admin: 平台管理员，管理所有商户
 * - merchant_owner: 商户所有者/管理员，管理所属商户及下级用户
 * - operator: 操作员，使用系统功能
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
     * 可选值: platform_admin, merchant_owner, operator
     */
    private String role;

    /**
     * 判断是否为平台管理员
     */
    public boolean isPlatformAdmin() {
        return "platform_admin".equals(role);
    }

    /**
     * 判断是否为商户所有者/管理员
     * 合并了 owner 和 admin 两个角色
     */
    public boolean isMerchantOwner() {
        return "merchant_owner".equals(role);
    }

    /**
     * 判断是否为操作员
     */
    public boolean isOperator() {
        return "operator".equals(role);
    }

    /**
     * 判断是否有管理权限（平台管理员、商户所有者/管理员）
     */
    public boolean hasManagementPermission() {
        return isPlatformAdmin() || isMerchantOwner();
    }

    /**
     * @deprecated 使用 isMerchantOwner() 替代
     */
    @Deprecated
    public boolean isOwner() {
        return isMerchantOwner();
    }

    /**
     * @deprecated 使用 isMerchantOwner() 替代
     */
    @Deprecated
    public boolean isAdmin() {
        return isMerchantOwner();
    }
}