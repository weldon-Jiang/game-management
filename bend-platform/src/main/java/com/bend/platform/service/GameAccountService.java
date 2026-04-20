package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.GameAccountPageRequest;
import com.bend.platform.entity.GameAccount;

import java.util.List;

/**
 * 游戏账号服务接口
 */
public interface GameAccountService {

    GameAccount create(String merchantId, GameAccount account);

    GameAccount findById(String id);

    GameAccount findByGamertag(String gamertag);

    IPage<GameAccount> findByMerchantId(String merchantId, GameAccountPageRequest request);

    IPage<GameAccount> findByStreamingId(String streamingId, GameAccountPageRequest request);

    List<GameAccount> findAllByStreamingId(String streamingId);

    IPage<GameAccount> findAll(GameAccountPageRequest request);

    void update(String id, GameAccount account);

    void lock(String id, String xboxHostId);

    void unlock(String id);

    void setPrimary(String id, boolean primary);

    void delete(String id);

    void updateAgentId(String id, String agentId);

    List<GameAccount> findByStreamingId(String streamingId);
}