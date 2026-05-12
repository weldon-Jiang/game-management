package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * VIP分组管理控制器
 *
 * 功能说明：
 * - VIP分组是商户的定价等级配置
 * - 根据商户累计消费金额确定VIP等级
 * - 不同VIP等级享受不同的订阅价格折扣
 *
 * 价格类型：
 * - window_original_price / window_discount_price: 流媒体账号包月原价/折后价
 * - account_original_price / account_discount_price: 游戏账号包月原价/折后价
 * - host_original_price / host_discount_price: Xbox主机包月原价/折后价
 * - full_original_price / full_discount_price: 全功能包月原价/折后价
 * - points_original_price / points_discount_price: 点数原价/折后价
 *
 * 权限说明：
 * - 查询接口：所有登录用户可用
 * - 创建/修改/删除接口：仅平台管理员可用
 */
@Slf4j
@RestController
@RequestMapping("/api/merchant-groups")
@RequiredArgsConstructor
public class MerchantGroupController {

    private final MerchantGroupMapper merchantGroupMapper;
    private final MerchantMapper merchantMapper;

    /**
     * 获取所有VIP分组列表
     *
     * @return VIP分组列表（包含各订阅类型的原价和折后价）
     */
    @GetMapping
    public ApiResponse<List<MerchantGroup>> listAll() {
        List<MerchantGroup> groups = merchantGroupMapper.selectList(null);
        return ApiResponse.success(groups);
    }

    /**
     * 根据ID获取VIP分组详情
     *
     * @param id 分组ID
     * @return 分组详情
     */
    @GetMapping("/{id}")
    public ApiResponse<MerchantGroup> getById(@PathVariable String id) {
        MerchantGroup group = merchantGroupMapper.selectById(id);
        if (group == null) {
            throw new BusinessException(ResultCode.MerchantGroup.NOT_FOUND);
        }
        return ApiResponse.success(group);
    }

    /**
     * 根据商户ID获取其VIP分组信息
     *
     * @param merchantId 商户ID
     * @return 该商户对应的VIP分组配置
     *
     * 说明：
     * - 根据商户的VIP等级匹配对应的分组
     * - VIP等级为0的商户返回null
     */
    @GetMapping("/by-merchant/{merchantId}")
    public ApiResponse<MerchantGroup> getByMerchantId(@PathVariable String merchantId) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        int merchantVipLevel = merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;
        if (merchantVipLevel == 0) {
            return ApiResponse.success(null);
        }

        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getVipLevel, merchantVipLevel)
               .eq(MerchantGroup::getStatus, "active")
               .last("LIMIT 1");
        MerchantGroup group = merchantGroupMapper.selectOne(wrapper);
        return ApiResponse.success(group);
    }

    /**
     * 创建VIP分组
     *
     * @param group 分组信息
     * @return 创建的分组
     *
     * @requires 平台管理员权限
     */
    @PostMapping
    public ApiResponse<MerchantGroup> create(@RequestBody MerchantGroup group) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        merchantGroupMapper.insert(group);
        return ApiResponse.success("分组创建成功", group);
    }

    /**
     * 更新VIP分组
     *
     * @param id    分组ID
     * @param group 更新后的分组信息
     * @return 操作结果
     *
     * @requires 平台管理员权限
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @RequestBody MerchantGroup group) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        group.setId(id);
        merchantGroupMapper.updateById(group);
        return ApiResponse.success("分组更新成功", null);
    }

    /**
     * 删除VIP分组
     *
     * @param id 分组ID
     * @return 操作结果
     *
     * 说明：
     * - 只能从最高VIP等级开始删除，不能删除中间等级
     * - 如果有商户在该等级，不允许删除
     * - VIP0不允许删除
     *
     * @requires 平台管理员权限
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        MerchantGroup group = merchantGroupMapper.selectById(id);
        if (group == null) {
            throw new BusinessException(ResultCode.MerchantGroup.NOT_FOUND);
        }

        // VIP0不允许删除
        if (group.getVipLevel() == 0) {
            throw new BusinessException(ResultCode.MerchantGroup.CANNOT_DELETE_VIP0);
        }

        // 检查是否是最高等级
        LambdaQueryWrapper<MerchantGroup> maxWrapper = new LambdaQueryWrapper<>();
        maxWrapper.orderByDesc(MerchantGroup::getVipLevel).last("LIMIT 1");
        MerchantGroup maxGroup = merchantGroupMapper.selectOne(maxWrapper);
        if (maxGroup == null || !maxGroup.getId().equals(group.getId())) {
            throw new BusinessException(ResultCode.MerchantGroup.NOT_HIGHEST_LEVEL);
        }

        // 检查是否有商户在该等级
        long merchantCount = merchantMapper.selectCount(
                new LambdaQueryWrapper<Merchant>().eq(Merchant::getVipLevel, group.getVipLevel()));
        if (merchantCount > 0) {
            throw new BusinessException(ResultCode.MerchantGroup.HAS_MERCHANT);
        }

        merchantGroupMapper.deleteById(id);
        log.info("删除VIP分组成功 - ID: {}, VIP等级: {}", id, group.getVipLevel());
        return ApiResponse.success("分组删除成功", null);
    }
}
