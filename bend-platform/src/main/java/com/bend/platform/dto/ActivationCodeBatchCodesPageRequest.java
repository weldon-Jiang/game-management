package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 批次激活码分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class ActivationCodeBatchCodesPageRequest extends PageRequest {

    private String status;
}
