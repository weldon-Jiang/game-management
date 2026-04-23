package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.StreamingAccountItemDto;
import com.bend.platform.dto.StreamingAccountPageRequest;
import com.bend.platform.dto.StreamingAccountRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.StreamingAccountLoginRecordService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 流媒体账号控制器
 *
 * 功能说明：
 * - 管理Xbox流媒体账号的CRUD操作
 * - 支持多个流媒体平台账号的管理
 * - 提供账号与Xbox主机的绑定关系管理
 *
 * 主要功能：
 * - 创建/编辑/删除流媒体账号
 * - 查询流媒体账号列表（分页）
 * - 获取账号已登录的Xbox主机列表
 * - 平台管理员可管理所有商户的账号
 * - 商户用户只能管理本商户的账号
 */
@RestController
@RequestMapping("/api/streaming-accounts")
@RequiredArgsConstructor
public class StreamingAccountController {

    private final StreamingAccountService streamingAccountService;
    private final StreamingAccountLoginRecordService loginRecordService;
    private final MerchantService merchantService;

    /**
     * 创建流媒体账号
     * 平台管理员可指定商户，非平台管理员自动使用当前用户商户
     *
     * @param request 流媒体账号信息
     * @return 创建的流媒体账号
     */
    @PostMapping
    public ApiResponse<StreamingAccount> create(@Valid @RequestBody StreamingAccountRequest request) {
        String merchantId;
        if (UserContext.isPlatformAdmin()) {
            merchantId = request.getMerchantId();
        } else {
            merchantId = UserContext.getMerchantId();
        }

        StreamingAccount account = streamingAccountService.create(
                merchantId, request.getName(), request.getEmail(), request.getPassword(), request.getAuthCode());
        return ApiResponse.success("创建成功", account);
    }

    /**
     * 分页查询流媒体账号列表
     * 平台管理员返回所有账号，商户用户返回本商户账号
     *
     * @param request 分页请求参数
     * @return 流媒体账号分页列表
     */
    @GetMapping
    public ApiResponse<IPage<StreamingAccountItemDto>> list(StreamingAccountPageRequest request) {
        String merchantId = UserContext.isPlatformAdmin() ? null : UserContext.getMerchantId();
        IPage<StreamingAccount> page = streamingAccountService.findByMerchantId(merchantId, request);

        List<Merchant> merchants = merchantService.findAllSimple();
        Map<String, String> merchantNameMap = merchants.stream()
                .collect(Collectors.toMap(Merchant::getId, Merchant::getName));

        IPage<StreamingAccountItemDto> dtoPage = page.convert(item -> {
            StreamingAccountItemDto dto = new StreamingAccountItemDto();
            BeanUtils.copyProperties(item, dto);
            dto.setMerchantName(merchantNameMap.get(item.getMerchantId()));
            return dto;
        });

        return ApiResponse.success(dtoPage);
    }

    /**
     * 获取流媒体账号详情
     *
     * @param id 流媒体账号ID
     * @return 流媒体账号信息
     */
    @GetMapping("/{id}")
    public ApiResponse<StreamingAccount> getById(@PathVariable String id) {
        StreamingAccount account = streamingAccountService.findById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !account.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        return ApiResponse.success(account);
    }

    /**
     * 更新流媒体账号
     *
     * @param id      流媒体账号ID
     * @param request 更新后的账号信息
     * @return 操作结果
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @Valid @RequestBody StreamingAccountRequest request) {
        StreamingAccount account = streamingAccountService.findById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !account.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        streamingAccountService.update(id, request.getName(), request.getAuthCode());
        return ApiResponse.success("更新成功", null);
    }

    /**
     * 删除流媒体账号
     *
     * @param id 流媒体账号ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        StreamingAccount account = streamingAccountService.findById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !account.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        streamingAccountService.delete(id);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 获取账号已登录的Xbox主机ID列表
     *
     * @param id 流媒体账号ID
     * @return Xbox主机ID列表
     */
    @GetMapping("/{id}/xbox-hosts")
    public ApiResponse<List<String>> getLoggedXboxHosts(@PathVariable String id) {
        StreamingAccount account = streamingAccountService.findById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }
        List<String> xboxHosts = loginRecordService.findByStreamingAccountId(id).stream()
                .map(r -> r.getXboxHostId())
                .collect(Collectors.toList());
        return ApiResponse.success(xboxHosts);
    }
}