package com.bend.platform.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class GameAccountImportDto {

    @NotBlank(message = "游戏昵称不能为空")
    @Size(max = 50, message = "游戏昵称长度不能超过50")
    private String gameName;

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    private String password;

    private String platform;
}
