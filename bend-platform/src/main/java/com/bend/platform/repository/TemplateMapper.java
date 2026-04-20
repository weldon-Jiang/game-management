package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.Template;
import org.apache.ibatis.annotations.Mapper;

/**
 * 模板Mapper
 */
@Mapper
public interface TemplateMapper extends BaseMapper<Template> {
}
