package com.bend.platform.dto;

import lombok.Data;

/**
 * License 签发结果 —— 返回给总控后台/打包脚本
 *
 * <p>licenseSecret 明文只在签发时返回一次,需安全保存并写入分控包配置。
 */
@Data
public class LicenseIssueResponse {

    private String id;

    private String merchantId;

    /** 商户名称（安装激活时展示用） */
    private String merchantName;

    private String licenseKey;

    /** license_secret 明文,仅签发时返回一次 */
    private String licenseSecret;

    private String status;

    private String expireAt;

    private Integer maxAgents;

    private Integer maxTasks;

    private String features;

    private Integer offlineGraceHours;
}
