package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 任务实体
 *
 * 功能说明：
 * - 存储和管理Xbox自动化任务的所有信息
 * - 支持任务状态流转和重试机制
 * - 关联流媒体账号、游戏账号和Agent
 *
 * 任务状态：
 * - pending: 等待分配
 * - running: 执行中
 * - completed: 已完成
 * - failed: 执行失败
 * - cancelled: 已取消
 *
 * 任务类型：
 * - template_match: 模板匹配（图像识别）
 * - input_sequence: 输入序列（自动化操作）
 * - scene_detection: 场景检测
 * - account_switch: 账号切换
 * - stream_control: 流媒体控制
 * - custom: 自定义任务
 */
@Data
@TableName("task")
public class Task {

    /**
     * 任务唯一标识符
     * 使用UUID自动生成
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 任务名称
     * 用于显示和识别任务
     */
    private String name;

    /**
     * 任务描述
     * 详细说明任务的目的和内容
     */
    private String description;

    /**
     * 任务类型
     * 决定任务的执行方式和处理逻辑
     */
    private String type;

    /**
     * 目标Agent ID
     * 指定由哪个Agent执行此任务
     */
    private String targetAgentId;

    /**
     * 关联的流媒体账号ID
     * 任务操作的流媒体账号
     */
    private String streamingAccountId;

    /**
     * 关联的游戏账号ID
     * 任务操作的游戏账号
     */
    private String gameAccountId;

    /**
     * 任务状态
     * 标识任务当前所处阶段
     */
    private String status;

    /**
     * 任务优先级
     * 数值越小优先级越高
     */
    private String priority;

    /**
     * 任务参数（JSON格式）
     * 存储任务执行所需的具体参数
     */
    private String params;

    /**
     * 任务执行结果
     * 任务完成后返回的结果信息
     */
    private String result;

    /**
     * 错误信息
     * 任务失败时的错误描述
     */
    private String errorMessage;

    /**
     * 创建者ID
     * 创建任务的用户ID
     */
    private String createdBy;

    /**
     * 分配时间
     * 任务分配给Agent的时间
     */
    private LocalDateTime assignedTime;

    /**
     * 开始执行时间
     * Agent实际开始执行任务的时间
     */
    private LocalDateTime startedTime;

    /**
     * 完成时间
     * 任务执行完成的时间
     */
    private LocalDateTime completedTime;

    /**
     * 过期时间
     * 任务过期自动取消的时间点
     */
    private LocalDateTime expireTime;

    /**
     * 当前重试次数
     * 任务已经重试的次数
     */
    private Integer retryCount;

    /**
     * 最大重试次数
     * 任务允许的最大重试次数
     */
    private Integer maxRetries;

    /**
     * 创建时间
     * 记录插入数据库的时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    /**
     * 更新时间
     * 记录最后修改数据库的时间
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
