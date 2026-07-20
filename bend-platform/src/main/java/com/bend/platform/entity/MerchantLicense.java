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
 * 商户授权(License)实体
 *
 * <p>总控平台签发,分控(租户)启动与定时校验时使用。
 * 一个商户同一时间通常只有一条 active 的 license。
 */
@Data
@TableName("merchant_license")
public class MerchantLicense {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /** 所属商户ID */
    private String merchantId;

    /** 授权密钥(分控校验时携带,对外可见) */
    private String licenseKey;

    /** 授权密钥哈希(服务端存储,用于校验 license_key) */
    private String licenseSecret;

    /** 状态: active, expired, revoked, pending */
    private String status;

    /** 到期时间 */
    private LocalDateTime expireAt;

    /** 最大Agent数量 */
    private Integer maxAgents;

    /** 最大并发任务数 */
    private Integer maxTasks;

    /** 功能特性(JSON) */
    private String features;

    /** 绑定的机器指纹(首次激活时写入,空表示未绑定) */
    private String boundMachineFingerprint;

    /** 首次激活时间 */
    private LocalDateTime activatedAt;

    /** 分控最近一次校验时间 */
    private LocalDateTime lastVerifiedAt;

    /** 分控最近一次校验来源IP */
    private String lastVerifyIp;

    /** 离线宽限小时数 */
    private Integer offlineGraceHours;

    /** 吊销时间 */
    private LocalDateTime revokedAt;

    /** 吊销原因 */
    private String revokeReason;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    @TableLogic
    private Boolean deleted;
}
