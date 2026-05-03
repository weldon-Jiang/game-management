package com.bend.platform.dto;

import lombok.Data;

@Data
public class MerchantUpdateRequest {
    private String name;
    private String phone;
    private Boolean isSystem;
}
