package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ImportResultDto;
import com.bend.platform.dto.StreamingAccountImportDto;
import com.bend.platform.dto.StreamingAccountPageRequest;
import com.bend.platform.entity.StreamingAccount;

import java.util.List;

/**
 * 流媒体账号服务接口
 * 定义流媒体账号相关的业务操作
 */
public interface StreamingAccountService {

    /**
     * 创建流媒体账号
     *
     * @param merchantId 商户ID
     * @param name       账号名称
     * @param email      邮箱
     * @param password   密码（加密存储）
     * @param authCode   认证码（可选）
     * @return 创建的账号实体
     */
    StreamingAccount create(String merchantId, String name, String email, String password, String authCode);

    /**
     * 批量导入流媒体账号
     *
     * @param merchantId 商户ID
     * @param accounts   导入的账号列表
     * @return 导入结果
     */
    ImportResultDto batchImport(String merchantId, List<StreamingAccountImportDto> accounts);

    /**
     * 根据ID查询账号
     *
     * @param id 账号ID
     * @return 账号实体，不存在返回null
     */
    StreamingAccount findById(String id);

    /**
     * 根据邮箱查询账号
     *
     * @param email 邮箱
     * @return 账号实体，不存在返回null
     */
    StreamingAccount findByEmail(String email);

    /**
     * 分页查询商户下的流媒体账号
     *
     * @param merchantId 商户ID
     * @param request     分页请求参数
     * @return 分页结果
     */
    IPage<StreamingAccount> findByMerchantId(String merchantId, StreamingAccountPageRequest request);

    /**
     * 查询商户下的所有流媒体账号
     *
     * @param merchantId 商户ID
     * @return 账号列表
     */
    List<StreamingAccount> findAllByMerchantId(String merchantId);

    /**
     * 更新账号信息
     *
     * @param id       账号ID
     * @param name     新名称（可选）
     * @param authCode 新认证码（可选）
     */
    void update(String id, String name, String authCode);

    /**
     * 更新账号信息（管理员用）
     *
     * @param id         账号ID
     * @param merchantId 新商户ID（可选）
     * @param name       新名称（可选）
     * @param authCode   新认证码（可选）
     */
    void update(String id, String merchantId, String name, String authCode);

    /**
     * 更新账号状态
     *
     * @param id     账号ID
     * @param status 新状态 (idle/busy/error)
     */
    void updateStatus(String id, String status);

    /**
     * 更新账号错误信息
     *
     * @param id            账号ID
     * @param errorCode     错误码
     * @param errorMessage 错误信息
     */
    void updateError(String id, String errorCode, String errorMessage);

    /**
     * 更新心跳时间
     *
     * @param id 账号ID
     */
    void updateHeartbeat(String id);

    /**
     * 删除账号
     *
     * @param id 账号ID
     */
    void delete(String id);

    /**
     * 更新账号绑定的Agent ID
     *
     * @param id      账号ID
     * @param agentId Agent ID（为null表示解除绑定）
     */
    void updateAgentId(String id, String agentId);

    /**
     * 查询账号关联的Agent是否在线
     *
     * @param id 账号ID
     * @return true if agent is online
     */
    boolean isAgentOnline(String id);
}