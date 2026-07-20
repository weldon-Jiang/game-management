package com.bend.platform.service;

import com.bend.platform.dto.TenantMetricsReport;
import com.bend.platform.dto.TenantStatusVo;
import com.bend.platform.entity.TenantMetrics;

import java.util.List;

/**
 * 分控汇总指标服务(总控侧)
 */
public interface TenantMetricsService {

    /**
     * 接收分控上报(用 licenseKey+secret 鉴权)。
     * 鉴权失败返回 false。
     */
    boolean report(TenantMetricsReport report);

    /** 查询某商户最近 N 条指标 */
    List<TenantMetrics> recentByMerchant(String merchantId, int limit);

    /** 查询每个商户最新一条指标(大盘) */
    List<TenantMetrics> latestPerMerchant();

    /** 查询各分控在线状态(总控大盘) */
    List<TenantStatusVo> listStatus();
}
