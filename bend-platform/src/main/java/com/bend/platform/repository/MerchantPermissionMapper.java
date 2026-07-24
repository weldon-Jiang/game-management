package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.MerchantPermission;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface MerchantPermissionMapper extends BaseMapper<MerchantPermission> {

    /**
     * 查询商户的权限记录（一个商户只有一条）。
     */
    @Select("SELECT * FROM merchant_permission WHERE merchant_id = #{merchantId} AND deleted = 0 LIMIT 1")
    MerchantPermission selectByMerchantId(@Param("merchantId") String merchantId);
}
