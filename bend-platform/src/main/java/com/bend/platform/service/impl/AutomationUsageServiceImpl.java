package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.*;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.repository.AutomationBillingEventMapper;
import com.bend.platform.repository.AutomationUsageMapper;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.AutomationUsageService;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.service.TaskService;
import com.bend.platform.service.TaskGameAccountStatusService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
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
    private final AutomationBillingEventMapper billingEventMapper;
    private final MerchantMapper merchantMapper;
    private final GameAccountMapper gameAccountMapper;
    private final TaskService taskService;
    private final TaskGameAccountStatusService taskGameAccountStatusService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public Map<String, Object> validateAndCalculatePoints(String merchantId, String streamingAccountId,
                                                List<GameAccount> gameAccounts, List<XboxHost> hosts) {
        Map<String, Object> result = new HashMap<>();
        int requiredPoints = 0;
        boolean canStart = true;
        StringBuilder message = new StringBuilder();
        String chargeType = null;

        List<Subscription> activeSubscriptions = subscriptionService.getActiveSubscriptions(merchantId);

        Merchant merchant = merchantMapper.selectById(merchantId);
        MerchantGroup group = getMerchantGroup(merchant);

        int windowPrice = group != null && group.getWindowDiscountPrice() != null ? group.getWindowDiscountPrice().intValue() : 1;
        int accountPrice = 1;
        int hostPrice = 1;

        Map<String, Object> windowMonthlyUsage = checkMonthlyUsage(merchantId, "window", streamingAccountId);
        Map<String, Object> accountMonthlyUsage = checkMonthlyUsage(merchantId, "account",
            gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getId() : null);
        Map<String, Object> hostMonthlyUsage = checkMonthlyUsage(merchantId, "host",
            hosts != null && !hosts.isEmpty() ? hosts.get(0).getId() : null);

        int accountCount = gameAccounts != null ? gameAccounts.size() : 0;
        int hostCount = hosts != null ? hosts.size() : 0;

        boolean hasWindowSubscription = checkSubscription(activeSubscriptions, "window", streamingAccountId);
        boolean hasAccountSubscription = false;
        boolean hasHostSubscription = false;

        for (GameAccount ga : gameAccounts) {
            if (checkSubscription(activeSubscriptions, "account", ga.getId())) {
                hasAccountSubscription = true;
                break;
            }
        }

        for (XboxHost host : hosts) {
            if (checkSubscription(activeSubscriptions, "host", host.getId())) {
                hasHostSubscription = true;
                break;
            }
        }

        boolean windowMonthlyFree = Boolean.TRUE.equals(windowMonthlyUsage.get("hasMonthlyFree"));
        boolean accountMonthlyFree = Boolean.TRUE.equals(accountMonthlyUsage.get("hasMonthlyFree"));
        boolean hostMonthlyFree = Boolean.TRUE.equals(hostMonthlyUsage.get("hasMonthlyFree"));

        if (hasWindowSubscription) {
            requiredPoints = 0;
            chargeType = "subscription_window";
            message.append("使用流媒体账号包月，不扣点");
        } else if (windowMonthlyFree) {
            requiredPoints = 0;
            chargeType = "monthly_window";
            message.append("本月流媒体账号月度额度已使用，当月免费");
        } else if (hasAccountSubscription) {
            requiredPoints = 0;
            chargeType = "subscription_account";
            message.append("使用游戏账号包月，不扣点");
        } else if (accountMonthlyFree) {
            requiredPoints = 0;
            chargeType = "monthly_account";
            message.append("本月游戏账号月度额度已使用，当月免费");
        } else if (hasHostSubscription) {
            requiredPoints = 0;
            chargeType = "subscription_host";
            message.append("使用Xbox主机包月，不扣点");
        } else if (hostMonthlyFree) {
            requiredPoints = 0;
            chargeType = "monthly_host";
            message.append("本月Xbox主机月度额度已使用，当月免费");
        } else if (accountCount > 0) {
            // 按游戏账号数量计算需要的点数（每个游戏账号完成当天最大比赛次数后扣1点）
            requiredPoints = accountPrice * accountCount;
            chargeType = "per_use_account";
            message.append("按次扣费：待执行游戏账号 ").append(accountCount).append(" 个，每个完成当日最大比赛次数后扣1点，共需 ").append(requiredPoints).append(" 点");
        } else if (hostCount > 0) {
            requiredPoints = hostPrice * hostCount;
            chargeType = "per_use_host";
            message.append("按次扣费：Xbox主机 ").append(hostCount).append(" 台，共 ").append(requiredPoints).append(" 点");
        } else {
            requiredPoints = windowPrice;
            chargeType = "per_use_window";
            message.append("按次扣费：流媒体账号，共 ").append(requiredPoints).append(" 点");
        }

        // 检查是否有生效订阅或月度额度，如果有则不检查余额
        boolean hasSubscription = hasWindowSubscription || hasAccountSubscription || hasHostSubscription
                || windowMonthlyFree || accountMonthlyFree || hostMonthlyFree;

        // 只有在没有订阅且需要扣点时才检查余额
        if (requiredPoints > 0 && !hasSubscription) {
            // 获取商户当前余额
            MerchantBalance balance = balanceService.getByMerchantId(merchantId);
            int currentBalance = balance != null ? balance.getBalance() : 0;

            // 统计其他正在运行的任务涉及的游戏账号数量（这些账号如果完成当日最大比赛次数也会扣点）
            int otherRunningGameAccountCount = 0;
            List<Task> otherRunningTasks = taskService.findRunningTasksByMerchantId(merchantId);
            for (Task task : otherRunningTasks) {
                // 排除当前流媒体账号关联的任务
                if (streamingAccountId != null && streamingAccountId.equals(task.getStreamingAccountId())) {
                    continue;
                }
                // 统计该任务关联的游戏账号数量
                List<TaskGameAccountStatus> gameAccountStatuses = taskGameAccountStatusService.findByTaskId(task.getId());
                otherRunningGameAccountCount += gameAccountStatuses.size();
            }

            // 总共需要的点数 = 本次启动的账号数 + 其他正在运行任务的账号数
            int totalRequiredPoints = requiredPoints + otherRunningGameAccountCount;

            if (currentBalance < totalRequiredPoints) {
                canStart = false;
                message.setLength(0);
                message.append("余额不足：当前余额 ").append(currentBalance)
                        .append(" 点不足")
                        .append("（本次启动需要 ").append(requiredPoints)
                        .append(" 点，其他正在运行的任务已占用 ").append(otherRunningGameAccountCount)
                        .append(" 点，共需 ").append(totalRequiredPoints).append(" 点）")
                        .append("，请先充值或使用激活码订阅。");
            }
        }

        result.put("canStart", canStart);
        result.put("totalPoints", requiredPoints);
        result.put("message", message.toString());
        result.put("chargeType", chargeType);

        result.put("hasWindowSubscription", hasWindowSubscription);
        result.put("hasAccountSubscription", hasAccountSubscription);
        result.put("hasHostSubscription", hasHostSubscription);

        result.put("windowMonthlyFree", windowMonthlyFree);
        result.put("accountMonthlyFree", accountMonthlyFree);
        result.put("hostMonthlyFree", hostMonthlyFree);

        result.put("windowPrice", windowPrice);
        result.put("accountPrice", accountPrice);
        result.put("hostPrice", hostPrice);

        result.put("accountCount", accountCount);
        result.put("hostCount", hostCount);

        result.put("windowMonthlyUsage", windowMonthlyUsage);
        result.put("accountMonthlyUsage", accountMonthlyUsage);
        result.put("hostMonthlyUsage", hostMonthlyUsage);

        result.put("streamingAccountId", streamingAccountId);
        result.put("gameAccounts", gameAccounts);
        result.put("hosts", hosts);

        log.info("自动化启动校验 - merchantId: {}, canStart: {}, requiredPoints: {}, chargeType: {}, accountCount: {}",
                merchantId, canStart, requiredPoints, chargeType, accountCount);

        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deductPointsAndRecordUsage(String merchantId, String userId, String taskId,
                                       String streamingAccountId, String streamingAccountName,
                                       int gameAccountsCount, int hostsCount, Map<String, Object> validationResult) {
        int totalPoints = (Integer) validationResult.get("totalPoints");
        String chargeType = (String) validationResult.get("chargeType");

        @SuppressWarnings("unchecked")
        List<GameAccount> gameAccounts = (List<GameAccount>) validationResult.get("gameAccounts");
        @SuppressWarnings("unchecked")
        List<XboxHost> hosts = (List<XboxHost>) validationResult.get("hosts");

        int accountCount = (Integer) validationResult.getOrDefault("accountCount", 0);
        int hostCount = (Integer) validationResult.getOrDefault("hostCount", 0);
        int accountPrice = (Integer) validationResult.getOrDefault("accountPrice", 5);
        int hostPrice = (Integer) validationResult.getOrDefault("hostPrice", 20);
        int windowPrice = (Integer) validationResult.getOrDefault("windowPrice", 10);

        if (totalPoints > 0) {
            boolean deducted = balanceService.deductPoints(merchantId, totalPoints, userId,
                    "automation", taskId,
                    "启动自动化任务消耗点数");
            if (!deducted) {
                throw new BusinessException(500, "扣点失败");
            }
        }

        String resourceType;
        String resourceId;
        String resourceName;
        String chargeMode;
        int pointsDeducted;

        if (chargeType.startsWith("subscription_") || chargeType.startsWith("monthly_")) {
            if (chargeType.contains("window")) {
                resourceType = "window";
                resourceId = streamingAccountId;
                resourceName = streamingAccountName;
                chargeMode = chargeType.startsWith("subscription_") ? "monthly" : "monthly";
                pointsDeducted = 0;
            } else if (chargeType.contains("account")) {
                resourceType = "account";
                resourceId = gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getId() : null;
                resourceName = gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getGameName() : null;
                chargeMode = chargeType.startsWith("subscription_") ? "monthly" : "monthly";
                pointsDeducted = 0;
            } else {
                resourceType = "host";
                resourceId = hosts != null && !hosts.isEmpty() ? hosts.get(0).getId() : null;
                resourceName = hosts != null && !hosts.isEmpty() ? hosts.get(0).getName() : null;
                chargeMode = chargeType.startsWith("subscription_") ? "monthly" : "monthly";
                pointsDeducted = 0;
            }
        } else {
            if (chargeType.contains("account")) {
                resourceType = "account";
                resourceId = gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getId() : null;
                resourceName = gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getGameName() : null;
                chargeMode = "per_use";
                pointsDeducted = accountPrice * accountCount;
            } else if (chargeType.contains("host")) {
                resourceType = "host";
                resourceId = hosts != null && !hosts.isEmpty() ? hosts.get(0).getId() : null;
                resourceName = hosts != null && !hosts.isEmpty() ? hosts.get(0).getName() : null;
                chargeMode = "per_use";
                pointsDeducted = hostPrice * hostCount;
            } else {
                resourceType = "window";
                resourceId = streamingAccountId;
                resourceName = streamingAccountName;
                chargeMode = "per_use";
                pointsDeducted = windowPrice;
            }
        }

        AutomationUsage usage = new AutomationUsage();
        usage.setMerchantId(merchantId);
        usage.setUserId(userId);
        usage.setTaskId(taskId);
        usage.setStreamingAccountId(streamingAccountId);
        usage.setStreamingAccountName(streamingAccountName);
        usage.setGameAccountsCount(gameAccountsCount);
        usage.setHostsCount(hostsCount);
        usage.setResourceType(resourceType);
        usage.setResourceId(resourceId);
        usage.setResourceName(resourceName);
        usage.setPointsDeducted(pointsDeducted);
        usage.setChargeMode(chargeMode);
        usage.setUsageTime(LocalDateTime.now());
        automationUsageMapper.insert(usage);

        log.info("记录自动化使用 - merchantId: {}, taskId: {}, resourceType: {}, points: {}, chargeMode: {}",
                merchantId, taskId, resourceType, pointsDeducted, chargeMode);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> recordBillableEvent(Task task, Map<String, Object> payload) {
        String gameAccountId = stringValue(payload.get("gameAccountId"));
        String sessionId = stringValue(payload.get("sessionId"));
        if (sessionId == null) {
            sessionId = task.getSessionId();
        }
        String gameActionType = normalizeGameActionType(
                stringValue(payload.get("gameActionType")) != null
                        ? stringValue(payload.get("gameActionType"))
                        : task.getGameActionType());
        String billingUnit = normalizeBillingUnit(gameActionType, stringValue(payload.get("billingUnit")));
        Integer unitIndex = intValue(payload.get("unitIndex"));
        if (gameAccountId == null || billingUnit == null || unitIndex == null) {
            throw new BusinessException(400, "gameAccountId、billingUnit、unitIndex不能为空");
        }

        String rawIdempotentKey = String.join(":",
                task.getId(),
                sessionId != null ? sessionId : "-",
                gameAccountId,
                gameActionType,
                billingUnit,
                String.valueOf(unitIndex));
        String idempotentKey = "bill:" + java.util.UUID.nameUUIDFromBytes(
                rawIdempotentKey.getBytes(StandardCharsets.UTF_8));

        AutomationBillingEvent event = new AutomationBillingEvent();
        event.setMerchantId(task.getMerchantId());
        event.setTaskId(task.getId());
        event.setSessionId(sessionId);
        event.setStreamingAccountId(task.getStreamingAccountId());
        event.setGameAccountId(gameAccountId);
        event.setGameActionType(gameActionType);
        event.setBillingUnit(billingUnit);
        event.setUnitIndex(unitIndex);
        event.setIdempotentKey(idempotentKey);
        event.setPointsDeducted(resolveEventPoints(gameActionType, billingUnit));
        event.setCoinsDelta(intValue(payload.get("coinsDelta")) != null ? intValue(payload.get("coinsDelta")) : 0);
        event.setStatus("recorded");
        try {
            event.setPayload(objectMapper.writeValueAsString(payload));
        } catch (Exception e) {
            event.setPayload("{}");
        }

        try {
            billingEventMapper.insert(event);
        } catch (DuplicateKeyException e) {
            Map<String, Object> duplicate = new HashMap<>();
            duplicate.put("recorded", true);
            duplicate.put("duplicate", true);
            duplicate.put("idempotentKey", idempotentKey);
            duplicate.put("pointsDeducted", 0);
            return duplicate;
        }

        int points = event.getPointsDeducted() != null ? event.getPointsDeducted() : 0;
        if (points > 0) {
            boolean deducted = balanceService.deductPoints(
                    task.getMerchantId(),
                    points,
                    task.getCreatedBy(),
                    "automation_billing",
                    idempotentKey,
                    "自动化计费事件: " + gameActionType + "/" + billingUnit);
            if (!deducted) {
                throw new BusinessException(400, "余额不足，无法结算本次计费事件");
            }
        }

        updateGameAccountMetrics(gameAccountId, billingUnit, event.getCoinsDelta());

        Map<String, Object> result = new HashMap<>();
        result.put("recorded", true);
        result.put("duplicate", false);
        result.put("idempotentKey", idempotentKey);
        result.put("pointsDeducted", points);
        return result;
    }

    private String normalizeGameActionType(String value) {
        if (value == null || value.isBlank()) {
            return "squad_battle";
        }
        return switch (value) {
            case "auction_transfer", "squad_battle", "transfer_sqb_combo",
                    "divisions_rivals", "weekend_league" -> value;
            default -> "squad_battle";
        };
    }

    private String normalizeBillingUnit(String gameActionType, String billingUnit) {
        if (billingUnit == null || billingUnit.isBlank()) {
            return null;
        }
        return switch (gameActionType) {
            case "auction_transfer" -> "transfer_round".equals(billingUnit) ? billingUnit : null;
            case "transfer_sqb_combo" ->
                    ("transfer_round".equals(billingUnit) || "match_completed".equals(billingUnit))
                            ? billingUnit : null;
            case "squad_battle", "divisions_rivals", "weekend_league" ->
                    "match_completed".equals(billingUnit) ? billingUnit : null;
            default -> null;
        };
    }

    private int resolveEventPoints(String gameActionType, String billingUnit) {
        if (normalizeBillingUnit(gameActionType, billingUnit) == null) {
            throw new BusinessException(400, "当前任务类型不支持该计费单元");
        }
        return 1;
    }

    private Integer intValue(Object raw) {
        if (raw instanceof Number number) {
            return number.intValue();
        }
        if (raw != null && !String.valueOf(raw).isBlank()) {
            return Integer.parseInt(String.valueOf(raw));
        }
        return null;
    }

    private String stringValue(Object raw) {
        if (raw == null || String.valueOf(raw).isBlank()) {
            return null;
        }
        return String.valueOf(raw);
    }

    private void updateGameAccountMetrics(String gameAccountId, String billingUnit, Integer coinsDelta) {
        GameAccount account = gameAccountMapper.selectById(gameAccountId);
        if (account == null) {
            return;
        }
        if ("match_completed".equals(billingUnit)) {
            account.setTodayMatchCount((account.getTodayMatchCount() != null ? account.getTodayMatchCount() : 0) + 1);
            account.setTotalMatchCount((account.getTotalMatchCount() != null ? account.getTotalMatchCount() : 0) + 1);
        }
        int delta = coinsDelta != null ? coinsDelta : 0;
        if (delta != 0) {
            account.setTodayCoins((account.getTodayCoins() != null ? account.getTodayCoins() : 0) + delta);
            account.setTotalCoins((account.getTotalCoins() != null ? account.getTotalCoins() : 0) + delta);
        }
        account.setTodayLastCompletedTime(LocalDateTime.now());
        account.setLastUsedTime(LocalDateTime.now());
        gameAccountMapper.updateById(account);
    }

    private boolean checkSubscription(List<Subscription> subscriptions, String type, String targetId) {
        if (subscriptions == null || targetId == null) {
            return false;
        }
        for (Subscription sub : subscriptions) {
            if (type.equals(sub.getSubscriptionType()) && targetId.equals(sub.getBoundResourceIds())) {
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
