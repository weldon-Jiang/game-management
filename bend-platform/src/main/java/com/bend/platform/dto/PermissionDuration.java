package com.bend.platform.dto;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;

/**
 * 使用权限套餐时长枚举。
 *
 * <p>管理员选套餐，后端算出到期日。续期时从当前到期日(已过期则从当前时间)往后加。
 * 前端下拉与后端校验共用此枚举的 code。
 */
public enum PermissionDuration {

    DAYS_30("30天", 30, ChronoUnit.DAYS),
    DAYS_90("90天", 90, ChronoUnit.DAYS),
    YEAR_1("1年", 1, ChronoUnit.YEARS);

    private final String label;
    private final long amount;
    private final ChronoUnit unit;

    PermissionDuration(String label, long amount, ChronoUnit unit) {
        this.label = label;
        this.amount = amount;
        this.unit = unit;
    }

    /** 从 base 时间往后加一个套餐时长 */
    public LocalDateTime plusFrom(LocalDateTime base) {
        return base.plus(amount, unit);
    }

    /** 容错解析：code 不匹配返回 null */
    public static PermissionDuration fromCode(String code) {
        if (code == null || code.isBlank()) {
            return null;
        }
        try {
            return PermissionDuration.valueOf(code.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    public String getLabel() { return label; }
    public long getAmount() { return amount; }
    public ChronoUnit getUnit() { return unit; }
}
