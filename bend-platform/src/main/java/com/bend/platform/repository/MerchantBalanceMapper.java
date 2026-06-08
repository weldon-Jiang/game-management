package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.MerchantBalance;
import org.apache.ibatis.annotations.Mapper;

/**
 * 商户点数余额Mapper接口
 */
@Mapper
public interface MerchantBalanceMapper extends BaseMapper<MerchantBalance> {
}
