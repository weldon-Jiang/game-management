package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 商户注册码分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class MerchantRegistrationCodePageRequest extends PageRequest {

    /**
     * 商户ID过滤
     */
    private String merchantId;

    /**
     * 关键词搜索
     */
    private String keyword;
}