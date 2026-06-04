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

    @NotBlank(message = "账号名称不能为空")
    private String name;

    private String email;

    private String password;

    private String authCode;
}