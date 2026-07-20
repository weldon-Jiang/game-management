package com.bend.platform.scheduler;

import com.bend.platform.config.LicenseClientCondition;
import com.bend.platform.service.LicenseClientService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 分控 License 定时校验
 *
 * <p>每 30 分钟(可配)向总控刷新一次校验结果。
 * 仅 tenant 模式装配。启动时的首次校验由 LicenseClientServiceImpl.init() 完成。
 */
@Slf4j
@Component
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class LicenseVerifyScheduler {

    private final LicenseClientService licenseClientService;

    /**
     * 每 license.verify-interval-ms(默认1800000=30min)刷新一次。
     * 在 application.yml 中 license.verify-interval-ms 可覆盖。
     */
    @Scheduled(fixedDelayString = "${license.verify-interval-ms:1800000}", initialDelayString = "${license.verify-interval-ms:1800000}")
    public void scheduledVerify() {
        try {
            boolean ok = licenseClientService.verifyNow();
            log.info("定时License校验完成 authorized={}", ok);
        } catch (Exception e) {
            log.warn("定时License校验异常: {}", e.getMessage());
        }
    }
}
