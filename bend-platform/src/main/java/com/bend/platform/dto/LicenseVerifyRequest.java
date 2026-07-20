package com.bend.platform.dto;

import lombok.Data;

/**
 * 分控向总控发起的 License 校验请求
 *
 * <p>分控每次启动 + 每30分钟携带本信息请求总控 /api/licenses/verify。
 */
@Data
public class LicenseVerifyRequest {

    /** 授权密钥 */
    private String licenseKey;

    /** 授权密钥明文(证明持有者身份) */
    private String licenseSecret;

    /** 当前机器指纹(用于首次激活绑定或后续校验一致性) */
    private String machineFingerprint;

    /** 当前分控版本号,可选(用于总控统计) */
    private String platformVersion;
}
