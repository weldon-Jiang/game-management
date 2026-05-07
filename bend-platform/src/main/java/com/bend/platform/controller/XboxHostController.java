package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.XboxHostItemDto;
import com.bend.platform.dto.XboxHostPageRequest;
import com.bend.platform.dto.XboxHostRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.XboxHostService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.BeanUtils;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Xbox主机控制器
 *
 * 功能说明：
 * - 管理Xbox主机设备
 * - 提供主机与流媒体账号的绑定关系
 *
 * 主要功能：
 * - 创建/编辑/删除Xbox主机
 * - 查询主机列表
 * - 绑定/解绑流媒体账号
 * - 获取主机可用的流媒体账号列表
 * - 平台管理员可管理所有商户的主机
 * - 商户用户只能管理本商户的主机
 */
@RestController
@RequestMapping("/api/xbox-hosts")
@RequiredArgsConstructor
public class XboxHostController {

    private final XboxHostService xboxHostService;
    private final MerchantService merchantService;

    /**
     * 创建Xbox主机
     * 平台管理员可指定商户，非平台管理员自动使用当前用户商户
     *
     * @param request 主机信息
     * @return 创建的主机
     */
    @PostMapping
    public ApiResponse<XboxHost> create(@Valid @RequestBody XboxHostRequest request) {
        String merchantId;
        if (UserContext.isPlatformAdmin()) {
            merchantId = request.getMerchantId();
        } else {
            merchantId = UserContext.getMerchantId();
        }

        XboxHost host = xboxHostService.create(merchantId, request.getXboxId(), request.getName(), request.getIpAddress());
        return ApiResponse.success("创建成功", host);
    }

    /**
     * 查询Xbox主机列表
     * 平台管理员返回所有主机，商户用户返回本商户主机
     * 平台管理员可指定merchantId查询特定商户的主机
     *
     * @return 主机列表
     */
    @GetMapping
    public ApiResponse<List<XboxHost>> list(XboxHostPageRequest request) {
        String merchantId;
        if (UserContext.isPlatformAdmin()) {
            merchantId = StringUtils.isNotBlank(request.getMerchantId()) ? request.getMerchantId() : null;
        } else {
            merchantId = UserContext.getMerchantId();
        }
        List<XboxHost> hosts = xboxHostService.findAllByMerchantId(merchantId);
        return ApiResponse.success(hosts);
    }

    /**
     * 分页查询Xbox主机列表
     * 平台管理员可指定merchantId查询特定商户的主机
     *
     * @param request 分页请求参数
     * @return 主机分页列表
     */
    @GetMapping("/page")
    public ApiResponse<IPage<XboxHostItemDto>> listPage(XboxHostPageRequest request) {
        String merchantId;
        if (UserContext.isPlatformAdmin()) {
            merchantId = StringUtils.isNotBlank(request.getMerchantId()) ? request.getMerchantId() : null;
        } else {
            merchantId = UserContext.getMerchantId();
        }
        IPage<XboxHost> page = xboxHostService.findByMerchantId(merchantId, request);

        List<Merchant> merchants = merchantService.findAllSimple();
        Map<String, String> merchantNameMap = merchants.stream()
                .collect(Collectors.toMap(Merchant::getId, Merchant::getName));

        IPage<XboxHostItemDto> dtoPage = page.convert(item -> {
            XboxHostItemDto dto = new XboxHostItemDto();
            BeanUtils.copyProperties(item, dto);
            dto.setMerchantName(merchantNameMap.get(item.getMerchantId()));
            return dto;
        });

        return ApiResponse.success(dtoPage);
    }

    /**
     * 获取主机详情
     *
     * @param id 主机ID
     * @return 主机信息
     */
    @GetMapping("/{id}")
    public ApiResponse<XboxHost> getById(@PathVariable String id) {
        XboxHost host = xboxHostService.findById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !host.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        return ApiResponse.success(host);
    }

    /**
     * 获取主机可用的流媒体账号列表
     *
     * @param id 主机ID
     * @return 可用的流媒体账号ID列表
     */
    @GetMapping("/{id}/available-streaming-accounts")
    public ApiResponse<List<String>> getAvailableStreamingAccounts(@PathVariable String id) {
        XboxHost host = xboxHostService.findById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !host.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        List<String> availableAccounts = xboxHostService.getAvailableStreamingAccounts(id);
        return ApiResponse.success(availableAccounts);
    }

    /**
     * 更新主机信息
     *
     * @param id      主机ID
     * @param request 更新后的主机信息
     * @return 操作结果
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @Valid @RequestBody XboxHostRequest request) {
        XboxHost host = xboxHostService.findById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !host.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        xboxHostService.update(id, request.getName(), request.getIpAddress());
        return ApiResponse.success("更新成功", null);
    }

    /**
     * 绑定流媒体账号到主机
     *
     * @param id                 主机ID
     * @param streamingAccountId  流媒体账号ID
     * @param gamertag            Xbox玩家标签（可选）
     * @return 操作结果
     */
    @PutMapping("/{id}/bind")
    public ApiResponse<Void> bindStreaming(
            @PathVariable String id,
            @RequestParam String streamingAccountId,
            @RequestParam(required = false) String gamertag) {
        XboxHost host = xboxHostService.findById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !host.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        xboxHostService.bindStreamingAccount(id, streamingAccountId, gamertag);
        return ApiResponse.success("绑定成功", null);
    }

    /**
     * 解绑流媒体账号
     *
     * @param id 主机ID
     * @return 操作结果
     */
    @PutMapping("/{id}/unbind")
    public ApiResponse<Void> unbindStreaming(@PathVariable String id) {
        XboxHost host = xboxHostService.findById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !host.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        xboxHostService.unbindStreamingAccount(id);
        return ApiResponse.success("解绑成功", null);
    }

    /**
     * 删除主机
     *
     * @param id 主机ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        XboxHost host = xboxHostService.findById(id);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !host.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        xboxHostService.delete(id);
        return ApiResponse.success("删除成功", null);
    }
}