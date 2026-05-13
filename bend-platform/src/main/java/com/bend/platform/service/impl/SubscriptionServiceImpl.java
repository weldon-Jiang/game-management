package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Subscription;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.SubscriptionMapper;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.service.XboxHostService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class SubscriptionServiceImpl implements SubscriptionService {

    private final SubscriptionMapper subscriptionMapper;
    private final GameAccountService gameAccountService;
    private final XboxHostService xboxHostService;
    private final GameAccountMapper gameAccountMapper;
    private final ObjectMapper objectMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Subscription createSubscription(String merchantId, String userId, String activationCodeId,
                                         String subscriptionType, String boundResourceType,
                                         String boundResourceIds, String boundResourceNames,
                                         LocalDateTime startTime, LocalDateTime endTime,
                                         Integer originalPrice, Integer discountPrice) {
        log.info("createSubscription 开始 - merchantId: {}, activationCodeId: {}, type: {}, startTime: {}, endTime: {}",
                merchantId, activationCodeId, subscriptionType, startTime, endTime);

        Subscription subscription = new Subscription();
        subscription.setMerchantId(merchantId);
        subscription.setUserId(userId);
        subscription.setActivationCodeId(activationCodeId);
        subscription.setSubscriptionType(subscriptionType);
        subscription.setBoundResourceType(boundResourceType);
        subscription.setBoundResourceIds(boundResourceIds);
        subscription.setBoundResourceNames(boundResourceNames);
        subscription.setStartTime(startTime);
        subscription.setEndTime(endTime);
        subscription.setOriginalPrice(originalPrice);
        subscription.setDiscountPrice(discountPrice);
        subscription.setStatus("active");

        log.info("createSubscription 插入记录 - subscription: {}", subscription);
        subscriptionMapper.insert(subscription);
        log.info("createSubscription 完成 - id: {}, merchantId: {}, type: {}", subscription.getId(), merchantId, subscriptionType);

        return subscription;
    }

    @Override
    public Subscription getCurrentActiveSubscription(String merchantId) {
        LocalDateTime now = LocalDateTime.now();
        LambdaQueryWrapper<Subscription> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Subscription::getMerchantId, merchantId)
                .eq(Subscription::getStatus, "active")
                .le(Subscription::getStartTime, now)
                .gt(Subscription::getEndTime, now)
                .orderByDesc(Subscription::getEndTime)
                .last("LIMIT 1");
        return subscriptionMapper.selectOne(wrapper);
    }

    @Override
    public Subscription getLatestActiveNonPointsSubscription(String merchantId) {
        LocalDateTime now = LocalDateTime.now();
        LambdaQueryWrapper<Subscription> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Subscription::getMerchantId, merchantId)
                .eq(Subscription::getStatus, "active")
                .ne(Subscription::getSubscriptionType, "points")
                .gt(Subscription::getEndTime, now)
                .orderByDesc(Subscription::getEndTime)
                .last("LIMIT 1");
        return subscriptionMapper.selectOne(wrapper);
    }

    @Override
    public List<Subscription> getActiveSubscriptions(String merchantId) {
        LocalDateTime now = LocalDateTime.now();
        LambdaQueryWrapper<Subscription> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Subscription::getMerchantId, merchantId)
                .eq(Subscription::getStatus, "active")
                .le(Subscription::getStartTime, now)
                .gt(Subscription::getEndTime, now)
                .orderByDesc(Subscription::getEndTime);
        return subscriptionMapper.selectList(wrapper);
    }

    @Override
    public Subscription getById(String subscriptionId) {
        return subscriptionMapper.selectById(subscriptionId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Subscription renewSubscription(String subscriptionId, LocalDateTime newEndTime) {
        Subscription subscription = subscriptionMapper.selectById(subscriptionId);
        if (subscription == null) {
            throw new BusinessException(ResultCode.System.NOT_FOUND, "订阅不存在");
        }
        subscription.setEndTime(newEndTime);
        subscriptionMapper.updateById(subscription);
        log.info("续费订阅 - subscriptionId: {}, newEndTime: {}", subscriptionId, newEndTime);
        return subscription;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void cancelSubscription(String subscriptionId) {
        Subscription subscription = subscriptionMapper.selectById(subscriptionId);
        if (subscription == null) {
            throw new BusinessException(ResultCode.System.NOT_FOUND, "订阅不存在");
        }
        subscription.setStatus("cancelled");
        subscriptionMapper.updateById(subscription);
        log.info("取消订阅 - subscriptionId: {}", subscriptionId);
    }

    @Override
    public IPage<Subscription> pageSubscriptions(String merchantId, int pageNum, int pageSize, String status) {
        LambdaQueryWrapper<Subscription> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Subscription::getMerchantId, merchantId);
        if (status != null && !status.isEmpty()) {
            wrapper.eq(Subscription::getStatus, status);
        }
        wrapper.orderByDesc(Subscription::getCreatedTime);
        Page<Subscription> page = new Page<>(pageNum, pageSize);
        return subscriptionMapper.selectPage(page, wrapper);
    }

    @Override
    public List<String> validateStreamingAccountForAutomation(String merchantId, String streamingAccountId) {
        List<String> errors = new ArrayList<>();
        Subscription subscription = getCurrentActiveSubscription(merchantId);

        if (subscription == null) {
            errors.add("当前没有有效的包月，请先购买订阅");
            return errors;
        }

        String subscriptionType = subscription.getSubscriptionType();

        if ("window_account".equals(subscriptionType)) {
            List<String> boundIds = parseJsonArray(subscription.getBoundResourceIds());
            if (!boundIds.contains(streamingAccountId)) {
                errors.add("选择的流媒体账号不在订阅范围内");
            }
        }

        return errors;
    }

    @Override
    public List<String> validateGameAccountsForAutomation(String merchantId, List<String> gameAccountIds) {
        List<String> errors = new ArrayList<>();
        Subscription subscription = getCurrentActiveSubscription(merchantId);

        if (subscription == null) {
            errors.add("当前没有有效的包月，请先购买订阅");
            return errors;
        }

        String subscriptionType = subscription.getSubscriptionType();

        if ("account".equals(subscriptionType)) {
            List<String> boundGameAccountIds = parseJsonArray(subscription.getBoundResourceIds());

            for (String gameAccountId : gameAccountIds) {
                if (!boundGameAccountIds.contains(gameAccountId)) {
                    errors.add("部分游戏账号不在订阅范围内");
                    break;
                }
            }

            if (errors.isEmpty()) {
                boolean hasValidGameAccount = false;
                for (String gameAccountId : gameAccountIds) {
                    GameAccount gameAccount = gameAccountMapper.selectById(gameAccountId);
                    if (gameAccount != null && gameAccount.getStreamingId() != null) {
                        hasValidGameAccount = true;
                        break;
                    }
                }
                if (!hasValidGameAccount) {
                    errors.add("订阅的游戏账号都未绑定流媒体账号，无法启动自动化");
                }
            }
        }

        return errors;
    }

    @Override
    public List<String> validateXboxHostForAutomation(String merchantId, String xboxHostId) {
        List<String> errors = new ArrayList<>();
        Subscription subscription = getCurrentActiveSubscription(merchantId);

        if (subscription == null) {
            errors.add("当前没有有效的包月，请先购买订阅");
            return errors;
        }

        String subscriptionType = subscription.getSubscriptionType();

        if ("host".equals(subscriptionType)) {
            List<String> boundIds = parseJsonArray(subscription.getBoundResourceIds());
            if (!boundIds.contains(xboxHostId)) {
                errors.add("选择的Xbox主机不在订阅范围内");
            }
        }

        return errors;
    }

    @Override
    public Map<String, Object> validateAutomationRequest(String merchantId, String streamingAccountId,
                                                        List<String> gameAccountIds, String xboxHostId) {
        Map<String, Object> result = new HashMap<>();
        List<String> allErrors = new ArrayList<>();
        Subscription subscription = getCurrentActiveSubscription(merchantId);

        if (subscription == null) {
            allErrors.add("当前没有有效的包月，请先购买订阅");
            result.put("canStart", false);
            result.put("errors", allErrors);
            result.put("subscriptionType", null);
            result.put("chargeType", null);
            return result;
        }

        String subscriptionType = subscription.getSubscriptionType();
        result.put("subscriptionType", subscriptionType);

        if ("window_account".equals(subscriptionType)) {
            List<String> boundStreamingIds = parseJsonArray(subscription.getBoundResourceIds());
            if (!boundStreamingIds.contains(streamingAccountId)) {
                allErrors.add("选择的流媒体账号不在订阅范围内");
            }
        }

        if ("account".equals(subscriptionType)) {
            List<String> boundGameAccountIds = parseJsonArray(subscription.getBoundResourceIds());

            for (String gameAccountId : gameAccountIds) {
                if (!boundGameAccountIds.contains(gameAccountId)) {
                    allErrors.add("部分游戏账号不在订阅范围内");
                    break;
                }
            }

            if (allErrors.isEmpty()) {
                boolean hasValidGameAccount = false;
                for (String gameAccountId : gameAccountIds) {
                    GameAccount gameAccount = gameAccountMapper.selectById(gameAccountId);
                    if (gameAccount != null && gameAccount.getStreamingId() != null) {
                        hasValidGameAccount = true;
                        break;
                    }
                }
                if (!hasValidGameAccount) {
                    allErrors.add("订阅的游戏账号都未绑定流媒体账号，无法启动自动化");
                }
            }
        }

        if ("host".equals(subscriptionType)) {
            if (xboxHostId == null || xboxHostId.isEmpty()) {
                allErrors.add("Xbox主机包月必须选择Xbox主机");
            } else {
                List<String> boundXboxHostIds = parseJsonArray(subscription.getBoundResourceIds());
                if (!boundXboxHostIds.contains(xboxHostId)) {
                    allErrors.add("选择的Xbox主机不在订阅范围内");
                }
            }
        }

        if (allErrors.isEmpty()) {
            result.put("canStart", true);
            result.put("chargeType", "monthly");
            result.put("message", "使用" + getSubscriptionTypeName(subscriptionType) + "，不扣点");
        } else {
            result.put("canStart", false);
            result.put("errors", allErrors);
        }

        return result;
    }

    @Override
    public List<String> getAvailableGameAccounts(String merchantId, String streamingAccountId) {
        Subscription subscription = getCurrentActiveSubscription(merchantId);
        List<String> result = new ArrayList<>();

        if (subscription == null) {
            return result;
        }

        String subscriptionType = subscription.getSubscriptionType();

        if ("account".equals(subscriptionType)) {
            List<String> boundGameAccountIds = parseJsonArray(subscription.getBoundResourceIds());
            for (String gameAccountId : boundGameAccountIds) {
                GameAccount gameAccount = gameAccountMapper.selectById(gameAccountId);
                if (gameAccount != null && gameAccount.getStreamingId() != null) {
                    result.add(gameAccountId);
                }
            }
        } else if ("window_account".equals(subscriptionType) ||
                   "full".equals(subscriptionType) ||
                   "points".equals(subscriptionType)) {
            List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(streamingAccountId);
            result = gameAccounts.stream().map(GameAccount::getId).collect(Collectors.toList());
        }

        return result;
    }

    @Override
    public List<String> getAvailableXboxHosts(String merchantId, String streamingAccountId) {
        Subscription subscription = getCurrentActiveSubscription(merchantId);
        List<String> result = new ArrayList<>();

        if (subscription == null) {
            return result;
        }

        String subscriptionType = subscription.getSubscriptionType();

        if ("host".equals(subscriptionType)) {
            return parseJsonArray(subscription.getBoundResourceIds());
        } else {
            List<XboxHost> hosts = xboxHostService.findAllByMerchantId(merchantId);
            result = hosts.stream()
                    .filter(host -> "online".equals(host.getStatus()) || "active".equals(host.getStatus()))
                    .map(XboxHost::getId)
                    .collect(Collectors.toList());
        }

        return result;
    }

    private String getSubscriptionTypeName(String type) {
        if (type == null) return "未知";
        switch (type) {
            case "window_account": return "流媒体账号包月";
            case "account": return "游戏账号包月";
            case "host": return "Xbox主机包月";
            case "full": return "全功能包月";
            case "points": return "点数充值";
            default: return type;
        }
    }

    private List<String> parseJsonArray(String json) {
        List<String> result = new ArrayList<>();
        if (json == null || json.isEmpty()) {
            return result;
        }
        try {
            result = objectMapper.readValue(json, new TypeReference<List<String>>() {});
        } catch (Exception e) {
            log.warn("解析JSON数组失败: {}", json, e);
        }
        return result;
    }

    @Override
    public int unbindDevice(String merchantId, String type, String deviceId, String userId) {
        log.info("解绑设备 - merchantId: {}, type: {}, deviceId: {}, userId: {}", merchantId, type, deviceId, userId);
        return 0;
    }

    @Override
    public boolean isDeviceBound(String merchantId, String type, String deviceId) {
        return false;
    }
}
