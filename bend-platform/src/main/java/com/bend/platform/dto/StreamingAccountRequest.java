package com.bend.platform.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 流媒体账号请求参数
 */
@Data
public class StreamingAccountRequest {
    private String id;

    private String merchantId;

    private String name;

    private String email;

    private String password;

    private String authCode;

    /**
     * 平台类型：xbox、playstation（必填，由用户自行选择）
     */
    @NotBlank(message = "平台类型不能为空")
    private String platform;
}