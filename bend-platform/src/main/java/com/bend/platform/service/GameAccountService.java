package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.GameAccountImportDto;
import com.bend.platform.dto.GameAccountPageRequest;
import com.bend.platform.dto.ImportResultDto;
import com.bend.platform.entity.GameAccount;

import java.util.List;

public interface GameAccountService {

    GameAccount create(String merchantId, GameAccount account);

    ImportResultDto batchImport(String merchantId, List<GameAccountImportDto> accounts);

    GameAccount findById(String id);

    /**
     * 按主键加载游戏账号并校验商户归属（Agent 回调，不依赖 JWT UserContext）。
     */
    GameAccount requireForMerchant(String gameAccountId, String merchantId);

    GameAccount findByGamertag(String gamertag);

    IPage<GameAccount> findByMerchantId(String merchantId, GameAccountPageRequest request);

    IPage<GameAccount> findByStreamingId(String streamingId, GameAccountPageRequest request);

    List<GameAccount> findAllByStreamingId(String streamingId);

    IPage<GameAccount> findAll(GameAccountPageRequest request);

    List<GameAccount> findUnboundByMerchantId(String merchantId, String platform);

    void update(String id, GameAccount account);

    void bindToStreamingAccount(String streamingAccountId, List<String> gameAccountIds);

    void unbindFromStreamingAccount(List<String> gameAccountIds);

    void disable(String id);

    void enable(String id);

    void setPrimary(String id, boolean primary);

    void delete(String id);

    void updateAgentId(String id, String agentId);

    /**
     * 更新账号状态（忙碌/空闲）
     *
     * @param id     账号ID
     * @param status 状态 (idle/busy)
     */
    void updateStatus(String id, String status);

    /**
     * Agent callback: persist console profile binding after successful login/switch.
     */
    void updateProfileBinding(String id, Boolean profileBound, Integer positionIndex, String gameName);

    /**
     * 清除串流账号下所有游戏账号的 Agent 绑定，并置为 idle。
     */
    void clearAgentIdByStreamingId(String streamingId);

    /**
     * 清除指定 Agent 关联的所有游戏账号绑定（含串流账号 agent_id 已清但游戏账号残留的兜底）。
     */
    void clearAgentBindingByAgentId(String agentId);

    List<GameAccount> findByStreamingId(String streamingId);

    /**
     * 根据流媒体账号ID查询绑定的游戏账号（保留密码信息）
     */
    List<GameAccount> findByStreamingIdWithCredentials(String streamingId);
}