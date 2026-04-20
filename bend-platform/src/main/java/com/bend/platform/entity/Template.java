package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 模板实体
 * 用于图像识别和自动化任务的模板图片
 */
@Data
@TableName("template")
public class Template {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;

    private String description;

    private String category;

    private String imageUrl;

    private String thumbnailUrl;

    private Integer width;

    private Integer height;

    private Double matchThreshold;

    private String game;

    private String region;

    private Integer usageCount;

    private Integer status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Boolean deleted;
}
