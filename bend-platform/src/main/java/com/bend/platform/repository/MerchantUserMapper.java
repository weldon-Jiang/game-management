package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.MerchantUser;
import org.apache.ibatis.annotations.Mapper;

/**
 * 商户用户Mapper接口
 */
@Mapper
public interface MerchantUserMapper extends BaseMapper<MerchantUser> {
}