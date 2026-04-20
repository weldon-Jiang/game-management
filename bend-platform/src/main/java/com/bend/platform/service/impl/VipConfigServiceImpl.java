package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.VipConfigPageRequest;
import com.bend.platform.entity.VipConfig;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.VipConfigMapper;
import com.bend.platform.service.VipConfigService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.*;

/**
 * VIP配置服务实现类（平台级）
 *
 * 功能说明：
 * - 管理VIP套餐配置
 * - 支持多种VIP类型和时长
 *
 * VIP类型：
 * - monthly: 月卡
 * - quarterly: 季卡
 * - yearly: 年卡
 *
 * 主要功能：
 * - 创建VIP配置
 * - 查询所有VIP配置
 * - 分页查询VIP配置
 * - 更新VIP配置
 * - 删除VIP配置
 * - 发布/取消发布VIP配置
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VipConfigServiceImpl implements VipConfigService {

    private static final Map<String, Integer> VIP_TYPE_ORDER;
    static {
        Map<String, Integer> map = new HashMap<>();
        map.put("monthly", 1);
        map.put("quarterly", 2);
        map.put("yearly", 3);
        VIP_TYPE_ORDER = Collections.unmodifiableMap(map);
    }

    private final VipConfigMapper vipConfigMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public VipConfig create(String vipType, String vipName, BigDecimal price, Integer durationDays, String features, Boolean isDefault) {
        LambdaQueryWrapper<VipConfig> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(VipConfig::getVipName, vipName);
        if (vipConfigMapper.selectCount(wrapper) > 0) {
            throw new BusinessException(ResultCode.VipConfig.NAME_DUPLICATE);
        }

        if (Boolean.TRUE.equals(isDefault)) {
            clearDefault();
        }

        VipConfig config = new VipConfig();
        config.setVipType(vipType);
        config.setVipName(vipName);
        config.setPrice(price);
        config.setDurationDays(durationDays);
        config.setFeatures(features);
        config.setIsDefault(isDefault);
        config.setStatus("active");
        config.setSortOrder(VIP_TYPE_ORDER.getOrDefault(vipType, 99));

        vipConfigMapper.insert(config);
        log.info("创建VIP配置成功 - ID: {}, 套餐名: {}", config.getId(), vipName);
        return config;
    }

    @Override
    public VipConfig findById(String id) {
        return vipConfigMapper.selectById(id);
    }

    @Override
    public VipConfig findByVipType(String vipType) {
        LambdaQueryWrapper<VipConfig> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(VipConfig::getVipType, vipType)
               .eq(VipConfig::getStatus, "active");
        return vipConfigMapper.selectOne(wrapper);
    }

    @Override
    public List<VipConfig> findAllActive() {
        LambdaQueryWrapper<VipConfig> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(VipConfig::getStatus, "active");
        List<VipConfig> configs = vipConfigMapper.selectList(wrapper);
        Collections.sort(configs, new Comparator<VipConfig>() {
            @Override
            public int compare(VipConfig c1, VipConfig c2) {
                int order1 = VIP_TYPE_ORDER.getOrDefault(c1.getVipType(), 99);
                int order2 = VIP_TYPE_ORDER.getOrDefault(c2.getVipType(), 99);
                return Integer.compare(order1, order2);
            }
        });
        return configs;
    }

    @Override
    public IPage<VipConfig> findAll(VipConfigPageRequest request) {
        LambdaQueryWrapper<VipConfig> wrapper = new LambdaQueryWrapper<>();
        Page<VipConfig> page = new Page<>(request.getPageNum(), request.getPageSize());
        IPage<VipConfig> result = vipConfigMapper.selectPage(page, wrapper);
        List<VipConfig> records = result.getRecords();
        Collections.sort(records, new Comparator<VipConfig>() {
            @Override
            public int compare(VipConfig c1, VipConfig c2) {
                int order1 = VIP_TYPE_ORDER.getOrDefault(c1.getVipType(), 99);
                int order2 = VIP_TYPE_ORDER.getOrDefault(c2.getVipType(), 99);
                return Integer.compare(order1, order2);
            }
        });
        result.setRecords(records);
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String id, String vipName, BigDecimal price, Integer durationDays, String features, Boolean isDefault) {
        VipConfig config = vipConfigMapper.selectById(id);
        if (config == null) {
            throw new BusinessException(ResultCode.VipConfig.NOT_FOUND);
        }

        if (vipName != null && !vipName.equals(config.getVipName())) {
            LambdaQueryWrapper<VipConfig> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(VipConfig::getVipName, vipName)
                   .ne(VipConfig::getId, id);
            if (vipConfigMapper.selectCount(wrapper) > 0) {
                throw new BusinessException(ResultCode.VipConfig.NAME_DUPLICATE);
            }
        }

        if (Boolean.TRUE.equals(isDefault)) {
            clearDefault();
        }

        if (vipName != null) config.setVipName(vipName);
        if (price != null) config.setPrice(price);
        if (durationDays != null) config.setDurationDays(durationDays);
        if (features != null) config.setFeatures(features);
        if (isDefault != null) config.setIsDefault(isDefault);

        vipConfigMapper.updateById(config);
        log.info("更新VIP配置 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateStatus(String id, String status) {
        VipConfig config = vipConfigMapper.selectById(id);
        if (config == null) {
            throw new BusinessException(ResultCode.VipConfig.NOT_FOUND);
        }

        config.setStatus(status);
        vipConfigMapper.updateById(config);
        log.info("更新VIP配置状态 - ID: {}, 新状态: {}", id, status);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        VipConfig config = vipConfigMapper.selectById(id);
        if (config == null) {
            throw new BusinessException(ResultCode.VipConfig.NOT_FOUND);
        }

        if (Boolean.TRUE.equals(config.getIsDefault())) {
            throw new BusinessException(ResultCode.VipConfig.CANNOT_DELETE_DEFAULT);
        }

        vipConfigMapper.deleteById(id);
        log.info("删除VIP配置 - ID: {}", id);
    }

    private void clearDefault() {
        LambdaQueryWrapper<VipConfig> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(VipConfig::getIsDefault, true);
        VipConfig existing = vipConfigMapper.selectOne(wrapper);
        if (existing != null) {
            existing.setIsDefault(false);
            vipConfigMapper.updateById(existing);
        }
    }
}