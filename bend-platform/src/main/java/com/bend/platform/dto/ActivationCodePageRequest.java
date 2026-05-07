package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 激活码分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class ActivationCodePageRequest extends PageRequest {

    /**
     * 商户ID过滤
     */
    private String merchantId;

    /**
     * 关键词搜索
     */
    private String keyword;

    /**
     * 状态过滤
     */
    private String status;

    /**
     * 订阅类型过滤
     */
    private String subscriptionType;
}
