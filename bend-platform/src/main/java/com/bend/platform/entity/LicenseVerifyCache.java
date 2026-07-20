package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 分控 License 校验缓存
 *
 * <p>仅分控库使用。缓存最近一次向总控校验的结果(含签名),
 * 用于总控不可达时的离线宽限判断。签名防止商户篡改缓存延长授权。
 */
@Data
@TableName("license_verify_cache")
public class LicenseVerifyCache {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String licenseKey;

    private String merchantId;

    /** 校验结果: true-有效 false-无效 */
    private Boolean valid;

    /** 授权到期时间(校验返回) */
    private LocalDateTime expireAt;

    /** 功能特性JSON(校验返回) */
    private String features;

    /** 本次校验时间(总控服务器时间,签名内) */
    private LocalDateTime verifiedAt;

    /** 校验结果签名(防伪造) */
    private String signature;

    /** 原始签名前JSON */
    private String rawPayload;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
