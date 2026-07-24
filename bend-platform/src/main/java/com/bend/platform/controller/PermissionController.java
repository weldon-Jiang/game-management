package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.PermissionCreateRequest;
import com.bend.platform.entity.MerchantPermission;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.PermissionService;
import com.bend.platform.util.UserContext;
import com.bend.platform.config.MasterModeCondition;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * 商户使用权限(Permission)管理接口（总控侧）
 *
 * <p>管理商户服务期限/配额/功能。与 License(软件授权)解耦。
 * <p>仅平台管理员可操作。
 */
@RestController
@RequestMapping("/api/permissions")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class PermissionController {

    private final PermissionService permissionService;

    /** 为商户创建/激活使用权限 */
    @PostMapping
    public ApiResponse<MerchantPermission> create(@RequestBody PermissionCreateRequest request) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success("创建成功", permissionService.createOrRenew(request));
    }

    /** 续期：自定义到期日期（兜底） */
    @PutMapping("/{id}/renew")
    public ApiResponse<Void> renew(@PathVariable String id, @RequestParam String expireAt) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        LocalDateTime newExpire = LocalDateTime.parse(expireAt, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        permissionService.renew(id, newExpire);
        return ApiResponse.success("续期成功", null);
    }

    /** 续期：按套餐时长（30天/90天/1年），从当前到期日往后加 */
    @PutMapping("/{id}/renew-duration")
    public ApiResponse<Void> renewByDuration(@PathVariable String id, @RequestParam String duration) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        permissionService.renewByDuration(id, duration);
        return ApiResponse.success("续期成功", null);
    }

    /** 停用 */
    @PutMapping("/{id}/suspend")
    public ApiResponse<Void> suspend(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        permissionService.suspend(id);
        return ApiResponse.success("已停用", null);
    }

    /** 启用（解除停用） */
    @PutMapping("/{id}/resume")
    public ApiResponse<Void> resume(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        permissionService.resume(id);
        return ApiResponse.success("已启用", null);
    }

    /** 查询商户的权限 */
    @GetMapping("/merchant/{merchantId}")
    public ApiResponse<MerchantPermission> getByMerchant(@PathVariable String merchantId) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(permissionService.findByMerchantId(merchantId));
    }

    /** 详情 */
    @GetMapping("/{id}")
    public ApiResponse<MerchantPermission> getById(@PathVariable String id) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(permissionService.findById(id));
    }

    /** 分页列表 */
    @GetMapping
    public ApiResponse<IPage<MerchantPermission>> list(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String merchantId,
            @RequestParam(required = false) String status) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(permissionService.page(pageNum, pageSize, merchantId, status));
    }
}
