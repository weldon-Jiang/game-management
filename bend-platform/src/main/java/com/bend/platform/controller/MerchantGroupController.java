package com.bend.platform.controller;

import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.service.MerchantGroupService;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * VIP分组管理控制器
 */
@RestController
@RequestMapping("/api/merchant-groups")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class MerchantGroupController {

    private final MerchantGroupService merchantGroupService;

    @GetMapping
    public ApiResponse<List<MerchantGroup>> listAll() {
        return ApiResponse.success(merchantGroupService.listAll());
    }

    @GetMapping("/{id}")
    public ApiResponse<MerchantGroup> getById(@PathVariable String id) {
        return ApiResponse.success(merchantGroupService.findById(id));
    }

    @GetMapping("/by-merchant/{merchantId}")
    public ApiResponse<MerchantGroup> getByMerchantId(@PathVariable String merchantId) {
        return ApiResponse.success(merchantGroupService.findByMerchantId(merchantId));
    }

    @PostMapping
    public ApiResponse<MerchantGroup> create(@RequestBody MerchantGroup group) {
        return ApiResponse.success("分组创建成功", merchantGroupService.create(group));
    }

    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @RequestBody MerchantGroup group) {
        merchantGroupService.update(id, group);
        return ApiResponse.success("分组更新成功", null);
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        merchantGroupService.delete(id);
        return ApiResponse.success("分组删除成功", null);
    }
}
