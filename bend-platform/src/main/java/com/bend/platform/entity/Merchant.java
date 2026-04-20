package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 商户实体类
 * 代表一个商户/租户组织
 */
@Data
@TableName("merchant")
public class Merchant {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String phone;
    private String name;
    private String status;
    private LocalDateTime expireTime;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}