package com.bend.platform.controller;

import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.TenantMetricsReport;
import com.bend.platform.dto.TenantStatusVo;
import com.bend.platform.entity.TenantMetrics;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.TenantMetricsService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 分控指标 Controller(总控侧)
 *
 * <p>POST /api/tenant-metrics/report: 分控上报(公开,license 鉴权,不走 JWT)
 * <p>GET  /api/tenant-metrics:       大盘,查询各分控最新指标(平台管理员)
 * <p>GET  /api/tenant-metrics/{merchantId}: 某商户指标趋势
 */
@RestController
@RequestMapping("/api/tenant-metrics")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class TenantMetricsController {

    private final TenantMetricsService metricsService;

    @PostMapping("/report")
    public ApiResponse<Void> report(@RequestBody TenantMetricsReport report) {
        if (report.getLicenseKey() == null || report.getLicenseSecret() == null) {
            throw new BusinessException(ResultCode.System.BAD_REQUEST);
        }
        boolean ok = metricsService.report(report);
        if (!ok) {
            return ApiResponse.error(401, "分控鉴权失败");
        }
        return ApiResponse.success("上报成功", null);
    }

    @GetMapping
    public ApiResponse<List<TenantMetrics>> latestPerMerchant() {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(metricsService.latestPerMerchant());
    }

    /**
     * 各分控在线状态(总控监控大盘)。
     * 在线判断:分控最近一次出站活动(license校验/指标上报)距今 <= 阈值(默认15min)。
     */
    @GetMapping("/status")
    public ApiResponse<List<TenantStatusVo>> status() {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(metricsService.listStatus());
    }

    @GetMapping("/{merchantId}")
    public ApiResponse<List<TenantMetrics>> recent(@PathVariable String merchantId,
                                                    @RequestParam(defaultValue = "100") int limit) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        return ApiResponse.success(metricsService.recentByMerchant(merchantId, limit));
    }
}
