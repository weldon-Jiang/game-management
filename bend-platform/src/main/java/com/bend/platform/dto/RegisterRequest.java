package com.bend.platform.dto;

import javax.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 注册请求参数
 */
@Data
public class RegisterRequest {
    @NotBlank(message = "用户名不能为空")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;

    private String phone;

    private String merchantName;
}