package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.VipConfigPageRequest;
import com.bend.platform.entity.VipConfig;
import java.math.BigDecimal;
import java.util.List;

/**
 * VIP配置服务接口（平台级）
 */
public interface VipConfigService {

    /**
     * 创建VIP配置
     *
     * @param vipType      VIP类型 (monthly/yearly/quarterly)
     * @param vipName      VIP名称
     * @param price        价格
     * @param durationDays 有效期天数
     * @param features     功能描述JSON
     * @param isDefault    是否默认
     * @return 创建的配置
     */
    VipConfig create(String vipType, String vipName, BigDecimal price, Integer durationDays, String features, Boolean isDefault);

    /**
     * 根据ID查询
     */
    VipConfig findById(String id);

    /**
     * 根据VIP类型查询
     */
    VipConfig findByVipType(String vipType);

    /**
     * 查询所有可用的VIP配置
     */
    List<VipConfig> findAllActive();

    /**
     * 分页查询VIP配置
     *
     * @param request 分页请求参数
     * @return VIP配置分页列表
     */
    IPage<VipConfig> findAll(VipConfigPageRequest request);

    /**
     * 更新VIP配置
     */
    void update(String id, String vipName, BigDecimal price, Integer durationDays, String features, Boolean isDefault);

    /**
     * 更新配置状态
     */
    void updateStatus(String id, String status);

    /**
     * 删除VIP配置
     */
    void delete(String id);
}