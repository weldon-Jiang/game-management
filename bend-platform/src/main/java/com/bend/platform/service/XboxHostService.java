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
    XboxHost create(String merchantId, String xboxId, String name, String ipAddress, String platform);

    /**
     * 根据ID查询主机
     *
     * @param id 主机ID
     * @return 主机实体，不存在返回null
     */
    XboxHost findById(String id);

    /**
     * 按主键加载主机并校验商户归属（Agent 回调 / 内部调用，不依赖 JWT UserContext）。
     */
    XboxHost requireForMerchant(String hostId, String merchantId);

    /**
     * 按商户 + GSSV serverId 查询主机（商户隔离）。
     */
    XboxHost findByMerchantIdAndXboxId(String merchantId, String xboxId);

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
     * CAS 锁定主机（agentId + taskId）；返回是否成功。
     */
    boolean tryLock(String merchantId, String xboxHostId, String agentId, String taskId, int leaseSeconds);

    /**
     * 解锁主机（仅持有 agentId+taskId 可释放）。
     */
    boolean unlock(String merchantId, String xboxHostId, String agentId, String taskId);

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

    /**
     * 根据绑定的流媒体账号ID查询Xbox主机列表
     *
     * @param streamingAccountId 流媒体账号ID
     * @return Xbox主机列表
     */
    List<XboxHost> findByBoundStreamingAccountId(String streamingAccountId);

    /**
     * 根据IP地址查询主机
     *
     * @param ipAddress IP地址
     * @return 主机实体，不存在返回null
     */
    XboxHost findByIpAddress(String ipAddress);

    /**
     * 按商户 + IP 查询主机（商户隔离）。
     */
    XboxHost findByMerchantIdAndIpAddress(String merchantId, String ipAddress);

    /**
     * 创建或更新Xbox主机（用于发现功能）
     * 如果xboxId已存在则更新，否则创建新主机
     *
     * @param merchantId       商户ID
     * @param xboxId           Xbox主机ID
     * @param name             主机名称
     * @param ipAddress        IP地址
     * @param port             SmartGlass端口
     * @param liveId           Xbox Live ID
     * @param consoleType      主机型号
     * @param firmwareVersion  固件版本
     * @param macAddress       MAC地址
     * @return 创建或更新的主机实体
     */
    XboxHost createOrUpdate(String merchantId, String xboxId, String name, String ipAddress, 
                            Integer port, String liveId, String consoleType, 
                            String firmwareVersion, String macAddress, String platform);

    /**
     * 获取并失效凭证（一次性令牌）
     *
     * @param token 一次性令牌
     * @return 解密后的凭证，null表示令牌无效或已过期
     */
    String getAndInvalidateCredential(String token);
}