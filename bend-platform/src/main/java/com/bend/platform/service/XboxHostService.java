package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.XboxHostPageRequest;
import com.bend.platform.entity.XboxHost;

import java.util.List;

/**
 * Xbox主机服务接口
 * 定义Xbox主机相关的业务操作
 */
public interface XboxHostService {

    /**
     * 创建Xbox主机
     *
     * @param merchantId 商户ID
     * @param xboxId    Xbox主机ID
     * @param name      主机名称
     * @param ipAddress IP地址（可选）
     * @return 创建的主机实体
     */
    XboxHost create(String merchantId, String xboxId, String name, String ipAddress);

    /**
     * 根据ID查询主机
     *
     * @param id 主机ID
     * @return 主机实体，不存在返回null
     */
    XboxHost findById(String id);

    /**
     * 根据XboxID查询主机
     *
     * @param xboxId Xbox主机ID
     * @return 主机实体，不存在返回null
     */
    XboxHost findByXboxId(String xboxId);

    /**
     * 分页查询商户下的Xbox主机
     *
     * @param merchantId 商户ID
     * @param request     分页请求参数
     * @return 分页结果
     */
    IPage<XboxHost> findByMerchantId(String merchantId, XboxHostPageRequest request);

    /**
     * 查询商户下的所有Xbox主机
     *
     * @param merchantId 商户ID
     * @return 主机列表
     */
    List<XboxHost> findAllByMerchantId(String merchantId);

    /**
     * 更新主机信息
     *
     * @param id        主机ID
     * @param name      新名称（可选）
     * @param ipAddress 新IP地址（可选）
     */
    void update(String id, String name, String ipAddress);

    /**
     * 更新主机状态
     *
     * @param id     主机ID
     * @param status 新状态 (online/offline/error)
     */
    void updateStatus(String id, String status);

    /**
     * 绑定流媒体账号
     *
     * @param id                  主机ID
     * @param streamingAccountId 流媒体账号ID
     * @param gamertag           Gamertag
     */
    void bindStreamingAccount(String id, String streamingAccountId, String gamertag);

    /**
     * 解绑流媒体账号
     *
     * @param id 主机ID
     */
    void unbindStreamingAccount(String id);

    /**
     * 锁定主机
     *
     * @param id         主机ID
     * @param agentId    Agent实例ID
     * @param expireTime 锁定过期时间
     */
    void lock(String id, String agentId, java.time.LocalDateTime expireTime);

    /**
     * 解锁主机
     *
     * @param id 主机ID
     */
    void unlock(String id);

    /**
     * 删除主机
     *
     * @param id 主机ID
     */
    void delete(String id);

    /**
     * 获取Xbox主机可用的流媒体账号列表（已登录过的）
     *
     * @param id Xbox主机ID
     * @return 可用的流媒体账号ID列表
     */
    List<String> getAvailableStreamingAccounts(String id);
}