package com.bend.platform.util;

import com.bend.platform.dto.LoginUserInfo;
import lombok.extern.slf4j.Slf4j;

/**
 * 用户上下文工具类
 * 使用ThreadLocal存储当前请求的用户信息
 * 在JWT认证拦截器中设置，供整个请求周期使用
 */
@Slf4j
public class UserContext {

    private static final ThreadLocal<LoginUserInfo> USER_INFO_HOLDER = new ThreadLocal<>();

    /**
     * 设置当前登录用户信息
     *
     * @param userInfo 登录用户信息
     */
    public static void setUserInfo(LoginUserInfo userInfo) {
        USER_INFO_HOLDER.set(userInfo);
    }

    /**
     * 获取当前登录用户信息
     *
     * @return 登录用户信息，如果未登录则返回null
     */
    public static LoginUserInfo getUserInfo() {
        return USER_INFO_HOLDER.get();
    }

    /**
     * 获取当前用户ID
     *
     * @return 用户ID
     */
    public static String getUserId() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null ? userInfo.getUserId() : null;
    }

    /**
     * 获取当前用户名
     *
     * @return 用户名
     */
    public static String getUsername() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null ? userInfo.getUsername() : null;
    }

    /**
     * 获取当前商户ID
     *
     * @return 商户ID
     */
    public static String getMerchantId() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null ? userInfo.getMerchantId() : null;
    }

    /**
     * 获取当前用户角色
     *
     * @return 角色
     */
    public static String getRole() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null ? userInfo.getRole() : null;
    }

    /**
     * 判断当前用户是否为平台管理员
     *
     * @return 是否为平台管理员
     */
    public static boolean isPlatformAdmin() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null && userInfo.isPlatformAdmin();
    }

    /**
     * 判断当前用户是否为商户所有者
     *
     * @return 是否为商户所有者
     */
    public static boolean isOwner() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null && userInfo.isOwner();
    }

    /**
     * 判断当前用户是否为商户管理员
     *
     * @return 是否为商户管理员
     */
    public static boolean isAdmin() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null && userInfo.isAdmin();
    }

    /**
     * 判断当前用户是否为操作员
     *
     * @return 是否为操作员
     */
    public static boolean isOperator() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null && userInfo.isOperator();
    }

    /**
     * 判断当前用户是否有管理权限
     *
     * @return 是否有管理权限
     */
    public static boolean hasManagementPermission() {
        LoginUserInfo userInfo = getUserInfo();
        return userInfo != null && userInfo.hasManagementPermission();
    }

    /**
     * 清除当前用户信息
     * 在请求结束时调用，防止内存泄漏
     */
    public static void clear() {
        USER_INFO_HOLDER.remove();
    }
}