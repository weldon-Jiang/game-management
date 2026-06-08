package com.bend.platform.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 单条游戏账号导入行（Excel/CSV 解析后映射）。
 */
@Data
public class GameAccountImportDto {

    @Size(max = 64, message = "游戏昵称长度不能超过64")
    private String gameName;

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    private String password;

    private String platform;

    private Integer dailyMatchLimit;

    private Integer cooldownHours;
}
