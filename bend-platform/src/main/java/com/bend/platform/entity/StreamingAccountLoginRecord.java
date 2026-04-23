package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 流媒体账号Xbox登录记录实体类
 * 记录流媒体账号在Xbox主机上的登录历史
 */
@Data
@TableName("streaming_account_login_record")
public class StreamingAccountLoginRecord {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String streamingAccountId;
    private String xboxHostId;
    private String loggedGamertag;
    private LocalDateTime loggedTime;
    private LocalDateTime lastUsedTime;
    private Integer useCount;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}