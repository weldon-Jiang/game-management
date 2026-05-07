package com.bend.platform.service;

import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.XboxHost;

import java.util.List;
import java.util.Map;

public interface AutomationUsageService {

    /**
     * 校验并计算启动自动化需要的点数
     *
     *  商户ID
     *  串流账号ID
     *  游戏账号列表
     *  主机列表
     *  包含校验结果和需要的点数
     */
    Map<String, Object> validateAndCalculatePoints(String merchantId, String streamingAccountId,
                                                List<GameAccount> gameAccounts, List<XboxHost> hosts);

    /**
     * 执行扣点并记录使用情况
     *
     *  商户ID
     *  用户ID
     *  任务ID
     *  串流账号ID
     *  串流账号名称
     *  游戏账号数量
     *  主机数量
     *  校验结果
     */
    void deductPointsAndRecordUsage(String merchantId, String userId, String taskId,
                                   String streamingAccountId, String streamingAccountName,
                                   int gameAccountsCount, int hostsCount, Map<String, Object> validationResult);
}
