package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 串流账号 xblive 认证 Token 平台缓存。
 *
 * <p>存储 Agent Step1 产出的 {@code token_doc}（AES 加密），供同商户下任意 Agent
 * 复用/刷新，避免换机重复 Playwright 全量登录。</p>
 */
@Data
@TableName("streaming_account_auth_cache")
public class StreamingAccountAuthCache {

    @TableId
    private String streamingAccountId;

    private String merchantId;

    /** AES 加密后的 token_doc JSON */
    private String tokenDocEncrypted;

    /** 乐观锁版本，PUT 时递增 */
    private Integer tokenVersion;

    /** valid / refresh_needed / expired */
    private String authState;

    private String lastAuthAgentId;

    private LocalDateTime lastAuthTime;

    private LocalDateTime xhomeExpiresAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
