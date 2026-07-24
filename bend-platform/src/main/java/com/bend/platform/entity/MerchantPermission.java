package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 商户使用权限(Permission)实体
 *
 * <p>与 License(软件授权)解耦:
 * <ul>
 *   <li>License: 软件授权凭证（终身有效，防拷贝/机器绑定）</li>
 *   <li>Permission: 使用权限（会到期，控制商户能否操作）</li>
 * </ul>
 *
 * <p>每个商户只有一条 permission 记录。
 */
@Data
@TableName("merchant_permission")
public class MerchantPermission {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /** 所属商户ID */
    private String merchantId;

    /** 状态: active, expired, suspended */
    private String status;

    /** 到期时间 */
    private LocalDateTime expireAt;

    /** 最大Agent数量 */
    private Integer maxAgents;

    /** 最大并发任务数 */
    private Integer maxTasks;

    /** 功能特性(JSON) */
    private String features;

    /** 离线宽限小时数 */
    private Integer offlineGraceHours;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    @TableLogic
    private Boolean deleted;
}
