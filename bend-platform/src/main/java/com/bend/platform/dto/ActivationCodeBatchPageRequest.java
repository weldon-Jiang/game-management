package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 激活码批次分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class ActivationCodeBatchPageRequest extends PageRequest {

    private String status;
}
