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
            "AND recorded_time >= #{startTime} " +
            "ORDER BY recorded_time ASC")
    List<SystemMetrics> selectTrend(@Param("metricName") String metricName,
                                     @Param("startTime") LocalDateTime startTime);

    /**
     * 限量查询指标趋势。
     *
     * 功能说明：
     * - 从最近数据中取固定数量的点，避免监控页面查询长时间范围时拉取过多记录
     * - 外层按时间正序返回，便于前端直接渲染
     *
     * 参数说明：
     * - metricName: 指标名称
     * - startTime: 开始时间
     * - limit: 最大返回数量
     *
     * 返回值：指标历史列表
     */
    @Select("SELECT * FROM (" +
            "SELECT * FROM system_metrics " +
            "WHERE metric_name = #{metricName} " +
            "AND recorded_time >= #{startTime} " +
            "ORDER BY recorded_time DESC LIMIT #{limit}" +
            ") recent_metrics ORDER BY recorded_time ASC")
    List<SystemMetrics> selectTrendLimited(@Param("metricName") String metricName,
                                           @Param("startTime") LocalDateTime startTime,
                                           @Param("limit") int limit);

    /**
     * 按类型和名称限量查询指标趋势。
     *
     * 参数说明：
     * - metricType: 指标类型
     * - metricName: 指标名称
     * - startTime: 开始时间
     * - limit: 最大返回数量
     *
     * 返回值：指标历史列表
     */
    @Select("SELECT * FROM (" +
            "SELECT * FROM system_metrics " +
            "WHERE metric_type = #{metricType} " +
            "AND metric_name = #{metricName} " +
            "AND recorded_time >= #{startTime} " +
            "ORDER BY recorded_time DESC LIMIT #{limit}" +
            ") recent_metrics ORDER BY recorded_time ASC")
    List<SystemMetrics> selectTrendLimitedByType(@Param("metricType") String metricType,
                                                 @Param("metricName") String metricName,
                                                 @Param("startTime") LocalDateTime startTime,
                                                 @Param("limit") int limit);

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
            "ORDER BY recorded_time DESC LIMIT #{limit}")
    List<SystemMetrics> selectRecentByType(@Param("metricType") String metricType,
                                           @Param("limit") int limit);
}
