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
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 自动化用量与计费服务实现。
 *
 * <p>职责边界：
 * <ul>
 *   <li>启动前根据订阅、月度额度、按次价格和运行中任务预占点数计算是否允许启动。</li>
 *   <li>启动时记录一次资源级用量，兼容窗口/游戏账号/Xbox 主机三类资源。</li>
 *   <li>Step4 完成可计费单元后写入幂等计费事件，并更新游戏账号统计指标。</li>
 * </ul>
 *
 * <p>计费事件使用 task/session/gameAccount/action/unit/index 生成幂等键，避免 Agent
 * 重试回调或网络抖动导致重复扣点。
 */
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

    @Value("${license.mode:master}")
    private String licenseMode;
    @Value("${license.master-url:}")
    private String masterUrl;
    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;
    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

    /**
     * 校验自动化启动是否需要预留点数。
     *
     * <p>分支优先级为包月订阅、月度免费额度、按游戏账号扣点、按主机扣点、按窗口扣点。
     * 若本次需要扣点，会把其他运行中任务的游戏账号数作为潜在扣点占用一起纳入余额校验。
     */
    @Override
    public Map<String, Object> validateAndCalculatePoints(String merchantId, String streamingAccountId,
                                                List<GameAccount> gameAccounts, List<XboxHost> hosts) {
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return proxyValidateToMaster(merchantId, streamingAccountId, gameAccounts, hosts);
        }
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

    /**
     * 记录启动阶段的资源用量。
     *
     * <p>这里保留旧的启动扣点/用量模型；真正按比赛或转会轮次结算的事件由
     * {@link #recordBillableEvent(Task, Map)} 处理。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deductPointsAndRecordUsage(String merchantId, String userId, String taskId,
                                        String streamingAccountId, String streamingAccountName,
                                        int gameAccountsCount, int hostsCount, Map<String, Object> validationResult) {
        // 分控模式：整体代理到总控（扣点 + 写 automation_usage 都在总控执行）
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            proxyDeductAndUsageToMaster(merchantId, userId, taskId, streamingAccountId,
                    streamingAccountName, gameAccountsCount, hostsCount, validationResult);
            return;
        }

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

        // 包月订阅和月度免费额度都记录为 monthly，便于后续同月再次启动时识别免费资格。
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

    /**
     * 写入 Step4 上报的可计费事件，并按幂等键扣点。
     *
     * <p>必填字段为 gameAccountId、billingUnit、unitIndex；sessionId 优先取 Agent
     * payload，缺省时回退任务当前 sessionId。重复事件只返回 duplicate=true，不再次扣点。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> recordBillableEvent(Task task, Map<String, Object> payload) {
        // 分控模式：整体代理到总控（写 billing_event + 扣点都在总控执行）
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return proxyBillableEventToMaster(task, payload);
        }

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

        // 幂等键包含 sessionId，保证同一长寿命任务的多轮自动化不会互相吞并计费事件。
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
            // Agent 可能因超时重试回调；数据库唯一键兜底确保同一事件最多扣点一次。
            Map<String, Object> duplicate = new HashMap<>();
            duplicate.put("recorded", true);
            duplicate.put("duplicate", true);
            duplicate.put("idempotentKey", idempotentKey);
            duplicate.put("pointsDeducted", 0);
            return duplicate;
        }

        int points = event.getPointsDeducted() != null ? event.getPointsDeducted() : 0;
        if (points > 0) {
            // 扣点与事件记录在同一事务中，余额不足会回滚事件，避免“记账成功但未扣费”。
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
        // 每种自动化类型只接受自己的结算单元，防止 Agent 误报造成跨模式扣点。
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
        // 只有比赛完成事件推进场次数；转会轮次仅可能更新金币变化。
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

    /** 解析 JSON 数组字符串为 List<String> */
    private List<String> parseJsonArray(String json) {
        List<String> result = new ArrayList<>();
        if (json == null || json.isEmpty()) {
            return result;
        }
        try {
            result = objectMapper.readValue(json, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {});
        } catch (Exception e) {
            log.warn("解析JSON数组失败: {}", json, e);
        }
        return result;
    }

    /**
     * 检查订阅是否覆盖指定资源。
     *
     * <p>方案A（商户级包月）：激活码不绑定具体 resource ID，只要 subscription_type 匹配即返回 true。
     * "full"（全功能包月）覆盖所有资源类型。
     * 若 subscription 绑定了具体 resource ID（boundResourceIds 非空），则校验 targetId 是否在列表中。
     *
     * @param subscriptions 生效中的订阅列表
     * @param type          资源类型简写："window"/"account"/"host"
     * @param targetId      目标资源 ID
     * @return true 表示有订阅覆盖该资源
     */
    private boolean checkSubscription(List<Subscription> subscriptions, String type, String targetId) {
        if (subscriptions == null || targetId == null) {
            return false;
        }
        // 资源类型简写 → DB subscription_type 映射
        String dbType = switch (type) {
            case "window" -> "window_account";
            case "account" -> "account";
            case "host" -> "host";
            default -> type;
        };
        for (Subscription sub : subscriptions) {
            String subType = sub.getSubscriptionType();
            // full（全功能包月）覆盖所有资源类型
            if ("full".equals(subType)) {
                return true;
            }
            if (dbType.equals(subType)) {
                // 商户级包月：未绑定具体资源 → 该商户所有同类资源都享受包月
                String boundIds = sub.getBoundResourceIds();
                if (boundIds == null || boundIds.isEmpty()) {
                    return true;
                }
                // 定向绑定：校验 targetId 是否在绑定列表中
                List<String> ids = parseJsonArray(boundIds);
                if (ids.isEmpty()) {
                    return true;
                }
                if (ids.contains(targetId)) {
                    return true;
                }
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

    @SuppressWarnings("unchecked")
    private Map<String, Object> proxyValidateToMaster(String merchantId, String streamingAccountId,
                                                        List<GameAccount> gameAccounts, List<XboxHost> hosts) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-License-Key", licenseKey);
            headers.set("X-License-Secret", licenseSecret);
            headers.setContentType(MediaType.APPLICATION_JSON);
            Map<String, Object> body = new HashMap<>();
            body.put("streamingAccountId", streamingAccountId);
            if (gameAccounts != null) body.put("gameAccountIds", gameAccounts.stream().map(GameAccount::getId).toList());
            // 分控的游戏账号/主机 ID 在总控库不存在，传数量让总控直接用于计费计算
            body.put("accountCount", gameAccounts != null ? gameAccounts.size() : 0);
            body.put("hostCount", hosts != null ? hosts.size() : 0);
            String url = masterUrl.replaceAll("/+$", "") + "/api/tenant/billing/validate";
            ResponseEntity<Map> resp = new RestTemplate().postForEntity(url, new HttpEntity<>(body, headers), Map.class);
            Map<String, Object> result = resp.getBody();
            if (result != null && Integer.valueOf(200).equals(result.get("code"))) {
                return (Map<String, Object>) result.get("data");
            }
            return Map.of("canStart", false, "errors", List.of("总控校验失败"));
        } catch (Exception e) {
            return Map.of("canStart", false, "errors", List.of("总控请求失败: " + e.getMessage()));
        }
    }

    /**
     * 分控代理：启动用量 + 扣点 → 总控 /api/tenant/automation/usage。
     *
     * <p>方案A：计费全归总控。分控不写本地 automation_usage，全部由总控处理。
     */
    @SuppressWarnings("unchecked")
    private void proxyDeductAndUsageToMaster(String merchantId, String userId, String taskId,
                                              String streamingAccountId, String streamingAccountName,
                                              int gameAccountsCount, int hostsCount,
                                              Map<String, Object> validationResult) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-License-Key", licenseKey);
            headers.set("X-License-Secret", licenseSecret);
            headers.setContentType(MediaType.APPLICATION_JSON);

            Map<String, Object> body = new HashMap<>();
            body.put("merchantId", merchantId);
            body.put("userId", userId);
            body.put("taskId", taskId);
            body.put("streamingAccountId", streamingAccountId);
            body.put("streamingAccountName", streamingAccountName);
            body.put("gameAccountsCount", gameAccountsCount);
            body.put("hostsCount", hostsCount);
            body.put("totalPoints", validationResult.getOrDefault("totalPoints", 0));
            body.put("chargeType", validationResult.getOrDefault("chargeType", ""));

            // 计算资源类型/ID/名称/扣点模式（与总控模式逻辑一致）
            String chargeType = (String) validationResult.getOrDefault("chargeType", "");
            int accountCount = (Integer) validationResult.getOrDefault("accountCount", 0);
            int hostCount = (Integer) validationResult.getOrDefault("hostCount", 0);
            int accountPrice = (Integer) validationResult.getOrDefault("accountPrice", 5);
            int hostPrice = (Integer) validationResult.getOrDefault("hostPrice", 20);
            int windowPrice = (Integer) validationResult.getOrDefault("windowPrice", 10);

            List<GameAccount> gameAccounts = (List<GameAccount>) validationResult.get("gameAccounts");
            List<XboxHost> hosts = (List<XboxHost>) validationResult.get("hosts");

            String resourceType;
            String resourceId;
            String resourceName;
            String chargeMode;
            int pointsDeducted;

            if (chargeType.startsWith("subscription_") || chargeType.startsWith("monthly_")) {
                if (chargeType.contains("window")) {
                    resourceType = "window"; resourceId = streamingAccountId; resourceName = streamingAccountName;
                } else if (chargeType.contains("account")) {
                    resourceType = "account";
                    resourceId = gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getId() : null;
                    resourceName = gameAccounts != null && !gameAccounts.isEmpty() ? gameAccounts.get(0).getGameName() : null;
                } else {
                    resourceType = "host";
                    resourceId = hosts != null && !hosts.isEmpty() ? hosts.get(0).getId() : null;
                    resourceName = hosts != null && !hosts.isEmpty() ? hosts.get(0).getName() : null;
                }
                chargeMode = "monthly";
                pointsDeducted = 0;
            } else if (chargeType.contains("account")) {
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
                resourceType = "window"; resourceId = streamingAccountId; resourceName = streamingAccountName;
                chargeMode = "per_use"; pointsDeducted = windowPrice;
            }

            body.put("resourceType", resourceType);
            body.put("resourceId", resourceId != null ? resourceId : "");
            body.put("resourceName", resourceName != null ? resourceName : "");
            body.put("chargeMode", chargeMode);
            body.put("pointsDeducted", pointsDeducted);

            String url = masterUrl.replaceAll("/+$", "") + "/api/tenant/automation/usage";
            ResponseEntity<Map> resp = new RestTemplate().postForEntity(url, new HttpEntity<>(body, headers), Map.class);
            Map<String, Object> result = resp.getBody();
            if (result == null || !Integer.valueOf(200).equals(result.get("code"))) {
                String msg = result != null ? String.valueOf(result.get("message")) : "总控无响应";
                throw new BusinessException(500, "分控代理扣点失败: " + msg);
            }
            log.info("分控代理用量记录成功 - taskId: {}, points: {}", taskId, validationResult.get("totalPoints"));
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(500, "分控代理用量记录失败: " + e.getMessage());
        }
    }

    /**
     * 分控代理：Step4 计费事件 + 扣点 → 总控 /api/tenant/automation/billing-event。
     *
     * <p>方案A：计费全归总控。分控不写本地 billing_event，全部由总控处理。
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> proxyBillableEventToMaster(Task task, Map<String, Object> payload) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-License-Key", licenseKey);
            headers.set("X-License-Secret", licenseSecret);
            headers.setContentType(MediaType.APPLICATION_JSON);

            // 构造与总控 recordBillableEvent 相同的参数
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

            String rawIdempotentKey = String.join(":",
                    task.getId(),
                    sessionId != null ? sessionId : "-",
                    gameAccountId,
                    gameActionType,
                    billingUnit,
                    String.valueOf(unitIndex));
            String idempotentKey = "bill:" + java.util.UUID.nameUUIDFromBytes(
                    rawIdempotentKey.getBytes(StandardCharsets.UTF_8));

            Map<String, Object> body = new HashMap<>();
            body.put("merchantId", task.getMerchantId());
            body.put("taskId", task.getId());
            body.put("sessionId", sessionId != null ? sessionId : "");
            body.put("streamingAccountId", task.getStreamingAccountId() != null ? task.getStreamingAccountId() : "");
            body.put("gameAccountId", gameAccountId != null ? gameAccountId : "");
            body.put("gameActionType", gameActionType);
            body.put("billingUnit", billingUnit);
            body.put("unitIndex", unitIndex != null ? unitIndex : 0);
            body.put("idempotentKey", idempotentKey);
            body.put("pointsDeducted", resolveEventPoints(gameActionType, billingUnit));
            body.put("coinsDelta", intValue(payload.get("coinsDelta")) != null ? intValue(payload.get("coinsDelta")) : 0);
            try {
                body.put("payload", objectMapper.writeValueAsString(payload));
            } catch (Exception e) {
                body.put("payload", "{}");
            }

            String url = masterUrl.replaceAll("/+$", "") + "/api/tenant/automation/billing-event";
            ResponseEntity<Map> resp = new RestTemplate().postForEntity(url, new HttpEntity<>(body, headers), Map.class);
            Map<String, Object> result = resp.getBody();
            if (result != null && Integer.valueOf(200).equals(result.get("code"))) {
                return (Map<String, Object>) result.get("data");
            }
            String msg = result != null ? String.valueOf(result.get("message")) : "总控无响应";
            throw new BusinessException(500, "分控代理计费事件失败: " + msg);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(500, "分控代理计费事件失败: " + e.getMessage());
        }
    }
}
