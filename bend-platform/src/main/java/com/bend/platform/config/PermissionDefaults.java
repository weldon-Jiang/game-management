package com.bend.platform.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 商户使用权限(Permission)默认值配置 —— 全局唯一来源。
 *
 * <p>散落于 InstallActivateService / PermissionServiceImpl / LicenseServiceImpl 的
 * 魔法数字(1年/5Agent/50任务/24h宽限)统一收敛到此，修改默认值只改 application.yml。
 */
@Data
@Component
@ConfigurationProperties(prefix = "bend.permission")
public class PermissionDefaults {

    /** 兜底默认有效期(年) */
    private int defaultExpireYears = 1;

    /** 兜底默认最大 Agent 数 */
    private int defaultMaxAgents = 5;

    /** 兜底默认最大并发任务数 */
    private int defaultMaxTasks = 50;

    /** 兜底默认离线宽限小时数 */
    private int defaultOfflineGraceHours = 24;
}
