package com.bend.platform.service;

import com.bend.platform.dto.StartAutomationRequest;

import java.util.Map;

/**
 * 自动化服务接口
 *
 * <p>提供Xbox自动化任务的完整管理功能，包括启动、停止、状态查询等。
 *
 * <p>核心功能：
 * <ul>
 *   <li>启动自动化：为流媒体账号创建自动化任务并分配给Agent执行</li>
 *   <li>停止自动化：停止指定账号的自动化任务</li>
 *   <li>状态查询：获取自动化任务执行状态</li>
 * </ul>
 *
 * <p>安全特性：
 * <ul>
 *   <li>商户隔离：所有操作校验商户归属</li>
 *   <li>凭证安全：密码通过一次性令牌传输，不直接暴露</li>
 *   <li>状态机控制：任务状态转换受状态机校验</li>
 * </ul>
 *
 * @see com.bend.platform.service.impl.AutomationServiceImpl
 */
public interface AutomationService {

    /**
     * 启动自动化任务
     *
     * <p>为指定的流媒体账号创建自动化任务，并分配给在线的Agent执行。
     *
     * <p>处理流程：
     * <ol>
     *   <li>校验Agent在线状态</li>
     *   <li>校验流媒体账号归属当前商户</li>
     *   <li>构建任务参数（含凭证令牌而非明文密码）</li>
     *   <li>创建任务并发送WebSocket消息通知Agent</li>
     *   <li>更新流媒体账号和游戏账号的Agent关联</li>
     * </ol>
     *
     * <p>凭证传递机制：
     * <ul>
     *   <li>流媒体账号密码通过 CredentialTokenService 生成一次性令牌</li>
     *   <li>游戏账号Xbox密码同样使用令牌机制</li>
     *   <li>令牌有效期5分钟，一次使用后失效</li>
     * </ul>
     *
     * @param request 自动化请求（含流媒体账号列表、AgentID、任务类型等）
     * @param userId 当前操作用户ID
     * @param merchantId 当前用户所属商户ID
     * @return 操作结果（含创建的任务数、任务ID列表、每个账号的处理详情）
     * @throws BusinessException Agent不在线或账号不存在
     */
    Map<String, Object> startAutomation(StartAutomationRequest request, String userId, String merchantId);

    /**
     * 停止自动化任务
     *
     * <p>停止指定流媒体账号的自动化执行，包括：
     * <ul>
     *   <li>向Agent发送停止指令</li>
     *   <li>解除流媒体账号与Agent的关联</li>
     *   <li>取消该账号下所有待处理任务</li>
     * </ul>
     *
     * @param streamingAccountId 流媒体账号ID
     * @param merchantId 当前用户所属商户ID（用于归属校验）
     * @throws BusinessException 账号不存在或无权访问
     */
    void stopAutomation(String streamingAccountId, String merchantId);

    /**
     * 获取自动化状态
     *
     * <p>查询指定流媒体账号的自动化执行状态，包括：
     * <ul>
     *   <li>关联的Agent信息</li>
     *   <li>Agent在线状态</li>
     *   <li>当前账号状态</li>
     *   <li>最近的任务列表</li>
     * </ul>
     *
     * @param streamingAccountId 流媒体账号ID
     * @param merchantId 当前用户所属商户ID
     * @return 自动化状态详情
     * @throws BusinessException 账号不存在或无权访问
     */
    Map<String, Object> getAutomationStatus(String streamingAccountId, String merchantId);
}