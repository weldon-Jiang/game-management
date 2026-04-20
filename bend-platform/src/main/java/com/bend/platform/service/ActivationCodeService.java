package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ActivationCodeBatchCodesPageRequest;
import com.bend.platform.dto.ActivationCodeBatchPageRequest;
import com.bend.platform.dto.ActivationCodePageRequest;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import java.util.List;

/**
 * 激活码服务接口
 */
public interface ActivationCodeService {

    /**
     * 生成激活码批次
     *
     * @param merchantId  商户ID
     * @param batchName  批次名称
     * @param vipType    VIP类型
     * @param count      生成数量
     * @param expireTime 过期时间
     * @return 批次信息
     */
    ActivationCodeBatch generateBatch(String merchantId, String batchName, String vipType, int count, java.time.LocalDateTime expireTime);

    /**
     * 根据ID查询激活码
     */
    ActivationCode findById(String id);

    /**
     * 根据激活码查询
     */
    ActivationCode findByCode(String code);

    /**
     * 使用激活码
     *
     * @param code   激活码
     * @param userId 使用者ID
     * @return 使用后的激活码信息
     */
    ActivationCode useCode(String code, String userId);

    /**
     * 查询批次的激活码列表
     *
     * @param batchId 批次ID
     * @param request 分页请求参数
     * @return 激活码分页列表
     */
    IPage<ActivationCode> findByBatchId(String batchId, ActivationCodeBatchCodesPageRequest request);

    /**
     * 查询商户的所有批次
     */
    List<ActivationCodeBatch> findAllBatchesByMerchantId(String merchantId);

    /**
     * 分页查询批次
     *
     * @param merchantId 商户ID
     * @param request     分页请求参数
     * @return 批次分页列表
     */
    IPage<ActivationCodeBatch> findBatchesByMerchantId(String merchantId, ActivationCodeBatchPageRequest request);

    /**
     * 查询批次详情
     */
    ActivationCodeBatch findBatchById(String batchId);

    /**
     * 分页查询商户的激活码列表
     *
     * @param merchantId 商户ID
     * @param request     分页请求参数
     * @return 激活码分页列表
     */
    IPage<ActivationCode> findByMerchantId(String merchantId, ActivationCodePageRequest request);

    /**
     * 分页查询商户的激活码列表（带关键词搜索）
     *
     * @param merchantId 商户ID
     * @param keyword     关键词搜索
     * @param request     分页请求参数
     * @return 激活码分页列表
     */
    IPage<ActivationCode> findByMerchantId(String merchantId, String keyword, ActivationCodePageRequest request);

    /**
     * 批量删除激活码
     *
     * @param ids 激活码ID列表
     */
    void deleteByIds(List<String> ids);
}