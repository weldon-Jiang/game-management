package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.MerchantUserItemDto;
import com.bend.platform.dto.MerchantUserPageRequest;
import com.bend.platform.dto.MerchantUserCreateRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantUser;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.MerchantUserService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 商户用户控制器
 *
 * 功能说明：
 * - 处理商户用户的CRUD操作
 * - 用户属于某个商户，有不同角色权限
 *
 * 用户角色：
 * - owner: 商户所有者
 * - admin: 商户管理员
 * - operator: 操作员
 *
 * 主要功能：
 * - 创建/编辑/删除商户用户
 * - 查询用户列表（分页）
 * - 重置用户密码
 * - 平台管理员可管理所有用户
 * - 商户管理员可管理本商户用户
 */
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class MerchantUserController {

    private final MerchantUserService merchantUserService;
    private final MerchantService merchantService;

    /**
     * 分页查询用户列表
     * 平台管理员返回所有用户，商户用户返回本商户用户
     *
     * @param request 分页请求参数
     * @return 用户分页列表
     */
    @GetMapping
    public ApiResponse<IPage<MerchantUserItemDto>> list(MerchantUserPageRequest request) {
        String merchantId = UserContext.getMerchantId();

        if (UserContext.isPlatformAdmin()) {
            merchantId = null;
        }

        IPage<MerchantUser> page = merchantUserService.findByMerchantId(merchantId, request);

        List<Merchant> merchants = merchantService.findAllSimple();
        Map<String, String> merchantNameMap = merchants.stream()
                .collect(Collectors.toMap(Merchant::getId, Merchant::getName));

        IPage<MerchantUserItemDto> dtoPage = page.convert(item -> {
            MerchantUserItemDto dto = new MerchantUserItemDto();
            BeanUtils.copyProperties(item, dto);
            dto.setMerchantName(merchantNameMap.get(item.getMerchantId()));
            return dto;
        });

        return ApiResponse.success(dtoPage);
    }

    /**
     * 创建商户用户
     * 平台管理员可指定商户，非平台管理员自动使用当前用户商户
     *
     * @param request 用户信息
     * @return 创建的用户
     */
    @PostMapping
    public ApiResponse<MerchantUser> create(@Valid @RequestBody MerchantUserCreateRequest request) {
        String currentMerchantId = UserContext.getMerchantId();

        String finalMerchantId;
        if (UserContext.isPlatformAdmin()) {
            finalMerchantId = request.getMerchantId();
        } else {
            finalMerchantId = currentMerchantId;
        }

        MerchantUser user = merchantUserService.register(
                request.getUsername(),
                request.getPassword(),
                finalMerchantId,
                request.getPhone(),
                request.getRole()
        );
        return ApiResponse.success("创建成功", user);
    }

    /**
     * 获取用户详情
     *
     * @param id 用户ID
     * @return 用户信息
     */
    @GetMapping("/{id}")
    public ApiResponse<MerchantUser> getById(@PathVariable String id) {
        MerchantUser user = merchantUserService.findById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !user.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        return ApiResponse.success(user);
    }

    /**
     * 更新用户信息
     * 只有平台管理员可以修改用户角色
     *
     * @param id     用户ID
     * @param phone  手机号（可选）
     * @param role   角色（可选，仅平台管理员可修改）
     * @param status 状态（可选）
     * @return 操作结果
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(
            @PathVariable String id,
            @RequestParam(required = false) String phone,
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String status) {
        MerchantUser user = merchantUserService.findById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !user.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        if (role != null && !UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        merchantUserService.updateUser(id, phone, role, status);
        return ApiResponse.success("更新成功", null);
    }

    /**
     * 重置用户密码
     *
     * @param id          用户ID
     * @param newPassword 新密码
     * @return 操作结果
     */
    @PutMapping("/{id}/password")
    public ApiResponse<Void> resetPassword(
            @PathVariable String id,
            @RequestParam String newPassword) {
        MerchantUser user = merchantUserService.findById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !user.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        merchantUserService.resetPassword(id, newPassword);
        return ApiResponse.success("密码重置成功", null);
    }

    /**
     * 删除用户
     *
     * @param id 用户ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        MerchantUser user = merchantUserService.findById(id);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !user.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        merchantUserService.deleteById(id);
        return ApiResponse.success("删除成功", null);
    }
}