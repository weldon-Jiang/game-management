package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;

/**
 * 商户分组管理控制器
 */
@RestController
@RequestMapping("/api/merchant-groups")
@RequiredArgsConstructor
public class MerchantGroupController {

    private final MerchantGroupMapper merchantGroupMapper;
    private final MerchantMapper merchantMapper;

    @GetMapping
    public ApiResponse<List<MerchantGroup>> listAll() {
        List<MerchantGroup> groups = merchantGroupMapper.selectList(null);
        return ApiResponse.success(groups);
    }

    @GetMapping("/{id}")
    public ApiResponse<MerchantGroup> getById(@PathVariable String id) {
        MerchantGroup group = merchantGroupMapper.selectById(id);
        if (group == null) {
            throw new BusinessException(ResultCode.MerchantGroup.NOT_FOUND);
        }
        return ApiResponse.success(group);
    }

    @PostMapping
    public ApiResponse<MerchantGroup> create(@RequestBody MerchantGroup group) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        merchantGroupMapper.insert(group);
        return ApiResponse.success("分组创建成功", group);
    }

    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @RequestBody MerchantGroup group) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        group.setId(id);
        merchantGroupMapper.updateById(group);
        return ApiResponse.success("分组更新成功", null);
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        long merchantCount = merchantMapper.selectCount(
                new LambdaQueryWrapper<Merchant>().eq(Merchant::getGroupId, id));
        if (merchantCount > 0) {
            throw new BusinessException(ResultCode.MerchantGroup.HAS_MERCHANT);
        }

        merchantGroupMapper.deleteById(id);
        return ApiResponse.success("分组删除成功", null);
    }
}
