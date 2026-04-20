package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * Agent分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class AgentPageRequest extends PageRequest {

    /**
     * 按状态筛选
     */
    private String status;

    /**
     * 按商户ID筛选
     */
    private String merchantId;
}