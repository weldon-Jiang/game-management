package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.TemplatePageRequest;
import com.bend.platform.entity.Template;
import java.util.List;

/**
 * 模板服务接口
 */
public interface TemplateService {

    Template create(Template template);

    Template findById(String id);

    List<Template> findAll();

    List<Template> findByCategory(String category);

    List<Template> findByGame(String game);

    IPage<Template> findPage(TemplatePageRequest request);

    Template update(Template template);

    void delete(String id);

    void incrementUsageCount(String id);
}
