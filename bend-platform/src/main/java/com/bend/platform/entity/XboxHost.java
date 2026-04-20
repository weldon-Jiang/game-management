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

    /**
     * 主机唯一标识符
     * 使用UUID自动生成
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 商户ID
     * 主机所属的商户
     */
    private String merchantId;

    /**
     * Xbox主机ID
     * Xbox设备序列号或LiveID
     */
    private String xboxId;

    /**
     * 主机名称
     * 用于显示的友好名称
     */
    private String name;

    /**
     * 主机IP地址
     * Xbox主机在局域网中的IP
     */
    private String ipAddress;

    /**
     * 绑定的流媒体账号ID
     * 主机当前绑定的流媒体账号
     */
    private String boundStreamingAccountId;

    /**
     * 绑定的Gamertag
     * 主机当前登录的Xbox Gamertag
     */
    private String boundGamertag;

    /**
     * 电源状态
     * on-开机 off-关机
     */
    private String powerState;

    /**
     * 锁定Agent ID
     * 主机当前被哪个Agent锁定
     * 为空表示未被锁定
     */
    private String lockedByAgentId;

    /**
     * 锁定时间
     * 主机被锁定的时间
     */
    private LocalDateTime lockedAt;

    /**
     * 锁定过期时间
     * 锁定自动解期的时间
     * 用于防止死锁
     */
    private LocalDateTime lockExpiresAt;

    /**
     * 主机状态
     * online-在线 offline-离线 in_use-使用中 error-错误
     */
    private String status;

    /**
     * 最后发现时间
     * 主机最后被发现的时间
     */
    private LocalDateTime lastSeenAt;

    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /**
     * 更新时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
