package com.bend.platform.dto;

import lombok.Data;

/**
 * 分页请求基类
 * 所有分页请求应继承此类
 */
@Data
public class PageRequest {

    /**
     * 页码（从1开始）
     */
    private Integer pageNum = 1;

    /**
     * 每页数量
     */
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