package com.bend.platform.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * Xbox主机请求参数
 */
@Data
public class XboxHostRequest {
    private String id;

    private String merchantId;

    @NotBlank(message = "Xbox ID不能为空")
    private String xboxId;

    private String name;
    private String ipAddress;
}