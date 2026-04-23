package com.bend.platform.dto;

import lombok.Data;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 商户用户创建请求DTO
 */
@Data
public class MerchantUserCreateRequest {

    /**
     * 商户ID（可选，平台管理员可以指定）
     */
    private String merchantId;

    /**
     * 用户名
     */
    @NotBlank(message = "用户名不能为空")
    @Size(min = 2, max = 20, message = "用户名长度为2-20个字符")
    private String username;

    /**
     * 密码
     */
    @NotBlank(message = "密码不能为空")
    @Size(min = 4, max = 20, message = "密码长度为4-20个字符")
    private String password;

    /**
     * 手机号
     */
    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;

    /**
     * 角色
     */
    @NotBlank(message = "角色不能为空")
    private String role;
}
