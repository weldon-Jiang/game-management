package com.bend.platform.dto;

import lombok.Data;

/**
 * 创建商户请求。
 */
@Data
public class MerchantCreateRequest {
    private String name;
    private String phone;
    private Boolean isSystem;
}
