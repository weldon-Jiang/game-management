package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.TemplatePageRequest;
import com.bend.platform.entity.Template;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.TemplateMapper;
import com.bend.platform.service.TemplateService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;

/**
 * 模板服务实现类
 *
 * 功能说明：
 * - 管理图像识别模板的CRUD操作
 * - 支持模板的类型和游戏分类
 *
 * 模板类型：
 * - ui_button: UI按钮
 * - ui_icon: UI图标
 * - ui_text: UI文本
 * - game_element: 游戏元素
 * - scene_background: 场景背景
 *
 * 主要功能：
 * - 创建模板
 * - 分页查询模板
 * - 根据条件查询模板
 * - 更新模板
 * - 删除模板
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TemplateServiceImpl implements TemplateService {

    private final TemplateMapper templateMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Template create(Template template) {
        templateMapper.insert(template);
        log.info("创建模板 - ID: {}, 名称: {}", template.getId(), template.getName());
        return template;
    }

    @Override
    public Template findById(String id) {
        return templateMapper.selectById(id);
    }

    @Override
    public List<Template> findAll() {
        LambdaQueryWrapper<Template> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Template::getDeleted, false);
        wrapper.eq(Template::getStatus, 1);
        wrapper.orderByDesc(Template::getCreatedTime);
        return templateMapper.selectList(wrapper);
    }

    @Override
    public List<Template> findByCategory(String category) {
        LambdaQueryWrapper<Template> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Template::getDeleted, false);
        wrapper.eq(Template::getStatus, 1);
        if (StringUtils.hasText(category)) {
            wrapper.eq(Template::getCategory, category);
        }
        wrapper.orderByDesc(Template::getUsageCount);
        return templateMapper.selectList(wrapper);
    }

    @Override
    public List<Template> findByGame(String game) {
        LambdaQueryWrapper<Template> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Template::getDeleted, false);
        wrapper.eq(Template::getStatus, 1);
        if (StringUtils.hasText(game)) {
            wrapper.eq(Template::getGame, game);
        }
        wrapper.orderByDesc(Template::getUsageCount);
        return templateMapper.selectList(wrapper);
    }

    @Override
    public IPage<Template> findPage(TemplatePageRequest request) {
        LambdaQueryWrapper<Template> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Template::getDeleted, false);
        if (StringUtils.hasText(request.getCategory())) {
            wrapper.eq(Template::getCategory, request.getCategory());
        }
        if (StringUtils.hasText(request.getGame())) {
            wrapper.eq(Template::getGame, request.getGame());
        }
        wrapper.orderByDesc(Template::getCreatedTime);
        Page<Template> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return templateMapper.selectPage(page, wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Template update(Template template) {
        if (template.getId() == null) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "模板ID不能为空");
        }
        Template existing = templateMapper.selectById(template.getId());
        if (existing == null) {
            throw new BusinessException(ResultCode.Template.NOT_FOUND, "模板不存在");
        }
        templateMapper.updateById(template);
        log.info("更新模板 - ID: {}", template.getId());
        return template;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        Template template = templateMapper.selectById(id);
        if (template == null) {
            throw new BusinessException(ResultCode.Template.NOT_FOUND, "模板不存在");
        }
        template.setDeleted(true);
        templateMapper.updateById(template);
        log.info("删除模板 - ID: {}", id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void incrementUsageCount(String id) {
        Template template = templateMapper.selectById(id);
        if (template != null) {
            template.setUsageCount(template.getUsageCount() == null ? 1 : template.getUsageCount() + 1);
            templateMapper.updateById(template);
        }
    }
}
