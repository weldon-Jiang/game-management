package com.bend.platform.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 游戏账号请求参数
 */
@Data
public class GameAccountRequest {

    @NotBlank(message = "串流账号ID不能为空")
    private String streamingId;

    @NotBlank(message = "游戏昵称不能为空")
    @Size(min = 1, max = 100, message = "游戏昵称长度必须在1-100之间")
    private String gameName;

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    private String password;

    @Size(max = 500, message = "备注长度不能超过500")
    private String remark;

    /**
     * Platform type: xbox, playstation (default xbox)
     */
    private String platform = "xbox";
}
