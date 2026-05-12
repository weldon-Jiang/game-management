package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class VipLevelService {

    private final MerchantGroupMapper merchantGroupMapper;
    private final MerchantMapper merchantMapper;

    public int calculateVipLevel(int totalAmount) {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.le(MerchantGroup::getAmountThreshold, totalAmount)
               .eq(MerchantGroup::getStatus, "active")
               .orderByDesc(MerchantGroup::getVipLevel)
               .last("LIMIT 1");
        MerchantGroup group = merchantGroupMapper.selectOne(wrapper);
        return group != null ? group.getVipLevel() : 0;
    }

    public MerchantGroup getMerchantGroupByVipLevel(int vipLevel) {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getVipLevel, vipLevel)
               .eq(MerchantGroup::getStatus, "active")
               .last("LIMIT 1");
        return merchantGroupMapper.selectOne(wrapper);
    }

    public Integer checkUpgrade(String merchantId, int newTotalRecharged) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            return null;
        }

        int currentVipLevel = merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;
        int newVipLevel = calculateVipLevel(newTotalRecharged);

        if (newVipLevel > currentVipLevel) {
            LambdaUpdateWrapper<Merchant> updateWrapper = new LambdaUpdateWrapper<>();
            updateWrapper.eq(Merchant::getId, merchantId)
                    .set(Merchant::getVipLevel, newVipLevel);
            merchantMapper.update(null, updateWrapper);
            return newVipLevel;
        }

        return null;
    }

    public VipInfo getVipInfo(String merchantId) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            return null;
        }

        VipInfo vipInfo = new VipInfo();
        vipInfo.setMerchantId(merchant.getId());
        vipInfo.setMerchantName(merchant.getName());
        vipInfo.setVipLevel(merchant.getVipLevel() != null ? merchant.getVipLevel() : 0);
        vipInfo.setTotalAmount(merchant.getTotalAmount() != null ? merchant.getTotalAmount() : 0);

        MerchantGroup currentGroup = getMerchantGroupByVipLevel(vipInfo.getVipLevel());
        if (currentGroup != null) {
            vipInfo.setCurrentGroupName(currentGroup.getName());
            vipInfo.setNextGroupName(getNextGroupName(vipInfo.getVipLevel()));
            vipInfo.setAmountToNextLevel(getAmountToNextLevel(vipInfo.getVipLevel(), vipInfo.getTotalAmount()));
        }

        return vipInfo;
    }

    public List<VipLevelInfo> getAllVipLevels() {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
               .orderByAsc(MerchantGroup::getVipLevel);
        List<MerchantGroup> groups = merchantGroupMapper.selectList(wrapper);

        return groups.stream().map(group -> {
            VipLevelInfo info = new VipLevelInfo();
            info.setVipLevel(group.getVipLevel());
            info.setGroupName(group.getName());
            info.setAmountThreshold(group.getAmountThreshold());
            info.setWindowOriginalPrice(group.getWindowOriginalPrice());
            info.setWindowDiscountPrice(group.getWindowDiscountPrice());
            info.setAccountOriginalPrice(group.getAccountOriginalPrice());
            info.setAccountDiscountPrice(group.getAccountDiscountPrice());
            info.setHostOriginalPrice(group.getHostOriginalPrice());
            info.setHostDiscountPrice(group.getHostDiscountPrice());
            info.setFullOriginalPrice(group.getFullOriginalPrice());
            info.setFullDiscountPrice(group.getFullDiscountPrice());
            info.setPointsOriginalPrice(group.getPointsOriginalPrice());
            info.setPointsDiscountPrice(group.getPointsDiscountPrice());
            return info;
        }).collect(Collectors.toList());
    }

    private String getNextGroupName(int currentLevel) {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
               .gt(MerchantGroup::getVipLevel, currentLevel)
               .orderByAsc(MerchantGroup::getVipLevel)
               .last("LIMIT 1");
        MerchantGroup nextGroup = merchantGroupMapper.selectOne(wrapper);
        return nextGroup != null ? nextGroup.getName() : null;
    }

    private Integer getAmountToNextLevel(int currentLevel, int totalAmount) {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
               .gt(MerchantGroup::getVipLevel, currentLevel)
               .orderByAsc(MerchantGroup::getVipLevel)
               .last("LIMIT 1");
        MerchantGroup nextGroup = merchantGroupMapper.selectOne(wrapper);
        if (nextGroup == null) {
            return null;
        }
        int amountNeeded = nextGroup.getAmountThreshold() - totalAmount;
        return amountNeeded > 0 ? amountNeeded : 0;
    }

    public static class VipInfo {
        private String merchantId;
        private String merchantName;
        private Integer vipLevel;
        private Integer totalAmount;
        private String currentGroupName;
        private String nextGroupName;
        private Integer amountToNextLevel;

        public String getMerchantId() { return merchantId; }
        public void setMerchantId(String merchantId) { this.merchantId = merchantId; }
        public String getMerchantName() { return merchantName; }
        public void setMerchantName(String merchantName) { this.merchantName = merchantName; }
        public Integer getVipLevel() { return vipLevel; }
        public void setVipLevel(Integer vipLevel) { this.vipLevel = vipLevel; }
        public Integer getTotalAmount() { return totalAmount; }
        public void setTotalAmount(Integer totalAmount) { this.totalAmount = totalAmount; }
        public String getCurrentGroupName() { return currentGroupName; }
        public void setCurrentGroupName(String currentGroupName) { this.currentGroupName = currentGroupName; }
        public String getNextGroupName() { return nextGroupName; }
        public void setNextGroupName(String nextGroupName) { this.nextGroupName = nextGroupName; }
        public Integer getAmountToNextLevel() { return amountToNextLevel; }
        public void setAmountToNextLevel(Integer amountToNextLevel) { this.amountToNextLevel = amountToNextLevel; }
    }

    public static class VipLevelInfo {
        private Integer vipLevel;
        private String groupName;
        private Integer amountThreshold;
        private Integer windowOriginalPrice;
        private Integer windowDiscountPrice;
        private Integer accountOriginalPrice;
        private Integer accountDiscountPrice;
        private Integer hostOriginalPrice;
        private Integer hostDiscountPrice;
        private Integer fullOriginalPrice;
        private Integer fullDiscountPrice;
        private Integer pointsOriginalPrice;
        private Integer pointsDiscountPrice;

        public Integer getVipLevel() { return vipLevel; }
        public void setVipLevel(Integer vipLevel) { this.vipLevel = vipLevel; }
        public String getGroupName() { return groupName; }
        public void setGroupName(String groupName) { this.groupName = groupName; }
        public Integer getAmountThreshold() { return amountThreshold; }
        public void setAmountThreshold(Integer amountThreshold) { this.amountThreshold = amountThreshold; }
        public Integer getWindowOriginalPrice() { return windowOriginalPrice; }
        public void setWindowOriginalPrice(Integer windowOriginalPrice) { this.windowOriginalPrice = windowOriginalPrice; }
        public Integer getWindowDiscountPrice() { return windowDiscountPrice; }
        public void setWindowDiscountPrice(Integer windowDiscountPrice) { this.windowDiscountPrice = windowDiscountPrice; }
        public Integer getAccountOriginalPrice() { return accountOriginalPrice; }
        public void setAccountOriginalPrice(Integer accountOriginalPrice) { this.accountOriginalPrice = accountOriginalPrice; }
        public void setAccountDiscountPrice(Integer accountDiscountPrice) { this.accountDiscountPrice = accountDiscountPrice; }
        public Integer getHostOriginalPrice() { return hostOriginalPrice; }
        public void setHostOriginalPrice(Integer hostOriginalPrice) { this.hostOriginalPrice = hostOriginalPrice; }
        public Integer getHostDiscountPrice() { return hostDiscountPrice; }
        public void setHostDiscountPrice(Integer hostDiscountPrice) { this.hostDiscountPrice = hostDiscountPrice; }
        public Integer getFullOriginalPrice() { return fullOriginalPrice; }
        public void setFullOriginalPrice(Integer fullOriginalPrice) { this.fullOriginalPrice = fullOriginalPrice; }
        public Integer getFullDiscountPrice() { return fullDiscountPrice; }
        public void setFullDiscountPrice(Integer fullDiscountPrice) { this.fullDiscountPrice = fullDiscountPrice; }
        public Integer getPointsOriginalPrice() { return pointsOriginalPrice; }
        public void setPointsOriginalPrice(Integer pointsOriginalPrice) { this.pointsOriginalPrice = pointsOriginalPrice; }
        public Integer getPointsDiscountPrice() { return pointsDiscountPrice; }
        public void setPointsDiscountPrice(Integer pointsDiscountPrice) { this.pointsDiscountPrice = pointsDiscountPrice; }
    }
}