package com.bend.platform.dto;

import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * 游戏账号批量导入请求（平台管理员可指定 merchantId）。
 */
@Data
public class BatchImportRequest {
    private String merchantId;

    @NotEmpty(message = "导入数据不能为空")
    private List<GameAccountImportDto> accounts;
}
