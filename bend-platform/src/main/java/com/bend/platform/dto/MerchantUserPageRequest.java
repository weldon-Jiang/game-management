package com.bend.platform.dto;

/**
 * 商户用户分页请求
 */
public class MerchantUserPageRequest extends PageRequest {

    private String merchantId;
    
    private String role;

    public String getMerchantId() {
        return merchantId;
    }

    public void setMerchantId(String merchantId) {
        this.merchantId = merchantId;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }
}
