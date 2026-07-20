package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.LicenseVerifyCache;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface LicenseVerifyCacheMapper extends BaseMapper<LicenseVerifyCache> {

    @Select("SELECT * FROM license_verify_cache WHERE license_key = #{licenseKey} LIMIT 1")
    LicenseVerifyCache selectByLicenseKey(@Param("licenseKey") String licenseKey);
}
