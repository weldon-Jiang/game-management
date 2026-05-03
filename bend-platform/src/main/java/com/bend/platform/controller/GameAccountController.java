package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.BatchImportRequest;
import com.bend.platform.dto.BindGameAccountRequest;
import com.bend.platform.dto.GameAccountImportDto;
import com.bend.platform.dto.GameAccountPageRequest;
import com.bend.platform.dto.ImportResultDto;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.util.UserContext;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.apache.commons.lang3.StringUtils;
import org.springframework.web.bind.annotation.*;

import javax.naming.AuthenticationException;
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
        if (StringUtils.isNotBlank(request.getStreamingId())) {
            StreamingAccount streaming = streamingAccountMapper.selectById(request.getStreamingId());
            if (streaming == null) {
                throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
            }
            if (!UserContext.isPlatformAdmin() && !streaming.getMerchantId().equals(UserContext.getMerchantId())) {
                throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
            }
            return ApiResponse.success(gameAccountService.findByStreamingId(request.getStreamingId(), request));
        }
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
        if (!UserContext.isPlatformAdmin() && !account.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
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
        String merchantId;
        if (UserContext.isPlatformAdmin() && account.getMerchantId() != null) {
            merchantId = account.getMerchantId();
        } else {
            merchantId = UserContext.getMerchantId();
        }
        GameAccount result = gameAccountService.create(merchantId, account);
        return ApiResponse.success("创建成功", result);
    }

    /**
     * 下载导入模板
     *
     * @return CSV模板内容
     */
    @GetMapping("/template")
    public ApiResponse<String> downloadTemplate() {
        String template = "Xbox玩家名称,Xbox邮箱,Xbox密码\nPlayer1,player1@email.com,password1\nPlayer2,player2@email.com,password2";
        return ApiResponse.success(template);
    }

    /**
     * 批量导入游戏账号
     *
     * @param accounts 导入的账号列表
     * @return 导入结果
     */
    @PostMapping("/batch")
    public ApiResponse<ImportResultDto> batchImport(@Valid @RequestBody BatchImportRequest request) {
        String merchantId;
        if (UserContext.isPlatformAdmin()) {
            if (request.getMerchantId() == null || request.getMerchantId().isEmpty()) {
                merchantId = UserContext.getMerchantId();
            } else {
                merchantId = request.getMerchantId();
            }
        } else {
            merchantId = UserContext.getMerchantId();
        }
        ImportResultDto result = gameAccountService.batchImport(merchantId, request.getAccounts());
        return ApiResponse.success(result);
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

        if (!UserContext.isPlatformAdmin()) {
            if (!existing.getMerchantId().equals(UserContext.getMerchantId())) {
                throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
            }
        }

        gameAccountService.update(id, account);
        return ApiResponse.success("更新成功", null);
    }

    @GetMapping("/unbound")
    public ApiResponse<List<GameAccount>> findUnboundAccounts(@RequestParam(required = false) String merchantId) {
        if (merchantId == null || merchantId.isEmpty()) {
            merchantId = UserContext.getMerchantId();
        } else if (!UserContext.isPlatformAdmin() && !merchantId.equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        List<GameAccount> accounts = gameAccountService.findUnboundByMerchantId(merchantId);
        return ApiResponse.success(accounts);
    }

    @PostMapping("/bind/{streamingAccountId}")
    public ApiResponse<Void> bindToStreamingAccount(@PathVariable String streamingAccountId, @Valid @RequestBody BindGameAccountRequest request) {
        StreamingAccount streaming = streamingAccountMapper.selectById(streamingAccountId);
        if (streaming == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }

        if (!UserContext.isPlatformAdmin() && !streaming.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        for (String gameAccountId : request.getGameAccountIds()) {
            GameAccount gameAccount = gameAccountService.findById(gameAccountId);
            if (gameAccount == null) {
                throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
            }
            if (!UserContext.isPlatformAdmin() && !gameAccount.getMerchantId().equals(streaming.getMerchantId())) {
                throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED, "只能绑定同一商户的游戏账号");
            }
        }

        gameAccountService.bindToStreamingAccount(streamingAccountId, request.getGameAccountIds());
        return ApiResponse.success("绑定成功", null);
    }

    @PostMapping("/unbind")
    public ApiResponse<Void> unbindFromStreamingAccount(@Valid @RequestBody BindGameAccountRequest request) {
        if (!UserContext.isPlatformAdmin()) {
            for (String gameAccountId : request.getGameAccountIds()) {
                GameAccount gameAccount = gameAccountService.findById(gameAccountId);
                if (gameAccount == null) {
                    throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
                }
                if (!gameAccount.getMerchantId().equals(UserContext.getMerchantId())) {
                    throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
                }
            }
        }
        gameAccountService.unbindFromStreamingAccount(request.getGameAccountIds());
        return ApiResponse.success("解绑成功", null);
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

        if (!UserContext.isPlatformAdmin() && !account.getMerchantId().equals(UserContext.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        if (account.getStreamingId() != null && !account.getStreamingId().isEmpty()) {
            throw new BusinessException(ResultCode.GameAccount.BIND_STREAMING_ACCOUNT, "该游戏账号已关联流媒体账号，请先解绑后再删除");
        }

        gameAccountService.delete(id);
        return ApiResponse.success("删除成功", null);
    }
}