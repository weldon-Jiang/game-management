package com.bend.platform.dto;

import lombok.Data;
import java.util.List;

/**
 * 批量导入结果摘要。
 */
@Data
public class ImportResultDto {
    private int successCount;
    private int skipCount;
    private int failCount;
    private List<String> errors;
}
