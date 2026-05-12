package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.MerchantPageRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.MerchantService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 商户服务实现类
 *
 * 功能说明：
 * - 管理商户的CRUD操作
 * - 商户是系统的顶级组织单元
 *
 * 主要功能：
 * - 创建商户
 * - 分页查询商户
 * - 查询所有商户
 * - 根据ID查询商户
 * - 更新商户状态
 * - 删除商户
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantServiceImpl implements MerchantService {

    private final MerchantMapper merchantMapper;

    /**
     * 创建商户
     * 新商户默认状态为active
     *
     * @param name  商户名称
     * @param phone 商户联系电话
     * @return 创建的商户实体
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Merchant createMerchant(String name, String phone, Boolean isSystem) {
        LambdaQueryWrapper<Merchant> phoneWrapper = new LambdaQueryWrapper<>();
        phoneWrapper.eq(Merchant::getPhone, phone);
        if (merchantMapper.selectCount(phoneWrapper) > 0) {
            throw new BusinessException(ResultCode.Merchant.PHONE_DUPLICATE);
        }

        if (isSystem != null && isSystem) {
            switchSystemMerchant(null);
        }

        Merchant merchant = new Merchant();
        merchant.setPhone(phone);
        merchant.setName(name);
        merchant.setStatus("active");
        merchant.setIsSystem(isSystem != null && isSystem);
        merchantMapper.insert(merchant);

        log.info("创建商户成功 - ID: {}, 名称: {}, 系统商户: {}", merchant.getId(), name, merchant.getIsSystem());
        return merchant;
    }

    /**
     * 根据ID查询商户
     *
     * @param id 商户ID
     * @return 商户实体，不存在返回null
     */
    @Override
    public Merchant findById(String id) {
        return merchantMapper.selectById(id);
    }

    /**
     * 分页查询所有商户
     *
     * @param pageNum  页码，从1开始
     * @param pageSize 每页记录数
     * @return 分页结果
     */
    @Override
    public IPage<Merchant> findAll(MerchantPageRequest request) {
        LambdaQueryWrapper<Merchant> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(Merchant::getCreatedTime);
        Page<Merchant> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return merchantMapper.selectPage(page, wrapper);
    }

    /**
     * 获取所有商户（不分页）
     *
     * @return 所有商户列表
     */
    @Override
    public List<Merchant> findAllSimple() {
        LambdaQueryWrapper<Merchant> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByAsc(Merchant::getName);
        return merchantMapper.selectList(wrapper);
    }

    /**
     * 更新商户状态
     *
     * @param id     商户ID
     * @param status 新状态 (active/expired/suspended)
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateStatus(String id, String status) {
        Merchant merchant = merchantMapper.selectById(id);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        if (!isValidStatus(status)) {
            throw new BusinessException(ResultCode.Merchant.STATUS_INVALID);
        }

        merchant.setStatus(status);
        merchantMapper.updateById(merchant);
        log.info("更新商户状态 - ID: {}, 新状态: {}", id, status);
    }

    /**
     * 删除商户
     *
     * @param id 商户ID
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteById(String id) {
        Merchant merchant = merchantMapper.selectById(id);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        merchantMapper.deleteById(id);
        log.info("删除商户 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateMerchant(String id, String name, String phone, Boolean isSystem) {
        Merchant merchant = merchantMapper.selectById(id);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        LambdaQueryWrapper<Merchant> phoneWrapper = new LambdaQueryWrapper<>();
        phoneWrapper.eq(Merchant::getPhone, phone)
                    .ne(Merchant::getId, id);
        if (merchantMapper.selectCount(phoneWrapper) > 0) {
            throw new BusinessException(ResultCode.Merchant.PHONE_DUPLICATE);
        }

        if (isSystem != null && isSystem && !Boolean.TRUE.equals(merchant.getIsSystem())) {
            switchSystemMerchant(id);
        }

        merchant.setName(name);
        merchant.setPhone(phone);
        merchant.setIsSystem(isSystem != null && isSystem);
        merchantMapper.updateById(merchant);

        log.info("更新商户 - ID: {}, 名称: {}, 系统商户: {}", id, name, merchant.getIsSystem());
    }

    /**
     * 校验商户是否有效（状态正常）
     *
     * @param merchantId 商户ID
     * @throws BusinessException 如果商户无效
     */
    @Override
    public void validateMerchantActive(String merchantId) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        if (!"active".equals(merchant.getStatus())) {
            throw new BusinessException(ResultCode.Merchant.STATUS_INVALID, "商户状态无效，请联系管理员");
        }
    }

    /**
     * 验证商户状态值是否有效
     *
     * @param status 状态值
     * @return 是否有效
     */
    private boolean isValidStatus(String status) {
        return "active".equals(status) || "expired".equals(status) || "suspended".equals(status);
    }

    /**
     * 切换系统商户
     * 将其他系统商户设置为非系统商户，确保只有一个系统商户
     *
     * @param excludeMerchantId 排除的商户ID（更新时传入自身ID）
     */
    private void switchSystemMerchant(String excludeMerchantId) {
        LambdaQueryWrapper<Merchant> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Merchant::getIsSystem, true);
        if (excludeMerchantId != null) {
            wrapper.ne(Merchant::getId, excludeMerchantId);
        }
        List<Merchant> systemMerchants = merchantMapper.selectList(wrapper);

        for (Merchant m : systemMerchants) {
            m.setIsSystem(false);
            merchantMapper.updateById(m);
            log.info("切换系统商户 - 原系统商户: {}, 新系统商户ID: {}", m.getId(), excludeMerchantId);
        }
    }
}
