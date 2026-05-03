package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 设备绑定记录实体
 */
@Data
@TableName("device_binding")
public class DeviceBinding {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String userId;

    private String type;

    private String deviceId;

    private String deviceName;

    private String deviceModel;

    private String boundSubscriptionId;

    private LocalDateTime boundTime;

    private LocalDateTime unboundTime;

    private Boolean isActive;

    private Integer unbindCount;

    private LocalDateTime lastUnbindTime;

    private String lastBindSubscriptionId;

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableLogic
    private Boolean deleted;
}
