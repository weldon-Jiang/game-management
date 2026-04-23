package com.bend.platform.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 分页请求基类
 * 所有分页请求应继承此类
 */
@Data
public class PageRequest {

    @Min(value = 1, message = "页码最小值为1")
    private Integer pageNum = 1;

    @Min(value = 1, message = "每页数量最小值为1")
    @Max(value = 100, message = "每页数量最大值为100")
    private Integer pageSize = 10;

    public int getOffset() {
        if (pageNum == null || pageNum < 1) {
            pageNum = 1;
        }
        if (pageSize == null || pageSize < 1) {
            pageSize = 10;
        }
        return (pageNum - 1) * pageSize;
    }
}