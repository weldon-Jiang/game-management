package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.MerchantPageRequest;
import com.bend.platform.entity.Merchant;

/**
 * 商户服务接口
 * 定义商户相关的业务操作
 */
public interface MerchantService {

    /**
     * 创建商户
     *
     * @param name  商户名称
     * @param phone 商户联系电话
     * @return 创建的商户实体
     */
    Merchant createMerchant(String name, String phone);

    /**
     * 根据ID查询商户
     *
     * @param id 商户ID
     * @return 商户实体，不存在返回null
     */
    Merchant findById(String id);

    /**
     * 分页查询所有商户
     *
     * @param request 分页请求参数
     * @return 分页结果
     */
    IPage<Merchant> findAll(MerchantPageRequest request);

    /**
     * 获取所有商户（不分页，用于下拉选择）
     *
     * @return 所有商户列表
     */
    java.util.List<Merchant> findAllSimple();

    /**
     * 更新商户状态
     *
     * @param id     商户ID
     * @param status 新状态 (active/expired/suspended)
     */
    void updateStatus(String id, String status);

    /**
     * 删除商户
     *
     * @param id 商户ID
     */
    void deleteById(String id);

    /**
     * 校验商户是否有效（状态正常且未过期）
     *
     * @param merchantId 商户ID
     * @throws BusinessException 如果商户无效
     */
    void validateMerchantActive(String merchantId);
}