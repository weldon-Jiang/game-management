package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.VipConfigPageRequest;
import com.bend.platform.dto.VipConfigRequest;
import com.bend.platform.entity.VipConfig;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.VipConfigService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.List;

/**
 * VIP配置控制器（平台级）
 *
 * 功能说明：
 * - 管理VIP套餐配置
 * - 支持多种VIP类型（月卡、季卡、年卡等）
 * - 配置价格、时长、功能权限等
 *
 * 主要功能：
 * - 创建/编辑/删除VIP配置
 * - 查询VIP配置列表
 * - 更新VIP配置状态（启用/禁用）
 */
@RestController
@RequestMapping("/api/vip-configs")
@RequiredArgsConstructor
public class VipConfigController {

    private final VipConfigService vipConfigService;

    /**
     * 创建VIP配置
     *
     * @param request VIP配置请求
     * @return 创建的VIP配置
     */
    @PostMapping
    public ApiResponse<VipConfig> create(@Valid @RequestBody VipConfigRequest request) {
        VipConfig config = vipConfigService.create(
                request.getVipType(),
                request.getVipName(),
                request.getPrice(),
                request.getDurationDays(),
                request.getFeatures(),
                request.getIsDefault()
        );
        return ApiResponse.success("创建成功", config);
    }

    /**
     * 查询启用的VIP配置列表
     *
     * @return VIP配置列表
     */
    @GetMapping
    public ApiResponse<List<VipConfig>> list() {
        List<VipConfig> configs = vipConfigService.findAllActive();
        return ApiResponse.success(configs);
    }

    /**
     * 分页查询VIP配置列表
     *
     * @param request 分页请求参数
     * @return VIP配置分页列表
     */
    @GetMapping("/page")
    public ApiResponse<IPage<VipConfig>> listPage(VipConfigPageRequest request) {
        IPage<VipConfig> page = vipConfigService.findAll(request);
        return ApiResponse.success(page);
    }

    /**
     * 获取VIP配置详情
     *
     * @param id VIP配置ID
     * @return VIP配置信息
     */
    @GetMapping("/{id}")
    public ApiResponse<VipConfig> getById(@PathVariable String id) {
        VipConfig config = vipConfigService.findById(id);
        if (config == null) {
            throw new BusinessException(ResultCode.VipConfig.NOT_FOUND);
        }
        return ApiResponse.success(config);
    }

    /**
     * 更新VIP配置
     *
     * @param id      VIP配置ID
     * @param request 更新后的配置信息
     * @return 操作结果
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(
            @PathVariable String id,
            @Valid @RequestBody VipConfigRequest request) {
        vipConfigService.update(id, request.getVipName(), request.getPrice(),
                request.getDurationDays(), request.getFeatures(), request.getIsDefault());
        return ApiResponse.success("更新成功", null);
    }

    /**
     * 更新VIP配置状态
     *
     * @param id     VIP配置ID
     * @param status 新状态（active/inactive）
     * @return 操作结果
     */
    @PutMapping("/{id}/status")
    public ApiResponse<Void> updateStatus(
            @PathVariable String id,
            @RequestParam String status) {
        vipConfigService.updateStatus(id, status);
        return ApiResponse.success("状态更新成功", null);
    }

    /**
     * 删除VIP配置
     *
     * @param id VIP配置ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        vipConfigService.delete(id);
        return ApiResponse.success("删除成功", null);
    }
}