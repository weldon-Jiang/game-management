package com.bend.platform.service;

import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.repository.XboxHostMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 商户资源归属校验服务
 *
 * <p>提供商户数据隔离的校验功能，确保商户只能访问属于自己的资源。
 *
 * <p>核心功能：
 * <ul>
 *   <li>流媒体账号归属校验</li>
 *   <li>游戏账号归属校验（通过上级流媒体账号间接校验）</li>
 *   <li>Xbox主机归属校验</li>
 *   <li>商户间资源访问校验</li>
 * </ul>
 *
 * <p>校验失败处理：
 * <ul>
 *   <li>抛出 BusinessException</li>
 *   <li>错误码：PERMISSION_DENIED</li>
 *   <li>记录警告日志</li>
 * </ul>
 *
 * <p>使用场景：
 * <ul>
 *   <li>Controller 层在执行敏感操作前校验</li>
 *   <li>Service 层跨商户操作前校验</li>
 *   <li>数据查询时过滤不属于当前商户的数据</li>
 * </ul>
 *
 * @see com.bend.platform.exception.ResultCode
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantOwnershipService {

    private final MerchantMapper merchantMapper;
    private final StreamingAccountMapper streamingAccountMapper;
    private final GameAccountMapper gameAccountMapper;
    private final XboxHostMapper xboxHostMapper;

    /**
     * 校验商户对流媒体账号的访问权限
     *
     * <p>验证指定商户是否有权访问该流媒体账号。
     * 用于在操作流媒体账号前进行权限校验。
     *
     * <p>校验规则：
     * <ul>
     *   <li>账号必须存在</li>
     *   <li>账号的 merchantId 必须与给定 merchantId 匹配</li>
     * </ul>
     *
     * @param streamingAccountId 流媒体账号ID
     * @param merchantId 要校验的商户ID
     * @throws BusinessException 账号不存在或无权访问
     */
    public void validateStreamingAccountOwnership(String streamingAccountId, String merchantId) {
        StreamingAccount account = streamingAccountMapper.selectById(streamingAccountId);
        if (account == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }
        if (!merchantId.equals(account.getMerchantId())) {
            log.warn("商户无权访问流媒体账号 - merchantId: {}, streamingAccountId: {}",
                merchantId, streamingAccountId);
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }

    /**
     * 校验商户对游戏账号的访问权限
     *
     * <p>游戏账号的归属通过其关联的流媒体账号间接确定。
     * 只有商户拥有该游戏账号所属的流媒体账号时，才有权访问。
     *
     * <p>校验规则：
     * <ul>
     *   <li>游戏账号必须存在</li>
     *   <li>关联的流媒体账号必须存在</li>
     *   <li>流媒体账号的 merchantId 必须与给定 merchantId 匹配</li>
     * </ul>
     *
     * @param gameAccountId 游戏账号ID
     * @param merchantId 要校验的商户ID
     * @throws BusinessException 账号不存在或无权访问
     */
    public void validateGameAccountOwnership(String gameAccountId, String merchantId) {
        GameAccount account = gameAccountMapper.selectById(gameAccountId);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        StreamingAccount streamingAccount = streamingAccountMapper.selectById(account.getStreamingId());
        if (streamingAccount == null || !merchantId.equals(streamingAccount.getMerchantId())) {
            log.warn("商户无权访问游戏账号 - merchantId: {}, gameAccountId: {}",
                merchantId, gameAccountId);
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }

    /**
     * 校验商户对Xbox主机的访问权限
     *
     * <p>验证指定商户是否有权访问该Xbox主机。
     *
     * <p>校验规则：
     * <ul>
     *   <li>主机必须存在</li>
     *   <li>主机的 merchantId 必须与给定 merchantId 匹配</li>
     * </ul>
     *
     * @param xboxHostId Xbox主机ID
     * @param merchantId 要校验的商户ID
     * @throws BusinessException 主机不存在或无权访问
     */
    public void validateXboxHostOwnership(String xboxHostId, String merchantId) {
        XboxHost host = xboxHostMapper.selectById(xboxHostId);
        if (host == null) {
            throw new BusinessException(ResultCode.XboxHost.NOT_FOUND);
        }
        if (!merchantId.equals(host.getMerchantId())) {
            log.warn("商户无权访问Xbox主机 - merchantId: {}, xboxHostId: {}",
                merchantId, xboxHostId);
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }

    /**
     * 校验商户间资源访问权限
     *
     * <p>验证两个商户ID是否相同，用于跨商户操作前的校验。
     *
     * @param merchantId 当前商户ID
     * @param targetMerchantId 目标商户ID
     * @throws BusinessException 商户ID不匹配，无权访问
     */
    public void validateMerchantOwnership(String merchantId, String targetMerchantId) {
        if (!merchantId.equals(targetMerchantId)) {
            log.warn("商户无权访问目标商户资源 - merchantId: {}, targetMerchantId: {}",
                merchantId, targetMerchantId);
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }

    /**
     * 检查流媒体账号是否属于指定商户
     *
     * <p>与 validateStreamingAccountOwnership 不同，此方法只返回校验结果，
     * 不抛出异常，适用于不需要中断流程的场景。
     *
     * @param streamingAccountId 流媒体账号ID
     * @param merchantId 商户ID
     * @return true 表示属于该商户，false 表示不属于或账号不存在
     */
    public boolean isStreamingAccountOwnedBy(String streamingAccountId, String merchantId) {
        StreamingAccount account = streamingAccountMapper.selectById(streamingAccountId);
        return account != null && merchantId.equals(account.getMerchantId());
    }

    /**
     * 检查Xbox主机是否属于指定商户
     *
     * @param xboxHostId Xbox主机ID
     * @param merchantId 商户ID
     * @return true 表示属于该商户，false 表示不属于或主机不存在
     */
    public boolean isXboxHostOwnedBy(String xboxHostId, String merchantId) {
        XboxHost host = xboxHostMapper.selectById(xboxHostId);
        return host != null && merchantId.equals(host.getMerchantId());
    }

    /**
     * 获取流媒体账号所属商户ID
     *
     * @param streamingAccountId 流媒体账号ID
     * @return 商户ID，账号不存在返回 null
     */
    public String getMerchantIdByStreamingAccount(String streamingAccountId) {
        StreamingAccount account = streamingAccountMapper.selectById(streamingAccountId);
        return account != null ? account.getMerchantId() : null;
    }

    /**
     * 获取Xbox主机所属商户ID
     *
     * @param xboxHostId Xbox主机ID
     * @return 商户ID，主机不存在返回 null
     */
    public String getMerchantIdByXboxHost(String xboxHostId) {
        XboxHost host = xboxHostMapper.selectById(xboxHostId);
        return host != null ? host.getMerchantId() : null;
    }
}