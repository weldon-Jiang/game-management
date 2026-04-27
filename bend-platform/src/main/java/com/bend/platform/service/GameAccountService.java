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

    GameAccount findByGamertag(String gamertag);

    IPage<GameAccount> findByMerchantId(String merchantId, GameAccountPageRequest request);

    IPage<GameAccount> findByStreamingId(String streamingId, GameAccountPageRequest request);

    List<GameAccount> findAllByStreamingId(String streamingId);

    IPage<GameAccount> findAll(GameAccountPageRequest request);

    List<GameAccount> findUnboundByMerchantId(String merchantId);

    void update(String id, GameAccount account);

    void bindToStreamingAccount(String streamingAccountId, List<String> gameAccountIds);

    void unbindFromStreamingAccount(List<String> gameAccountIds);

    void lock(String id, String xboxHostId);

    void unlock(String id);

    void setPrimary(String id, boolean primary);

    void delete(String id);

    void updateAgentId(String id, String agentId);

    List<GameAccount> findByStreamingId(String streamingId);
}