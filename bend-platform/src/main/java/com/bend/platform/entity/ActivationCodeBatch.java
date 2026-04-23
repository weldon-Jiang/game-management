package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 激活码批次实体类
 * 代表一批生成的激活码
 */
@Data
@TableName("activation_code_batch")
public class ActivationCodeBatch {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;
    private String batchName;
    private Integer totalCount;
    private Integer usedCount;
    private Integer remainingCount;
    private String vipType;
    private String vipConfigId;
    private LocalDateTime expireTime;
    private String status;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}