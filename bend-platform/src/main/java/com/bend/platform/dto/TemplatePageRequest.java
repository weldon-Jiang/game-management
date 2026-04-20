package com.bend.platform.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 模板分页请求
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class TemplatePageRequest extends PageRequest {

    /**
     * 模板类型过滤
     */
    private String category;

    /**
     * 游戏类型过滤
     */
    private String game;
}