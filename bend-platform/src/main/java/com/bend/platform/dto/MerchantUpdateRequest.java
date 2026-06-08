package com.bend.platform.dto;

import lombok.Data;

/**
 * 更新商户基本信息请求。
 */
@Data
public class MerchantUpdateRequest {
    private String name;
    private String phone;
    private Boolean isSystem;
}
