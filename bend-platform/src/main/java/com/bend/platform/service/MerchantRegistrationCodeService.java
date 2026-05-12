package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.MerchantRegistrationCodePageRequest;
import com.bend.platform.entity.MerchantRegistrationCode;
import java.util.List;

/**
 * 商户注册码服务接口
 */
public interface MerchantRegistrationCodeService {

    /**
     * 生成注册码
     *
     * @param merchantId 商户ID
     * @param count 生成数量
     * @return 注册码列表
     */
    List<String> generateCodes(String merchantId, int count);

    /**
     * 激活注册码（Agent激活时调用）
     *
     * @param code 注册码
     * @param agentId Agent实例ID
     * @param agentSecret Agent密钥
     * @return 激活结果，包含agentId和agentSecret
     */
    ActivationResult activateCode(String code, String agentId, String agentSecret);

    /**
     * 验证注册码（不激活）
     *
     * @param code 注册码
     * @return 注册码信息
     */
    MerchantRegistrationCode validateCode(String code);

    /**
     * 验证并消费注册码（一次性使用）
     * 验证成功后会将注册码状态改为已使用
     *
     * @param code 注册码
     * @return 激活结果，包含merchantId
     */
    ActivationResult validateAndConsume(String code);

    /**
     * 分页查询商户的注册码
     *
     * @param merchantId 商户ID
     * @param request 分页请求
     * @return 注册码分页列表
     */
    IPage<MerchantRegistrationCode> findByMerchantId(String merchantId, MerchantRegistrationCodePageRequest request);

    /**
     * 分页查询商户的注册码（带关键词搜索）
     *
     * @param merchantId 商户ID
     * @param keyword 关键词搜索（注册码）
     * @param request 分页请求
     * @return 注册码分页列表
     */
    IPage<MerchantRegistrationCode> findByMerchantId(String merchantId, String keyword, MerchantRegistrationCodePageRequest request);

    /**
     * 查询注册码详情
     *
     * @param code 注册码
     * @return 注册码信息
     */
    MerchantRegistrationCode findByCode(String code);

    /**
     * 删除注册码
     *
     * @param ids 注册码ID列表
     */
    void deleteByIds(List<String> ids);

    /**
     * 解绑注册码与Agent
     * 当Agent被卸载时调用，使注册码可以重新使用
     *
     * @param agentId Agent ID
     */
    void unbindByAgentId(String agentId);

    /**
     * 重置注册码状态
     * 解除注册码的绑定，使其可以重新使用
     *
     * @param id 注册码ID
     */
    void resetCode(String id);

    /**
     * 检查注册码激活失败次数是否超限
     * 用于防止暴力破解
     *
     * @param code 注册码
     * @return true=超限，false=未超限
     */
    boolean isExcessiveAttempts(String code);

    /**
     * 记录注册码激活失败
     * 用于限流
     *
     * @param code 注册码
     */
    void recordFailedAttempt(String code);

    /**
     * 激活结果（用于注册码验证）
     */
    class ActivationResult {
        private boolean success;
        private String merchantId;
        private String message;

        public static ActivationResult success(String merchantId) {
            ActivationResult result = new ActivationResult();
            result.success = true;
            result.merchantId = merchantId;
            return result;
        }

        public static ActivationResult failure(String message) {
            ActivationResult result = new ActivationResult();
            result.success = false;
            result.message = message;
            return result;
        }

        public boolean isSuccess() { return success; }
        public void setSuccess(boolean success) { this.success = success; }
        public String getMerchantId() { return merchantId; }
        public void setMerchantId(String merchantId) { this.merchantId = merchantId; }
        public String getMessage() { return message; }
        public void setMessage(String message) { this.message = message; }
    }
}
