package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.MerchantLicense;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface MerchantLicenseMapper extends BaseMapper<MerchantLicense> {

    /**
     * 按 license_key 查询有效记录(未逻辑删除)。
     */
    @Select("SELECT * FROM merchant_license WHERE license_key = #{licenseKey} AND deleted = 0 LIMIT 1")
    MerchantLicense selectByLicenseKey(@Param("licenseKey") String licenseKey);

    /**
     * 查询商户当前有效 license(active 状态,未到期,未吊销)。
     */
    @Select("SELECT * FROM merchant_license WHERE merchant_id = #{merchantId} AND status = 'active' AND deleted = 0 ORDER BY created_time DESC LIMIT 1")
    MerchantLicense selectActiveByMerchantId(@Param("merchantId") String merchantId);
}
