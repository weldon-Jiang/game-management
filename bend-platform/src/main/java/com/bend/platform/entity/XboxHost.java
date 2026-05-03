package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * Xbox主机实体类
 *
 * 功能说明：
 * - 存储和管理Xbox主机设备信息
 * - 支持Xbox主机的发现和状态监控
 * - 实现主机锁定机制防止冲突使用
 * - 关联流媒体账号和Gamertag
 *
 * 主机状态：
 * - online: 在线，已被发现
 * - offline: 离线
 * - in_use: 正在使用中
 * - error: 错误状态
 *
 * 锁定机制：
 * - 用于防止多个Agent同时控制同一台主机
 * - 锁定有过期时间设计
 * - 支持强制解锁
 */
@Data
@TableName("xbox_host")
public class XboxHost {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;

    private String xboxId;

    private String name;

    private String ipAddress;

    private String status;

    private String boundStreamingAccountId;

    private String boundGamertag;

    private String powerState;

    private String lockedByAgentId;

    private LocalDateTime lockedTime;

    private LocalDateTime lockExpiresTime;

    private LocalDateTime lastSeenTime;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    @TableLogic
    private Boolean deleted;
}
