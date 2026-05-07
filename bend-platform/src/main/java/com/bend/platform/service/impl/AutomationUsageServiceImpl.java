package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.*;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.repository.AutomationUsageMapper;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.AutomationUsageService;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.SubscriptionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.YearMonth;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class AutomationUsageServiceImpl implements AutomationUsageService {

    private final SubscriptionService subscriptionService;
    private final MerchantBalanceService balanceService;
    private final MerchantGroupMapper merchantGroupMapper;
    private final AutomationUsageMapper automationUsageMapper;
    private final MerchantMapper merchantMapper;

    @Override
    public Map<String, Object> validateAndCalculatePoints(String merchantId, String streamingAccountId,
                                                List<GameAccount> gameAccounts, List<XboxHost> hosts) {
        Map<String, Object> result = new HashMap<>();
        int totalPoints = 0;
        boolean canStart = true;
        StringBuilder message = new StringBuilder();

        List<Subscription> activeSubscriptions = subscriptionService.getActiveSubscriptions(merchantId);

        boolean hasWindowSubscription = checkSubscription(activeSubscriptions, "window", streamingAccountId);

        boolean hasAccountSubscription = false;
        String accountId = null;
        if (gameAccounts != null && !gameAccounts.isEmpty()) {
            accountId = gameAccounts.get(0).getId();
            for (GameAccount gameAccount : gameAccounts) {
                if (checkSubscription(activeSubscriptions, "account", gameAccount.getId())) {
                    hasAccountSubscription = true;
                    break;
                }
            }
        }

        boolean hasHostSubscription = false;
        String hostId = null;
        if (hosts != null && !hosts.isEmpty()) {
            hostId = hosts.get(0).getId();
            for (XboxHost host : hosts) {
                if (checkSubscription(activeSubscriptions, "host", host.getId())) {
                    hasHostSubscription = true;
                    break;
                }
            }
        }

        Merchant merchant = merchantMapper.selectById(merchantId);
        MerchantGroup group = getMerchantGroup(merchant);

        int windowPrice = group != null && group.getWindowPrice() != null ? group.getWindowPrice().intValue() : 10;
        int accountPrice = group != null && group.getAccountPrice() != null ? group.getAccountPrice().intValue() : 5;
        int hostPrice = group != null && group.getHostPrice() != null ? group.getHostPrice().intValue() : 20;

        Map<String, Object> windowMonthlyUsage = checkMonthlyUsage(merchantId, "window", streamingAccountId);
        Map<String, Object> accountMonthlyUsage = checkMonthlyUsage(merchantId, "account", accountId);
        Map<String, Object> hostMonthlyUsage = checkMonthlyUsage(merchantId, "host", hostId);

        if (!hasWindowSubscription && !Boolean.TRUE.equals(windowMonthlyUsage.get("hasMonthlyFree"))) {
            totalPoints += windowPrice;
            result.put("windowCharge", true);
        }

        int accountCount = gameAccounts != null ? gameAccounts.size() : 0;
        if (!hasAccountSubscription && !Boolean.TRUE.equals(accountMonthlyUsage.get("hasMonthlyFree")) && accountCount > 0) {
            totalPoints += accountPrice * accountCount;
            result.put("accountCharge", true);
        }

        int hostCount = hosts != null ? hosts.size() : 0;
        if (!hasHostSubscription && !Boolean.TRUE.equals(hostMonthlyUsage.get("hasMonthlyFree")) && hostCount > 0) {
            totalPoints += hostPrice * hostCount;
            result.put("hostCharge", true);
        }

        if (totalPoints > 0 && !balanceService.hasEnoughBalance(merchantId, totalPoints)) {
            canStart = false;
            message.append("余额不足，需要").append(totalPoints).append("点，当前余额不足，请先充值或使用激活码订阅。");
        }

        result.put("canStart", canStart);
        result.put("totalPoints", totalPoints);
        result.put("message", message.toString());
        result.put("hasWindowSubscription", hasWindowSubscription);
        result.put("hasAccountSubscription", hasAccountSubscription);
        result.put("hasHostSubscription", hasHostSubscription);
        result.put("windowPrice", windowPrice);
        result.put("accountPrice", accountPrice);
        result.put("hostPrice", hostPrice);
        result.put("windowMonthlyUsage", windowMonthlyUsage);
        result.put("accountMonthlyUsage", accountMonthlyUsage);
        result.put("hostMonthlyUsage", hostMonthlyUsage);
        result.put("windowCharge", result.containsKey("windowCharge") ? result.get("windowCharge") : false);
        result.put("accountCharge", result.containsKey("accountCharge") ? result.get("accountCharge") : false);
        result.put("hostCharge", result.containsKey("hostCharge") ? result.get("hostCharge") : false);
        result.put("streamingAccountId", streamingAccountId);
        result.put("accountId", accountId);
        result.put("hostId", hostId);
        result.put("gameAccounts", gameAccounts);
        result.put("hosts", hosts);

        log.info("自动化启动校验 - merchantId: {}, canStart: {}, totalPoints: {}",
                merchantId, canStart, totalPoints);

        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deductPointsAndRecordUsage(String merchantId, String userId, String taskId,
                                       String streamingAccountId, String streamingAccountName,
                                       int gameAccountsCount, int hostsCount, Map<String, Object> validationResult) {
        int totalPoints = (Integer) validationResult.get("totalPoints");

        String accountId = (String) validationResult.get("accountId");
        String hostId = (String) validationResult.get("hostId");
        Boolean hasWindowSubscription = (Boolean) validationResult.get("hasWindowSubscription");
        Boolean hasAccountSubscription = (Boolean) validationResult.get("hasAccountSubscription");
        Boolean hasHostSubscription = (Boolean) validationResult.get("hasHostSubscription");
        Boolean windowCharge = (Boolean) validationResult.get("windowCharge");
        Boolean accountCharge = (Boolean) validationResult.get("accountCharge");
        Boolean hostCharge = (Boolean) validationResult.get("hostCharge");
        int windowPrice = (Integer) validationResult.get("windowPrice");
        int accountPrice = (Integer) validationResult.get("accountPrice");
        int hostPrice = (Integer) validationResult.get("hostPrice");
        @SuppressWarnings("unchecked")
        List<GameAccount> gameAccounts = (List<GameAccount>) validationResult.get("gameAccounts");
        @SuppressWarnings("unchecked")
        List<XboxHost> hosts = (List<XboxHost>) validationResult.get("hosts");

        if (totalPoints > 0) {
            boolean deducted = balanceService.deductPoints(merchantId, totalPoints, userId,
                    "automation", taskId,
                    "启动自动化任务消耗点数");
            if (!deducted) {
                throw new BusinessException(500, "扣点失败");
            }
        }

        if (streamingAccountId != null) {
            AutomationUsage windowUsage = new AutomationUsage();
            windowUsage.setMerchantId(merchantId);
            windowUsage.setUserId(userId);
            windowUsage.setTaskId(taskId);
            windowUsage.setStreamingAccountId(streamingAccountId);
            windowUsage.setStreamingAccountName(streamingAccountName);
            windowUsage.setGameAccountsCount(gameAccountsCount);
            windowUsage.setHostsCount(hostsCount);
            windowUsage.setResourceType("window");
            windowUsage.setResourceId(streamingAccountId);
            windowUsage.setResourceName(streamingAccountName);
            if (hasWindowSubscription) {
                windowUsage.setPointsDeducted(0);
                windowUsage.setChargeMode("monthly");
            } else if (Boolean.TRUE.equals(windowCharge)) {
                windowUsage.setPointsDeducted(windowPrice);
                windowUsage.setChargeMode("per_use");
            } else {
                windowUsage.setPointsDeducted(0);
                windowUsage.setChargeMode("monthly");
            }
            windowUsage.setUsageTime(LocalDateTime.now());
            automationUsageMapper.insert(windowUsage);
        }

        if (gameAccounts != null && !gameAccounts.isEmpty()) {
            GameAccount firstAccount = gameAccounts.get(0);
            AutomationUsage accountUsage = new AutomationUsage();
            accountUsage.setMerchantId(merchantId);
            accountUsage.setUserId(userId);
            accountUsage.setTaskId(taskId);
            accountUsage.setStreamingAccountId(streamingAccountId);
            accountUsage.setStreamingAccountName(streamingAccountName);
            accountUsage.setGameAccountsCount(gameAccountsCount);
            accountUsage.setHostsCount(hostsCount);
            accountUsage.setResourceType("account");
            accountUsage.setResourceId(firstAccount.getId());
            accountUsage.setResourceName(firstAccount.getXboxGameName());
            if (hasAccountSubscription) {
                accountUsage.setPointsDeducted(0);
                accountUsage.setChargeMode("monthly");
            } else if (Boolean.TRUE.equals(accountCharge)) {
                accountUsage.setPointsDeducted(accountPrice);
                accountUsage.setChargeMode("per_use");
            } else {
                accountUsage.setPointsDeducted(0);
                accountUsage.setChargeMode("monthly");
            }
            accountUsage.setUsageTime(LocalDateTime.now());
            automationUsageMapper.insert(accountUsage);
        }

        if (hosts != null && !hosts.isEmpty()) {
            XboxHost firstHost = hosts.get(0);
            AutomationUsage hostUsage = new AutomationUsage();
            hostUsage.setMerchantId(merchantId);
            hostUsage.setUserId(userId);
            hostUsage.setTaskId(taskId);
            hostUsage.setStreamingAccountId(streamingAccountId);
            hostUsage.setStreamingAccountName(streamingAccountName);
            hostUsage.setGameAccountsCount(gameAccountsCount);
            hostUsage.setHostsCount(hostsCount);
            hostUsage.setResourceType("host");
            hostUsage.setResourceId(firstHost.getId());
            hostUsage.setResourceName(firstHost.getName());
            if (hasHostSubscription) {
                hostUsage.setPointsDeducted(0);
                hostUsage.setChargeMode("monthly");
            } else if (Boolean.TRUE.equals(hostCharge)) {
                hostUsage.setPointsDeducted(hostPrice);
                hostUsage.setChargeMode("per_use");
            } else {
                hostUsage.setPointsDeducted(0);
                hostUsage.setChargeMode("monthly");
            }
            hostUsage.setUsageTime(LocalDateTime.now());
            automationUsageMapper.insert(hostUsage);
        }

        log.info("记录自动化使用 - merchantId: {}, taskId: {}, points: {}",
                merchantId, taskId, totalPoints);
    }

    private boolean checkSubscription(List<Subscription> subscriptions, String type, String targetId) {
        if (subscriptions == null || targetId == null) {
            return false;
        }
        for (Subscription sub : subscriptions) {
            if (type.equals(sub.getType()) && targetId.equals(sub.getTargetId())) {
                return true;
            }
        }
        return false;
    }

    private Map<String, Object> checkMonthlyUsage(String merchantId, String type, String targetId) {
        Map<String, Object> result = new HashMap<>();
        boolean hasMonthlyFree = false;

        if (targetId == null) {
            result.put("hasMonthlyFree", false);
            result.put("usageCount", 0);
            return result;
        }

        LocalDateTime monthStart = YearMonth.now().atDay(1).atStartOfDay();
        LocalDateTime monthEnd = YearMonth.now().atEndOfMonth().atTime(23, 59, 59);

        LambdaQueryWrapper<AutomationUsage> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AutomationUsage::getMerchantId, merchantId)
                .eq(AutomationUsage::getResourceType, type)
                .eq(AutomationUsage::getResourceId, targetId)
                .ge(AutomationUsage::getUsageTime, monthStart)
                .le(AutomationUsage::getUsageTime, monthEnd);

        List<AutomationUsage> usages = automationUsageMapper.selectList(wrapper);

        for (AutomationUsage usage : usages) {
            if ("monthly".equals(usage.getChargeMode()) || (usage.getPointsDeducted() == null || usage.getPointsDeducted() == 0)) {
                hasMonthlyFree = true;
                break;
            }
        }

        result.put("hasMonthlyFree", hasMonthlyFree);
        result.put("usageCount", usages.size());

        return result;
    }

    private MerchantGroup getMerchantGroup(Merchant merchant) {
        int vipLevel = 0;
        if (merchant != null && merchant.getVipLevel() != null) {
            vipLevel = merchant.getVipLevel();
        }

        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getVipLevel, vipLevel)
                .eq(MerchantGroup::getStatus, "active")
                .last("LIMIT 1");
        MerchantGroup group = merchantGroupMapper.selectOne(wrapper);

        if (group == null && vipLevel > 0) {
            wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(MerchantGroup::getVipLevel, 0)
                    .eq(MerchantGroup::getStatus, "active")
                    .last("LIMIT 1");
            group = merchantGroupMapper.selectOne(wrapper);
        }

        return group;
    }
}
