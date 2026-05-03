package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 商户点数账户实体
 */
@Data
@TableName("merchant_balance")
public class MerchantBalance {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private Integer balance;

    private Integer totalRecharged;

    private Integer totalConsumed;

    @Version
    private Integer version;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
