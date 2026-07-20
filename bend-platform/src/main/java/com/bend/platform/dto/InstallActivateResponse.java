package com.bend.platform.dto;

import lombok.Data;

/**
 * 分控安装激活响应（总控 → 安装器）
 *
 * <p>激活成功后一次性返回 License 凭证 + 商户数据 SQL。
 * licenseSecret 明文仅在此返回，安装器写入 tenant.env 后不再传输。
 */
@Data
public class InstallActivateResponse {

    /** License 密钥（分控持有，形如 LIC-xxxxxxxx-xxxxxxxx-xxxxxxxx） */
    private String licenseKey;

    /** License 密钥明文（分控持有，64位随机串，仅此一次返回，需写入 tenant.env） */
    private String licenseSecret;

    /** 商户 ID */
    private String merchantId;

    /** 商户名称（安装完成提示用） */
    private String merchantName;

    /** 总控地址（回传确认，安装器写入 tenant.env 的 LICENSE_MASTER_URL） */
    private String masterUrl;

    /** 商户数据 SQL（INSERT IGNORE 语句，安装器导入本地 MySQL） */
    private String merchantData;

    /** MySQL root 密码（总控管理员指定，安装时设置到分控 MySQL） */
    private String dbPassword;

    /** License 到期时间 */
    private String expireAt;

    /** 最大 Agent 数 */
    private Integer maxAgents;

    /** 最大并发任务数 */
    private Integer maxTasks;
}
