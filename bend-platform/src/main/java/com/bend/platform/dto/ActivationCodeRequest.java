package com.bend.platform.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 激活码请求参数
 */
@Data
public class ActivationCodeRequest {
    private String merchantId;
    private String batchName;
    private String vipType;
    private Integer count;
    private LocalDateTime expireTime;
}