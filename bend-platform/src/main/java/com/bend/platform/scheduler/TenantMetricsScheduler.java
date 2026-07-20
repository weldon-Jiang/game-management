package com.bend.platform.scheduler;

import com.bend.platform.config.LicenseClientCondition;
import com.bend.platform.service.impl.TenantMetricsReporter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 分控汇总指标定时上报(默认每5分钟)
 */
@Slf4j
@Component
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class TenantMetricsScheduler {

    private final TenantMetricsReporter reporter;

    @Scheduled(fixedDelayString = "${license.metrics-interval-ms:300000}",
               initialDelayString = "${license.metrics-interval-ms:300000}")
    public void scheduledReport() {
        try {
            reporter.reportOnce();
        } catch (Exception e) {
            log.warn("定时指标上报异常: {}", e.getMessage());
        }
    }
}
