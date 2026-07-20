package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 分控安装激活请求（安装器 → 总控）
 *
 * <p>安装器在商户机器上收集激活码+机器指纹后调总控激活接口。
 * 接口公开不走 JWT，以激活码作为一次性凭证。
 */
@Data
public class InstallActivateRequest {

    /** 激活码（总控管理员生成，一次性使用） */
    @NotBlank
    private String activationCode;

    /** 机器指纹（MAC+主机名+OS 的 SHA-256，绑定 License 防拷贝） */
    @NotBlank
    private String machineFingerprint;
}
