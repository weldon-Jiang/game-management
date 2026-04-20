package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.StreamingAccountLoginRecordService;
import com.bend.platform.service.XboxHostService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * Agent回调控制器
 *
 * 功能说明：
 * - Agent执行操作后回调平台记录结果
 * - 处理Agent上报的各种状态和事件
 *
 * 主要功能：
 * - 记录流媒体账号登录成功
 * - Xbox主机状态更新
 */
@RestController
@RequestMapping("/api/agent-callback")
@RequiredArgsConstructor
public class AgentCallbackController {

    private final StreamingAccountLoginRecordService loginRecordService;
    private final XboxHostService xboxHostService;

    /**
     * 记录流媒体账号在Xbox主机上登录成功
     * Agent登录成功后调用此接口记录
     *
     * @param streamingAccountId 流媒体账号ID
     * @param xboxHostId        Xbox主机ID
     * @param gamertag          登录时使用的Gamertag
     */
    @PostMapping("/streaming-login-success")
    public ApiResponse<Void> recordStreamingLoginSuccess(
            @RequestParam String streamingAccountId,
            @RequestParam String xboxHostId,
            @RequestParam String gamertag) {
        loginRecordService.recordLogin(streamingAccountId, xboxHostId, gamertag);
        return ApiResponse.success("记录成功", null);
    }

    /**
     * Xbox主机状态更新
     * Agent定期上报Xbox主机状态
     *
     * @param xboxHostId Xbox主机ID
     * @param status     状态 (online/offline/error)
     */
    @PostMapping("/xbox-status")
    public ApiResponse<Void> updateXboxStatus(
            @RequestParam String xboxHostId,
            @RequestParam String status) {
        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }
        xboxHostService.updateStatus(xboxHostId, status);
        return ApiResponse.success("状态更新成功", null);
    }
}