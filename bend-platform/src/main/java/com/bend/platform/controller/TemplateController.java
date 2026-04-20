package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.PageRequest;
import com.bend.platform.dto.TemplatePageRequest;
import com.bend.platform.entity.Template;
import com.bend.platform.service.TemplateService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

/**
 * 模板控制器
 *
 * 功能说明：
 * - 管理图像识别模板
 * - 支持模板的上传、查询、更新、删除
 *
 * 模板类型：
 * - ui_button: UI按钮
 * - ui_icon: UI图标
 * - ui_text: UI文本
 * - game_element: 游戏元素
 * - scene_background: 场景背景
 *
 * 主要功能：
 * - 上传模板图片
 * - 查询模板列表（分页）
 * - 获取模板详情
 * - 更新/删除模板
 * - 获取支持的类型和游戏列表
 */
@Slf4j
@RestController
@RequestMapping("/api/templates")
@RequiredArgsConstructor
public class TemplateController {

    private final TemplateService templateService;

    private static final String UPLOAD_DIR = "/data/templates/";

    /**
     * 上传模板图片
     * 仅平台管理员可操作
     *
     * @param file           模板图片文件
     * @param name           模板名称
     * @param description    模板描述（可选）
     * @param category       模板类型（可选）
     * @param game          游戏类型（可选）
     * @param matchThreshold 匹配阈值（默认0.8）
     * @return 创建的模板信息
     */
    @PostMapping("/upload")
    public ApiResponse<Template> uploadTemplate(
            @RequestParam("file") MultipartFile file,
            @RequestParam String name,
            @RequestParam(required = false) String description,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String game,
            @RequestParam(required = false, defaultValue = "0.8") Double matchThreshold) {

        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }

        if (file.isEmpty()) {
            return ApiResponse.error(400, "文件不能为空");
        }

        try {
            String originalFilename = file.getOriginalFilename();
            String extension = originalFilename != null && originalFilename.contains(".")
                ? originalFilename.substring(originalFilename.lastIndexOf("."))
                : ".png";

            String filename = UUID.randomUUID().toString() + extension;
            Path uploadPath = Paths.get(UPLOAD_DIR);
            if (!Files.exists(uploadPath)) {
                Files.createDirectories(uploadPath);
            }

            Path filePath = uploadPath.resolve(filename);
            Files.copy(file.getInputStream(), filePath);

            Template template = new Template();
            template.setName(name);
            template.setDescription(description);
            template.setCategory(category);
            template.setGame(game);
            template.setImageUrl(filePath.toString());
            template.setMatchThreshold(matchThreshold);
            template.setStatus(1);

            Template created = templateService.create(template);
            return ApiResponse.success("上传成功", created);

        } catch (IOException e) {
            log.error("上传模板文件失败", e);
            return ApiResponse.error(500, "文件保存失败: " + e.getMessage());
        }
    }

    /**
     * 分页查询模板列表
     *
     * @param request 分页请求参数
     * @return 模板分页列表
     */
    @GetMapping
    public ApiResponse<IPage<Template>> list(TemplatePageRequest request) {

        IPage<Template> page = templateService.findPage(request);
        return ApiResponse.success(page);
    }

    /**
     * 获取模板详情
     *
     * @param id 模板ID
     * @return 模板信息
     */
    @GetMapping("/{id}")
    public ApiResponse<Template> getById(@PathVariable String id) {
        Template template = templateService.findById(id);
        if (template == null) {
            return ApiResponse.error(404, "模板不存在");
        }
        return ApiResponse.success(template);
    }

    /**
     * 更新模板
     * 仅平台管理员可操作
     *
     * @param id      模板ID
     * @param template 更新后的模板信息
     * @return 更新后的模板信息
     */
    @PutMapping("/{id}")
    public ApiResponse<Template> update(@PathVariable String id, @RequestBody Template template) {

        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }

        template.setId(id);
        Template updated = templateService.update(template);
        return ApiResponse.success("更新成功", updated);
    }

    /**
     * 删除模板
     * 仅平台管理员可操作
     *
     * @param id 模板ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {

        if (!UserContext.isPlatformAdmin()) {
            return ApiResponse.error(403, "无权限");
        }

        templateService.delete(id);
        return ApiResponse.success("删除成功", null);
    }

    /**
     * 获取所有模板类型
     *
     * @return 模板类型列表
     */
    @GetMapping("/categories")
    public ApiResponse<List<String>> getCategories() {
        return ApiResponse.success(Arrays.asList(
            "ui_button", "ui_icon", "ui_text", "game_element", "scene_background"
        ));
    }

    /**
     * 获取所有游戏类型
     *
     * @return 游戏类型列表
     */
    @GetMapping("/games")
    public ApiResponse<List<String>> getGames() {
        return ApiResponse.success(Arrays.asList(
            "general", "xbox_home", "game_pass", "xcloud"
        ));
    }
}