package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 游戏账号实体类
 *
 * 功能说明：
 * - 存储和管理Xbox游戏账号信息
 * - 关联到流媒体账号，一个流媒体账号可包含多个游戏账号
 * - 支持游戏账号的优先级管理和使用限制
 * - 记录游戏账号的使用统计
 *
 * 主要用途：
 * - Xbox云游戏账号管理
 * - 游戏内多账号切换
 * - 游戏时长和场次统计
 *
 * 安全说明：
 * - Xbox密码使用AES加密存储
 * - 敏感信息不在日志中打印
 */
@Data
@TableName("game_account")
public class GameAccount {

    /**
     * 账号唯一标识符
     * 使用UUID自动生成
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 关联的流媒体账号ID
     * 游戏账号所属的流媒体账号
     */
    private String streamingId;

    /**
     * 商户ID
     * 账号所属的商户
     */
    private String merchantId;

    /**
     * 游戏昵称
     * 玩家的游戏名称
     */
    private String gameName;

    /**
     * 登录邮箱
     * 游戏账号的登录邮箱
     */
    private String email;

    /**
     * 加密后的密码
     * 使用AES加密存储，JsonIgnore避免序列化返回给前端
     */
    @JsonIgnore
    private String passwordEncrypted;

    /**
     * 明文密码（仅用于接收前端输入，不存储到数据库）
     * 使用JsonProperty确保Jackson序列化时包含此字段
     */
    @TableField(exist = false)
    @JsonProperty
    private String password;

    /**
     * 锁定的Xbox ID
     * 当前锁定到此Xbox主机
     */
    private Long lockedXboxId;

    /**
     * 是否为主账号
     * true-主账号 false-备选账号
     * 主账号优先使用
     */
    private Boolean isPrimary;

    /**
     * 是否激活
     * true-已激活 false-未激活
     */
    private Boolean isActive;

    /**
     * 使用优先级
     * 数值越小优先级越高
     */
    private Integer priority;

    /**
     * 每日比赛限制场次
     * 每天最多进行的游戏场次
     */
    private Integer dailyMatchLimit;

    /**
     * 今日已完成场次
     * 当天已进行的游戏场次
     */
    private Integer todayMatchCount;

    /**
     * 总比赛场次
     * 累计已进行的游戏场次
     */
    private Integer totalMatchCount;

    /**
     * 最后使用时间
     * 账号最后一次被使用的时间
     */
    private LocalDateTime lastUsedTime;

    /**
     * 当前绑定的Agent ID
     */
    private String agentId;

    /**
     * 当前状态
     * idle-空闲 busy-忙碌
     */
    private String status;

    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    /**
     * 更新时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    @TableField(exist = false)
    private String merchantName;

    @TableField(exist = false)
    private String streamingName;

    @TableLogic
    private Boolean deleted;
}
