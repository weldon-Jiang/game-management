package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.entity.RechargeCard;
import com.bend.platform.entity.RechargeCardBatch;

import java.util.List;

/**
 * 充值卡服务接口
 */
public interface RechargeCardService {

    /**
     * 使用充值卡充值
     */
    void useCard(String cardNo, String cardPwd);

    /**
     * 生成充值卡批次
     */
    RechargeCardBatch createBatch(String name, String cardType, String targetMerchantId,
                                 int count, int denomination, int bonusPoints, int price, int validDays);

    /**
     * 查询批次列表
     */
    IPage<RechargeCardBatch> pageBatches(int pageNum, int pageSize);

    /**
     * 查询卡密列表
     */
    IPage<RechargeCard> pageCards(String batchId, String status, int pageNum, int pageSize);

    /**
     * 根据卡号查询卡密
     */
    RechargeCard getByCardNo(String cardNo);

    /**
     * 批量查询卡密
     */
    List<RechargeCard> getByBatchId(String batchId);

    /**
     * 激活卡密(设置已售出)
     */
    void activateCard(String cardNo, String merchantId);

    /**
     * 导出卡密
     */
    List<RechargeCard> exportCards(String batchId);
}
