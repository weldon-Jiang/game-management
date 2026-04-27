package com.bend.platform.dto;

import lombok.Data;
import java.util.List;

@Data
public class ImportResultDto {
    private int successCount;
    private int failCount;
    private List<String> errors;
}
