package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.GameAccountImportDto;
import com.bend.platform.dto.GameAccountPageRequest;
import com.bend.platform.dto.ImportResultDto;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.StreamingAccount;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.StreamingAccountMapper;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.util.AesUtil;
import com.bend.platform.util.DataSecurityUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 游戏账号服务实现类
 *
 * 功能说明：
 * - 管理Xbox游戏账号的CRUD操作
 * - 游戏账号关联到流媒体账号
 *
 * 主要功能：
 * - 创建游戏账号
 * - 分页查询游戏账号
 * - 根据流媒体账号ID查询游戏账号
 * - 更新游戏账号信息
 * - 删除游戏账号
 * - 批量更新游戏账号的AgentID
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class GameAccountServiceImpl implements GameAccountService {

    private final GameAccountMapper gameAccountMapper;
    private final StreamingAccountMapper streamingAccountMapper;
    private final MerchantMapper merchantMapper;
    private final DataSecurityUtil dataSecurityUtil;
    private final AesUtil aesUtil;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public GameAccount create(String merchantId, GameAccount account) {
        StreamingAccount streaming = streamingAccountMapper.selectById(account.getStreamingId());
        if (streaming == null) {
            throw new BusinessException(ResultCode.StreamingAccount.NOT_FOUND);
        }
        if (!streaming.getMerchantId().equals(merchantId)) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }

        GameAccount entity = new GameAccount();
        entity.setMerchantId(merchantId);
        entity.setStreamingId(account.getStreamingId());
        entity.setXboxGameName(account.getXboxGameName());
        entity.setXboxLiveEmail(account.getXboxLiveEmail());
        if (account.getXboxLivePasswordEncrypted() != null) {
            entity.setXboxLivePasswordEncrypted(aesUtil.encrypt(account.getXboxLivePasswordEncrypted()));
        }
        entity.setIsActive(true);
        entity.setIsPrimary(false);
        entity.setCreatedTime(LocalDateTime.now());
        entity.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.insert(entity);
        log.info("创建游戏账号成功 - ID: {}, 名称: {}", entity.getId(), entity.getXboxGameName());
        return entity;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ImportResultDto batchImport(String merchantId, List<GameAccountImportDto> accounts) {
        ImportResultDto result = new ImportResultDto();
        List<String> errors = new ArrayList<>();
        int successCount = 0;

        if (CollectionUtils.isEmpty(accounts)) {
            errors.add("导入数据不能为空");
            result.setFailCount(accounts.size());
            result.setErrors(errors);
            return result;
        }

        Set<String> gamertagSet = new HashSet<>();
        for (int i = 0; i < accounts.size(); i++) {
            GameAccountImportDto dto = accounts.get(i);
            int rowNum = i + 2;

            if (gamertagSet.contains(dto.getXboxGameName())) {
                errors.add(String.format("第%d行: Xbox玩家名称[%s]重复", rowNum, dto.getXboxGameName()));
                continue;
            }

            GameAccount existing = findByGamertag(dto.getXboxGameName());
            if (existing != null) {
                errors.add(String.format("第%d行: Xbox玩家名称[%s]已存在", rowNum, dto.getXboxGameName()));
                continue;
            }

            gamertagSet.add(dto.getXboxGameName());
        }

        if (!errors.isEmpty()) {
            result.setSuccessCount(0);
            result.setFailCount(accounts.size());
            result.setErrors(errors);
            return result;
        }

        for (GameAccountImportDto dto : accounts) {
            try {
                GameAccount entity = new GameAccount();
                entity.setMerchantId(merchantId);
                entity.setXboxGameName(dto.getXboxGameName());
                entity.setXboxLiveEmail(dto.getXboxLiveEmail());
                if (dto.getXboxLivePassword() != null) {
                    entity.setXboxLivePasswordEncrypted(aesUtil.encrypt(dto.getXboxLivePassword()));
                }
                entity.setIsActive(true);
                entity.setIsPrimary(false);
                entity.setCreatedTime(LocalDateTime.now());
                entity.setUpdatedTime(LocalDateTime.now());
                gameAccountMapper.insert(entity);
                successCount++;
            } catch (Exception e) {
                log.error("导入游戏账号失败: {}", dto.getXboxGameName(), e);
                errors.add(String.format("Xbox玩家名称[%s]: 导入失败", dto.getXboxGameName()));
            }
        }

        result.setSuccessCount(successCount);
        result.setFailCount(accounts.size() - successCount);
        result.setErrors(errors);
        log.info("批量导入游戏账号完成 - 成功: {}, 失败: {}", successCount, accounts.size() - successCount);
        return result;
    }

    @Override
    public GameAccount findById(String id) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account != null) {
            dataSecurityUtil.validateMerchantAccess(account.getMerchantId(), "GameAccount");
        }
        return account;
    }

    @Override
    public GameAccount findByGamertag(String gamertag) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getXboxGameName, gamertag);
        return gameAccountMapper.selectOne(wrapper);
    }

    @Override
    public IPage<GameAccount> findByMerchantId(String merchantId, GameAccountPageRequest request) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(GameAccount::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(GameAccount::getCreatedTime);
        Page<GameAccount> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        IPage<GameAccount> result = gameAccountMapper.selectPage(page, wrapper);
        fillRelatedNames(result.getRecords());
        return result;
    }

    @Override
    public IPage<GameAccount> findByStreamingId(String streamingId, GameAccountPageRequest request) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getStreamingId, streamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        Page<GameAccount> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        IPage<GameAccount> result = gameAccountMapper.selectPage(page, wrapper);
        fillRelatedNames(result.getRecords());
        return result;
    }

    @Override
    public List<GameAccount> findAllByStreamingId(String streamingId) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getStreamingId, streamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        List<GameAccount> result = gameAccountMapper.selectList(wrapper);
        fillRelatedNames(result);
        return result;
    }

    private void fillRelatedNames(List<GameAccount> accounts) {
        if (CollectionUtils.isEmpty(accounts)) {
            return;
        }
        Set<String> merchantIds = accounts.stream()
                .map(GameAccount::getMerchantId)
                .filter(id -> id != null)
                .collect(Collectors.toSet());
        Set<String> streamingIds = accounts.stream()
                .map(GameAccount::getStreamingId)
                .filter(id -> id != null)
                .collect(Collectors.toSet());

        Map<String, String> merchantNameMap = new HashMap<>();
        if (!merchantIds.isEmpty()) {
            LambdaQueryWrapper<Merchant> merchantWrapper = new LambdaQueryWrapper<>();
            merchantWrapper.in(Merchant::getId, merchantIds);
            List<Merchant> merchants = merchantMapper.selectList(merchantWrapper);
            merchantNameMap = merchants.stream()
                    .collect(Collectors.toMap(Merchant::getId, Merchant::getName));
        }

        Map<String, String> streamingNameMap = new HashMap<>();
        if (!streamingIds.isEmpty()) {
            LambdaQueryWrapper<StreamingAccount> streamingWrapper = new LambdaQueryWrapper<>();
            streamingWrapper.in(StreamingAccount::getId, streamingIds);
            List<StreamingAccount> streamings = streamingAccountMapper.selectList(streamingWrapper);
            streamingNameMap = streamings.stream()
                    .collect(Collectors.toMap(StreamingAccount::getId, StreamingAccount::getName));
        }

        for (GameAccount account : accounts) {
            account.setMerchantName(merchantNameMap.get(account.getMerchantId()));
            account.setStreamingName(streamingNameMap.get(account.getStreamingId()));
        }
    }

    @Override
    public IPage<GameAccount> findAll(GameAccountPageRequest request) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(GameAccount::getCreatedTime);
        Page<GameAccount> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        IPage<GameAccount> result = gameAccountMapper.selectPage(page, wrapper);
        fillRelatedNames(result.getRecords());
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String id, GameAccount account) {
        GameAccount existing = gameAccountMapper.selectById(id);
        if (existing == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        if (account.getMerchantId() != null) {
            existing.setMerchantId(account.getMerchantId());
        }
        if (account.getXboxLiveEmail() != null) {
            existing.setXboxLiveEmail(account.getXboxLiveEmail());
        }
        if (account.getXboxLivePasswordEncrypted() != null) {
            existing.setXboxLivePasswordEncrypted(aesUtil.encrypt(account.getXboxLivePasswordEncrypted()));
        }
        if (account.getIsActive() != null) {
            existing.setIsActive(account.getIsActive());
        }
        existing.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.updateById(existing);
        log.info("更新游戏账号 - ID: {}", id);
    }

    @Override
    public List<GameAccount> findUnboundByMerchantId(String merchantId) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getMerchantId, merchantId)
               .isNull(GameAccount::getStreamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        return gameAccountMapper.selectList(wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindToStreamingAccount(String streamingAccountId, List<String> gameAccountIds) {
        for (String gameAccountId : gameAccountIds) {
            GameAccount account = gameAccountMapper.selectById(gameAccountId);
            if (account == null) {
                throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
            }
            account.setStreamingId(streamingAccountId);
            account.setUpdatedTime(LocalDateTime.now());
            gameAccountMapper.updateById(account);
        }
        log.info("绑定游戏账号到流媒体账号 - streamingId: {}, gameAccountIds: {}", streamingAccountId, gameAccountIds);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindFromStreamingAccount(List<String> gameAccountIds) {
        log.info("开始解绑游戏账号 - gameAccountIds: {}", gameAccountIds);
        for (String gameAccountId : gameAccountIds) {
            GameAccount account = gameAccountMapper.selectById(gameAccountId);
            log.info("查询到的账号 - id: {}, streamingId: {}", account.getId(), account.getStreamingId());
            if (account == null) {
                throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
            }

            LambdaUpdateWrapper<GameAccount> wrapper = new LambdaUpdateWrapper<>();
            wrapper.eq(GameAccount::getId, gameAccountId)
                   .set(GameAccount::getStreamingId, null)
                   .set(GameAccount::getUpdatedTime, LocalDateTime.now());
            int rows = gameAccountMapper.update(null, wrapper);
            log.info("更新结果 - gameAccountId: {}, affectedRows: {}", gameAccountId, rows);
        }
        log.info("解绑游戏账号完成 - gameAccountIds: {}", gameAccountIds);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void disable(String id) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setIsActive(false);
        account.setUpdatedTime(LocalDateTime.now());
        gameAccountMapper.updateById(account);
        log.info("禁用游戏账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void enable(String id) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setIsActive(true);
        account.setUpdatedTime(LocalDateTime.now());
        gameAccountMapper.updateById(account);
        log.info("启用游戏账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setPrimary(String id, boolean primary) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setIsPrimary(primary);
        account.setUpdatedTime(LocalDateTime.now());

        gameAccountMapper.updateById(account);
        log.info("设置游戏账号为主账号 - ID: {}, Primary: {}", id, primary);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        gameAccountMapper.deleteById(id);
        log.info("删除游戏账号 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateAgentId(String id, String agentId) {
        GameAccount account = gameAccountMapper.selectById(id);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        account.setAgentId(agentId);
        account.setUpdatedTime(LocalDateTime.now());
        gameAccountMapper.updateById(account);
        log.info("更新游戏账号Agent绑定 - ID: {}, AgentID: {}", id, agentId);
    }

    @Override
    public List<GameAccount> findByStreamingId(String streamingId) {
        LambdaQueryWrapper<GameAccount> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(GameAccount::getStreamingId, streamingId)
               .orderByDesc(GameAccount::getCreatedTime);
        return gameAccountMapper.selectList(wrapper);
    }
}