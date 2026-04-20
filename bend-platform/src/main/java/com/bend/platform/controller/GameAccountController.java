package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.GameAccountPageRequest;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 游戏账号控制器
 *
 * 功能说明：
 * - 管理Xbox游戏账号
 * - 游戏账号关联到流媒体账号
 *
 * 主要功能：
 * - 创建/编辑/删除游戏账号
 * - 查询游戏账号列表（分页）
 * - 平台管理员可管理所有账号
 * - 商户用户只能管理本商户的账号
 */
@RestController
@RequestMapping("/api/game-accounts")
@RequiredArgsConstructor
public class GameAccountController {

    private final GameAccountService gameAccountService;
    private final StreamingAccountMapper streamingAccountMapper;

    /**
     * 分页查询游戏账号列表
     * 平台管理员返回所有账号，商户用户返回本商户账号
     *
     * @param request 分页请求参数
     * @return 游戏账号分页列表
     */
    @GetMapping
    public ApiResponse<IPage<GameAccount>> list(GameAccountPageRequest request) {
        if (UserContext.isPlatformAdmin()) {
            return ApiResponse.success(gameAccountService.findAll(request));
        }
        return ApiResponse.success(gameAccountService.findByMerchantId(UserContext.getMerchantId(), request));
    }

    /**
     * 获取游戏账号详情
     *
     * @param id 游戏账号ID
     * @return 游戏账号信息
     */
    @GetMapping("/{id}")
    public ApiResponse<GameAccount> getById(@PathVariable String id) {
        GameAccount account = gameAccountService.findById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }
        return ApiResponse.success(account);
    }

    /**
     * 创建游戏账号
     *
     * @param account 游戏账号信息
     * @return 创建的游戏账号
     */
    @PostMapping
    public ApiResponse<GameAccount> create(@RequestBody GameAccount account) {
        String merchantId = UserContext.getMerchantId();
        if (UserContext.isPlatformAdmin() && account.getStreamingId() != null) {
            StreamingAccount streaming = streamingAccountMapper.selectById(account.getStreamingId());
            if (streaming != null) {
                merchantId = streaming.getMerchantId();
            }
        }
        GameAccount result = gameAccountService.create(merchantId, account);
        return ApiResponse.success("创建成功", result);
    }

    /**
     * 更新游戏账号
     *
     * @param id      游戏账号ID
     * @param account 更新后的账号信息
     * @return 操作结果
     */
    @PutMapping("/{id}")
    public ApiResponse<Void> update(@PathVariable String id, @RequestBody GameAccount account) {
        GameAccount existing = gameAccountService.findById(id);
        if (existing == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        String merchantId = UserContext.getMerchantId();
        if (!UserContext.isPlatformAdmin()) {
            StreamingAccount streaming = streamingAccountMapper.selectById(existing.getStreamingId());
            if (streaming == null || !streaming.getMerchantId().equals(merchantId)) {
                throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
            }
        }

        gameAccountService.update(id, account);
        return ApiResponse.success("更新成功", null);
    }

    /**
     * 删除游戏账号
     *
     * @param id 游戏账号ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        GameAccount account = gameAccountService.findById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        String merchantId = UserContext.getMerchantId();
        if (!UserContext.isPlatformAdmin()) {
            StreamingAccount streaming = streamingAccountMapper.selectById(account.getStreamingId());
            if (streaming == null || !streaming.getMerchantId().equals(merchantId)) {
                throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
            }
        }

        gameAccountService.delete(id);
        return ApiResponse.success("删除成功", null);
    }
}