package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 流媒体账号实体类
 *
 * 功能说明：
 * - 存储和管理Xbox Game Pass等流媒体服务账号信息
 * - 支持多商户隔离，每个账号归属于特定商户
 * - 记录账号状态和错误信息用于监控
 * - 关联Agent实现远程控制和自动化
 *
 * 账号状态：
 * - active: 正常可用
 * - inactive: 未激活
 * - error: 错误状态
 * - offline: 离线状态
 *
 * 安全说明：
 * - 密码使用AES加密存储
 * - 敏感信息不在日志中打印
 */
@Data
@TableName("streaming_account")
public class StreamingAccount {

    /**
     * 账号唯一标识符
     * 使用UUID自动生成
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 商户ID
     * 标识账号所属的商户
     */
    private String merchantId;

    /**
     * 账号名称
     * 用于显示的友好名称
     */
    private String name;

    /**
     * 账号邮箱
     * 流媒体服务的登录邮箱
     */
    private String email;

    /**
     * 加密后的密码
     * 使用AES加密存储，保障安全
     */
    private String passwordEncrypted;

    /**
     * 认证码
     * 流媒体服务（如Twitch、Mixer等）的额外认证码
     */
    private String authCode;

    /**
     * 账号状态
     * active-正常 inactive-未激活 error-错误 offline-离线
     */
    private String status;

    /**
     * 当前绑定的Agent ID
     * 账号当前由哪个Agent控制
     * 为空表示账号未被任何Agent使用
     */
    private String agentId;

    /**
     * 最近错误代码
     * 记录最近一次错误的代码标识
     */
    private String lastErrorCode;

    /**
     * 最近错误信息
     * 记录最近一次错误的详细描述
     */
    private String lastErrorMessage;

    /**
     * 最近错误发生时间
     * 记录最近错误的时间戳
     */
    private LocalDateTime lastErrorTime;

    /**
     * 错误重试次数
     * 记录连续发生错误的次数
     * 用于判断账号是否需要人工介入
     */
    private Integer errorRetryCount;

    /**
     * 最后心跳时间
     * Agent发送心跳的最新时间
     * 用于判断Agent与账号的连接状态
     */
    private LocalDateTime lastHeartbeat;

    /**
     * 创建时间
     * 记录账号首次添加到系统的时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    /**
     * 更新时间
     * 记录账号信息最后修改的时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
