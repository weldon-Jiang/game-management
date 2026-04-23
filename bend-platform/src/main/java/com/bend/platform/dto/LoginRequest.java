package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 登录请求参数
 */
@Data
public class LoginRequest {
    @NotBlank(message = "账号不能为空")
    private String loginKey;

    @NotBlank(message = "密码不能为空")
    private String password;
}