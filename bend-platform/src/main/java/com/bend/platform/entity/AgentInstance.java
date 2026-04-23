package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * Agent实例实体类
 *
 * 功能说明：
 * - 存储和管理已注册的Agent实例信息
 * - 追踪Agent的运行状态和健康状况
 * - 关联商户实现多租户隔离
 * - 支持Agent的注册、注销和重新上线
 *
 * Agent状态：
 * - online: 在线，运行中
 * - offline: 离线，未运行
 * - uninstalled: 已卸载
 *
 * 安全说明：
 * - agentSecret用于Agent身份验证，请妥善保管
 * - 定期更新密钥增强安全性
 */
@Data
@TableName("agent_instance")
public class AgentInstance {

    /**
     * 数据库主键ID
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * Agent唯一标识符
     * 用于在系统中唯一标识一个Agent实例
     */
    private String agentId;

    /**
     * Agent密钥
     * 用于API请求的身份验证
     * 首次注册时由系统生成
     */
    private String agentSecret;

    /**
     * 商户ID
     * Agent绑定的商户，用于多租户隔离
     */
    private String merchantId;

    /**
     * 注册码
     * Agent注册时使用的注册码
     * 注册成功后关联到具体商户
     */
    private String registrationCode;

    /**
     * Agent主机IP地址
     * Agent所在机器的IP地址
     */
    private String host;

    /**
     * Agent监听端口
     * Agent监听的端口号，默认8888
     */
    private Integer port;

    /**
     * Agent版本号
     * 用于版本管理和升级判断
     */
    private String version;

    /**
     * Agent状态
     * online-在线 offline-离线 uninstalled-已卸载
     */
    private String status;

    /**
     * 当前流媒体账号ID
     * Agent当前正在控制的流媒体账号
     */
    private String currentStreamingId;

    /**
     * 当前任务ID
     * Agent当前正在执行的任务
     */
    private String currentTaskId;

    /**
     * 最后心跳时间
     * Agent发送心跳的最新时间
     * 用于判断Agent是否存活
     */
    private LocalDateTime lastHeartbeat;

    /**
     * 最后在线时间
     * Agent最后处于在线状态的时间
     */
    private LocalDateTime lastOnlineTime;

    /**
     * 卸载原因
     * 记录Agent被卸载的原因
     */
    private String uninstallReason;

    /**
     * 创建时间
     * Agent首次注册到系统的时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    /**
     * 更新时间
     * Agent信息最后修改的时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    /**
     * 软删除标记
     * true表示已删除，false表示未删除
     */
    @TableLogic
    private Boolean deleted;
}
