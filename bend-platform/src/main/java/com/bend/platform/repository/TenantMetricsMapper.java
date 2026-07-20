package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.TenantMetrics;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface TenantMetricsMapper extends BaseMapper<TenantMetrics> {

    /** 查询某商户最近 N 条指标(趋势) */
    @Select("SELECT * FROM tenant_metrics WHERE merchant_id = #{merchantId} ORDER BY report_at DESC LIMIT #{limit}")
    List<TenantMetrics> selectRecentByMerchant(@Param("merchantId") String merchantId, @Param("limit") int limit);

    /** 查询每个商户的最新一条指标(大盘) */
    @Select("SELECT m.* FROM tenant_metrics m INNER JOIN " +
            "(SELECT merchant_id, MAX(report_at) AS max_at FROM tenant_metrics GROUP BY merchant_id) t " +
            "ON m.merchant_id = t.merchant_id AND m.report_at = t.max_at")
    List<TenantMetrics> selectLatestPerMerchant();
}
