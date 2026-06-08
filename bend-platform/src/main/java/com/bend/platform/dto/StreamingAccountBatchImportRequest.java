package com.bend.platform.dto;

import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * 流媒体账号批量导入请求。
 */
@Data
public class StreamingAccountBatchImportRequest {
    private String merchantId;

    @NotEmpty(message = "导入数据不能为空")
    private List<StreamingAccountImportDto> accounts;
}
