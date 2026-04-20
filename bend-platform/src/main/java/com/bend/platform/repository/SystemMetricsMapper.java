package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.SystemMetrics;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 系统指标Mapper
 */
@Mapper
public interface SystemMetricsMapper extends BaseMapper<SystemMetrics> {

    /**
     * 查询指标趋势
     *
     * 功能说明：
     * - 查询指定指标在指定时间段内的历史数据
     * - 用于绘制监控图表
     *
     * 参数说明：
     * - metricName: 指标名称
     * - startTime: 开始时间
     *
     * 返回值：指标历史列表
     */
    @Select("SELECT * FROM system_metrics " +
            "WHERE metric_name = #{metricName} " +
            "AND recorded_at >= #{startTime} " +
            "ORDER BY recorded_at ASC")
    List<SystemMetrics> selectTrend(@Param("metricName") String metricName,
                                     @Param("startTime") LocalDateTime startTime);

    /**
     * 查询最近的指标数据
     *
     * 参数说明：
     * - metricType: 指标类型
     * - limit: 返回数量
     *
     * 返回值：指标列表
     */
    @Select("SELECT * FROM system_metrics " +
            "WHERE metric_type = #{metricType} " +
            "ORDER BY recorded_at DESC LIMIT #{limit}")
    List<SystemMetrics> selectRecentByType(@Param("metricType") String metricType,
                                           @Param("limit") int limit);
}
