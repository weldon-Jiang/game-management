package com.bend.platform.util;

import com.bend.platform.enums.PlatformType;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;

/**
 * Helpers for platform type validation across services.
 */
public final class PlatformTypeUtil {

    private PlatformTypeUtil() {
    }

    public static String normalizeOrDefault(String platform) {
        return PlatformType.normalizeOrDefault(platform);
    }

    public static String requireValid(String platform) {
        PlatformType type = PlatformType.fromCode(platform);
        if (type == null) {
            throw new BusinessException(ResultCode.System.INVALID_PLATFORM);
        }
        return type.getCode();
    }

    public static void requireSamePlatform(String left, String right, String context) {
        String normalizedLeft = normalizeOrDefault(left);
        String normalizedRight = normalizeOrDefault(right);
        if (!normalizedLeft.equals(normalizedRight)) {
            throw new BusinessException(ResultCode.System.PLATFORM_MISMATCH, context);
        }
    }
}
