package com.bend.platform.dto;

import lombok.Data;

@Data
public class MerchantCreateRequest {
    private String name;
    private String phone;
    private Boolean isSystem;
}
