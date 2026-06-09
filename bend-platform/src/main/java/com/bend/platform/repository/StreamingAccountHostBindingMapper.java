package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.StreamingAccountHostBinding;
import org.apache.ibatis.annotations.Mapper;

/**
 * 流媒体账号与主机绑定 Mapper。
 */
@Mapper
public interface StreamingAccountHostBindingMapper extends BaseMapper<StreamingAccountHostBinding> {
}
