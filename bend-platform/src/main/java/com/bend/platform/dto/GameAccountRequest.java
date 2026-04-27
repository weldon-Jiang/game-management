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

    @NotBlank(message = "账号名称不能为空")
    @Size(min = 1, max = 100, message = "账号名称长度必须在1-100之间")
    private String name;

    @NotBlank(message = "Xbox玩家名不能为空")
    @Size(max = 50, message = "Xbox玩家名长度不能超过50")
    private String xboxGameName;

    @NotBlank(message = "Xbox邮箱不能为空")
    @Email(message = "Xbox邮箱格式不正确")
    private String xboxLiveEmail;

    private String xboxLivePassword;

    @Size(max = 500, message = "备注长度不能超过500")
    private String remark;
}
