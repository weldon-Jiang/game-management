package com.bend.platform.dto;

import lombok.Data;
import java.math.BigDecimal;

/**
 * VIP配置请求参数
 */
@Data
public class VipConfigRequest {
    private String vipType;
    private String vipName;
    private BigDecimal price;
    private Integer durationDays;
    private String features;
    private Boolean isDefault;
}