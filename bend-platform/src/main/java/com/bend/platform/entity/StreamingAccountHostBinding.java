package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 流媒体账号与主机 M:N 绑定关系。
 *
 * <p>设备注册信息仍在 {@link XboxHost}；本表仅表达账号可串流哪些主机，
 * 以及绑定来源（手动 / 云端同步 / 串流成功后自动绑定）。</p>
 */
@Data
@TableName("streaming_account_host_binding")
public class StreamingAccountHostBinding {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String streamingAccountId;

    private String xboxHostId;

    /** manual / cloud_sync / stream_success */
    private String source;

    /** active / inactive */
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
