package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.MerchantCreateRequest;
import com.bend.platform.dto.MerchantPageRequest;
import com.bend.platform.dto.MerchantUpdateRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.MerchantService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 商户控制器
 *
 * 功能说明：
 * - 管理商户信息
 * - 商户是系统的顶级组织单元
 *
 * 主要功能：
 * - 创建商户
 * - 查询商户列表（分页）
 * - 获取商户详情
 * - 更新商户状态
 * - 删除商户
 */
@RestController
@RequestMapping("/api/merchants")
@RequiredArgsConstructor
public class MerchantController {

    private final MerchantService merchantService;

    /**
     * 创建商户
     *
     * @param name     商户名称
     * @param phone    商户联系电话
     * @param isSystem 是否为系统商户
     * @return 创建的商户信息
     */
    @PostMapping
    public ApiResponse<Merchant> create(@RequestBody MerchantCreateRequest request) {
        if (!UserContext.hasManagementPermission()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        Merchant merchant = merchantService.createMerchant(request.getName(), request.getPhone(), request.getIsSystem());
        return ApiResponse.success("商户创建成功", merchant);
    }

    /**
     * 更新商户信息
     *
     * @param id       商户ID
     * @param name     商户名称
     * @param phone    商户联系电话
     * @param isSystem 是否为系统商户
     * @return 操作结果
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @RequestBody MerchantUpdateRequest request) {
        if (!UserContext.hasManagementPermission()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        merchantService.updateMerchant(id, request.getName(), request.getPhone(), request.getIsSystem());
        return ApiResponse.success("商户更新成功", null);
    }

    /**
     * 获取商户详情
     *
     * @param id 商户ID
     * @return 商户信息
     */
    @GetMapping("/{id}")
    public ApiResponse<Merchant> getById(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin() && !id.equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        Merchant merchant = merchantService.findById(id);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }
        return ApiResponse.success(merchant);
    }

    /**
     * 分页查询商户列表
     *
     * @param request 分页请求参数
     * @return 商户分页列表
     */
    @GetMapping
    public ApiResponse<IPage<Merchant>> list(MerchantPageRequest request) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        IPage<Merchant> page = merchantService.findAll(request);
        return ApiResponse.success(page);
    }

    /**
     * 获取所有商户（下拉框用）
     *
     * @return 所有商户列表
     */
    @GetMapping("/all")
    public ApiResponse<List<Merchant>> listAll() {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        List<Merchant> merchants = merchantService.findAllSimple();
        return ApiResponse.success(merchants);
    }

    /**
     * 更新商户状态
     *
     * @param id     商户ID
     * @param status 新状态（active/inactive）
     * @return 操作结果
     */
    @PutMapping("/{id}/status")
    public ApiResponse<Void> updateStatus(@PathVariable String id, @RequestParam String status) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        merchantService.updateStatus(id, status);
        return ApiResponse.success("状态更新成功", null);
    }

    /**
     * 删除商户
     *
     * @param id 商户ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        merchantService.deleteById(id);
        return ApiResponse.success("删除成功", null);
    }
}