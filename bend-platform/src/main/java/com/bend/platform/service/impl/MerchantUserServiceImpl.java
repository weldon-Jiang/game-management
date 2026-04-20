package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.MerchantUserPageRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantUser;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.MerchantUserMapper;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.MerchantUserService;
import com.bend.platform.util.AesUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * 商户用户服务实现类
 *
 * 功能说明：
 * - 处理商户用户的登录、注册、密码管理等
 * - 用户属于某个商户，有不同角色权限
 *
 * 用户角色：
 * - owner: 商户所有者
 * - admin: 商户管理员
 * - operator: 操作员
 *
 * 主要功能：
 * - 用户登录验证
 * - 用户注册（创建用户）
 * - 分页查询用户
 * - 根据商户ID查询用户
 * - 更新用户信息
 * - 重置密码
 * - 删除用户
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantUserServiceImpl implements MerchantUserService {

    private final MerchantUserMapper merchantUserMapper;
    private final MerchantMapper merchantMapper;
    private final MerchantService merchantService;
    private final AesUtil aesUtil;

    /**
     * 商户用户登录
     * 1. 查询用户（支持用户名或手机号）
     * 2. 校验商户状态和有效期（仅限非平台管理员）
     * 3. 校验密码
     *
     * @param loginKey 登录名（用户名或手机号）
     * @param password 密码（明文）
     * @return 登录成功的用户实体
     */
    @Override
    public MerchantUser login(String loginKey, String password) {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.and(w -> w
                .eq(MerchantUser::getUsername, loginKey)
                .or()
                .eq(MerchantUser::getPhone, loginKey))
                .eq(MerchantUser::getStatus, "active");

        MerchantUser user = merchantUserMapper.selectOne(wrapper);
        if (user == null) {
            throw new BusinessException(ResultCode.Auth.USERNAME_PASSWORD_ERROR);
        }

        // 校验密码（不校验商户状态，允许过期商户登录后使用激活码续期）
        String storedHash = user.getPasswordHash();
        String decryptedPassword = aesUtil.decrypt(storedHash);

        if (decryptedPassword == null || !decryptedPassword.equals(password)) {
            throw new BusinessException(ResultCode.MerchantUser.PASSWORD_ERROR);
        }

        // 更新最后登录时间
        updateLastLoginTime(user.getId());

        log.info("用户登录成功 - 用户名: {}", loginKey);
        return user;
    }

    /**
     * 注册新用户
     *
     * @param username   用户名
     * @param password   密码（明文，会加密存储）
     * @param merchantId 商户ID
     * @param phone      联系电话
     * @param role       角色 (owner/admin/operator)
     * @return 注册成功的用户实体
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public MerchantUser register(String username, String password, String merchantId, String phone, String role) {
        if (findByUsername(username) != null) {
            throw new BusinessException(ResultCode.MerchantUser.USERNAME_DUPLICATE);
        }

        if (findByPhone(phone) != null) {
            throw new BusinessException(ResultCode.MerchantUser.PHONE_DUPLICATE);
        }

        if (!isValidRole(role)) {
            role = "operator";
        }

        MerchantUser user = new MerchantUser();
        user.setUsername(username);
        user.setPasswordHash(aesUtil.encrypt(password));
        user.setMerchantId(merchantId);
        user.setPhone(phone);
        user.setRole(role);
        user.setStatus("active");

        merchantUserMapper.insert(user);

        log.info("注册用户成功 - 用户名: {}, 商户ID: {}", username, merchantId);
        return user;
    }

    @Override
    public MerchantUser findById(String id) {
        return merchantUserMapper.selectById(id);
    }

    @Override
    public MerchantUser findByUsername(String username) {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantUser::getUsername, username);
        return merchantUserMapper.selectOne(wrapper);
    }

    @Override
    public MerchantUser findByPhone(String phone) {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantUser::getPhone, phone);
        return merchantUserMapper.selectOne(wrapper);
    }

    @Override
    public IPage<MerchantUser> findByMerchantId(String merchantId, MerchantUserPageRequest request) {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(MerchantUser::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(MerchantUser::getCreatedAt);

        Page<MerchantUser> page = new Page<>(request.getPageNum(), request.getPageSize());
        return merchantUserMapper.selectPage(page, wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateUser(String id, String phone, String role, String status) {
        MerchantUser user = merchantUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        if (phone != null) {
            user.setPhone(phone);
        }
        if (role != null && isValidRole(role)) {
            user.setRole(role);
        }
        if (status != null) {
            user.setStatus(status);
        }

        merchantUserMapper.updateById(user);
        log.info("更新用户信息 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void resetPassword(String id, String newPassword) {
        MerchantUser user = merchantUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        user.setPasswordHash(aesUtil.encrypt(newPassword));
        merchantUserMapper.updateById(user);
        log.info("重置用户密码 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteById(String id) {
        MerchantUser user = merchantUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        if (isLastUser(user.getMerchantId(), id)) {
            throw new BusinessException(ResultCode.MerchantUser.LAST_USER_CANNOT_DELETE);
        }

        merchantUserMapper.deleteById(id);
        log.info("删除用户 - ID: {}", id);
    }

    @Override
    public boolean isLastUser(String merchantId, String userId) {
        LambdaQueryWrapper<MerchantUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantUser::getMerchantId, merchantId);
        long count = merchantUserMapper.selectCount(wrapper);
        return count <= 1;
    }

    private void updateLastLoginTime(String userId) {
        LambdaUpdateWrapper<MerchantUser> wrapper = new LambdaUpdateWrapper<>();
        wrapper.eq(MerchantUser::getId, userId)
               .set(MerchantUser::getLastLoginAt, LocalDateTime.now());
        merchantUserMapper.update(null, wrapper);
    }

    private boolean isValidRole(String role) {
        return "owner".equals(role) || "admin".equals(role) || "operator".equals(role) || "platform_admin".equals(role);
    }
}