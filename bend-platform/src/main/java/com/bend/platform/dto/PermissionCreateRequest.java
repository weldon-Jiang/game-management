package com.bend.platform.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 创建/更新商户使用权限请求
 *
 * <p>有效期两种指定方式（二选一，duration 优先）:
 * <ul>
 *   <li>{@code duration}：套餐码（DAYS_30/DAYS_90/YEAR_1），后端算出到期日</li>
 *   <li>{@code expireAt}：直接指定到期时间（自定义日期兜底）</li>
 * </ul>
 * <p>两者都空且为新建时，用 {@code bend.permission.default-expire-years} 兜底。
 */
@Data
public class PermissionCreateRequest {

    /** 商户ID */
    private String merchantId;

    /** 套餐时长码（与 expireAt 二选一，优先）：DAYS_30 / DAYS_90 / YEAR_1 */
    private String duration;

    /** 到期时间（与 duration 二选一） */
    private LocalDateTime expireAt;

    /** 最大Agent数量，空则取默认 */
    private Integer maxAgents;

    /** 最大并发任务数，空则取默认 */
    private Integer maxTasks;

    /** 功能特性JSON */
    private String features;

    /** 离线宽限小时数，空则取默认 */
    private Integer offlineGraceHours;
}
