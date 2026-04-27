package com.bend.platform.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class GameAccountImportDto {

    @NotBlank(message = "Xbox玩家名称不能为空")
    @Size(max = 50, message = "Xbox玩家名称长度不能超过50")
    private String xboxGameName;

    @NotBlank(message = "Xbox邮箱不能为空")
    @Email(message = "Xbox邮箱格式不正确")
    private String xboxLiveEmail;

    private String xboxLivePassword;
}
