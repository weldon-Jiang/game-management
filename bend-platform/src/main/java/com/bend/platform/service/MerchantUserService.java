package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.MerchantUserPageRequest;
import com.bend.platform.entity.MerchantUser;

/**
 * 商户用户服务接口
 * 定义商户用户相关的业务操作
 */
public interface MerchantUserService {

    /**
     * 商户用户登录
     *
     * @param loginKey 登录名（用户名或手机号）
     * @param password 密码（明文）
     * @return 登录成功的用户实体
     */
    MerchantUser login(String loginKey, String password);

    /**
     * 注册新用户
     *
     * @param username    用户名
     * @param password    密码（明文，会加密存储）
     * @param merchantId  商户ID
     * @param phone       联系电话
     * @param role        角色 (owner/admin/operator)
     * @return 注册成功的用户实体
     */
    MerchantUser register(String username, String password, String merchantId, String phone, String role);

    /**
     * 根据ID查询用户
     *
     * @param id 用户ID
     * @return 用户实体，不存在返回null
     */
    MerchantUser findById(String id);

    /**
     * 根据用户名查询用户
     *
     * @param username 用户名
     * @return 用户实体，不存在返回null
     */
    MerchantUser findByUsername(String username);

    /**
     * 根据手机号查询用户
     *
     * @param phone 手机号
     * @return 用户实体，不存在返回null
     */
    MerchantUser findByPhone(String phone);

    /**
     * 分页查询商户下的所有用户
     *
     * @param merchantId 商户ID
     * @param request     分页请求参数
     * @return 分页结果
     */
    IPage<MerchantUser> findByMerchantId(String merchantId, MerchantUserPageRequest request);

    /**
     * 更新用户信息
     *
     * @param id       用户ID
     * @param phone    新联系电话（可选）
     * @param role     新角色（可选）
     * @param status   新状态（可选）
     */
    void updateUser(String id, String phone, String role, String status);

    /**
     * 重置用户密码
     *
     * @param id          用户ID
     * @param newPassword 新密码（明文，会加密存储）
     */
    void resetPassword(String id, String newPassword);

    /**
     * 删除用户
     *
     * @param id 用户ID
     */
    void deleteById(String id);

    /**
     * 检查是否为商户最后一位用户
     *
     * @param merchantId 商户ID
     * @param userId      用户ID
     * @return 是否为最后一位用户
     */
    boolean isLastUser(String merchantId, String userId);
}