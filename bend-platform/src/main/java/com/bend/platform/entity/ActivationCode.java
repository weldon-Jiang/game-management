package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 激活码实体类
 * 代表一个具体的激活码
 */
@Data
@TableName("activation_code")
public class ActivationCode {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;
    private String batchId;
    private String code;
    private String status;
    private String usedBy;
    private LocalDateTime usedTime;
    private LocalDateTime expireTime;
    private LocalDateTime generatedTime;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}