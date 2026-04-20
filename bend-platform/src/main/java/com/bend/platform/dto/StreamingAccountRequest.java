package com.bend.platform.dto;

import javax.validation.constraints.Email;
import javax.validation.constraints.NotBlank;
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

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    @NotBlank(message = "密码不能为空")
    private String password;

    private String authCode;
}