package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.AgentVersion;
import com.bend.platform.service.AgentVersionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * Agent版本检查控制器（Agent端调用）
 *
 * 功能说明：
 * - 提供Agent版本检查和更新下载接口
 * - Agent启动时或定期检查是否有新版本
 *
 * 主要功能：
 * - 检查版本更新：对比当前版本与最新版本
 * - 获取最新版本信息
 * - 获取指定版本的下载信息
 *
 * 认证方式：
 * - 使用X-Agent-ID和X-Agent-Secret请求头进行身份验证
 */
@Slf4j
@RestController
@RequestMapping("/api/agents/version")
@RequiredArgsConstructor
public class AgentVersionCheckController {

    private final AgentVersionService agentVersionService;

    /**
     * 检查版本更新
     * Agent调用此接口检查是否有新版本可用
     *
     * @param agentId        AgentID
     * @param agentSecret    Agent密钥
     * @param currentVersion 当前版本号
     * @return 检查结果（包含是否有更新、最新版本信息等）
     */
    @GetMapping("/check")
    public ApiResponse<Map<String, Object>> checkUpdate(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @RequestParam String currentVersion) {

        log.info("Agent版本检查请求 - AgentID: {}, 当前版本: {}", agentId, currentVersion);

        Map<String, Object> result = new HashMap<>();
        result.put("currentVersion", currentVersion);

        AgentVersion update = agentVersionService.findUpdate(currentVersion);
        if (update != null) {
            result.put("hasUpdate", true);
            result.put("latestVersion", update.getVersion());
            result.put("downloadUrl", update.getDownloadUrl());
            result.put("md5Checksum", update.getMd5Checksum());
            result.put("changelog", update.getChangelog());
            result.put("mandatory", update.getMandatory() != null && update.getMandatory() == 1);
            result.put("forceRestart", update.getForceRestart() != null && update.getForceRestart() == 1);

            log.info("发现新版本 - AgentID: {}, 新版本: {}, 是否强制: {}",
                    agentId, update.getVersion(), update.getMandatory() == 1);
        } else {
            result.put("hasUpdate", false);
            result.put("latestVersion", currentVersion);
            log.info("当前已是最新版本 - AgentID: {}", agentId);
        }

        return ApiResponse.success(result);
    }

    /**
     * 获取最新版本信息
     *
     * @return 最新版本信息
     */
    @GetMapping("/latest")
    public ApiResponse<AgentVersion> getLatestVersion() {
        AgentVersion latest = agentVersionService.findLatest();
        return ApiResponse.success(latest);
    }

    /**
     * 获取指定版本的下载信息
     *
     * @param agentId     AgentID
     * @param agentSecret Agent密钥
     * @param version     版本号
     * @return 下载信息（包含下载地址和MD5校验码）
     */
    @GetMapping("/download/{version}")
    public ApiResponse<Map<String, String>> getDownloadInfo(
            @RequestHeader("X-Agent-ID") String agentId,
            @RequestHeader("X-Agent-Secret") String agentSecret,
            @PathVariable String version) {

        AgentVersion versionInfo = agentVersionService.findByVersion(version);
        if (versionInfo == null) {
            return ApiResponse.error(404, "版本不存在");
        }

        Map<String, String> downloadInfo = new HashMap<>();
        downloadInfo.put("version", versionInfo.getVersion());
        downloadInfo.put("downloadUrl", versionInfo.getDownloadUrl());
        downloadInfo.put("md5Checksum", versionInfo.getMd5Checksum());

        return ApiResponse.success(downloadInfo);
    }
}