package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.DeviceBinding;
import org.apache.ibatis.annotations.Mapper;

/**
 * 设备绑定Mapper接口
 */
@Mapper
public interface DeviceBindingMapper extends BaseMapper<DeviceBinding> {
}
