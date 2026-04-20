package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.TaskPageRequest;
import com.bend.platform.entity.Task;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.TaskService;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 任务服务实现类
 *
 * 功能说明：
 * - 实现任务管理的核心业务逻辑
 * - 管理任务的完整生命周期（创建、分配、执行、完成、失败、取消）
 * - 与MyBatis-Plus集成进行数据库操作
 * - 通过WebSocket与Agent通信
 *
 * 主要功能：
 * - 任务的CRUD操作
 * - 任务状态流转管理
 * - 任务重试机制
 * - 任务分配给Agent
 *
 * 事务管理：
 * - 所有写操作使用@Transactional确保数据一致性
 * - 事务回滚条件：任何异常都会触发回滚
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TaskServiceImpl implements TaskService {

    private final TaskMapper taskMapper;

    /**
     * 创建任务
     *
     * 功能说明：
     * - 在数据库中创建新的任务记录
     * - 自动设置默认状态为pending
     * - 初始化重试次数为0
     * - 默认最大重试次数为3
     *
     * 参数说明：
     * - task: 任务实体对象
     *
     * 返回值：
     * - 创建后的任务对象（包含生成的主键ID）
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task create(Task task) {
        task.setStatus("pending");  // 初始状态为待执行
        task.setRetryCount(0);     // 重试次数归零
        if (task.getMaxRetries() == null) {
            task.setMaxRetries(3); // 默认最大重试3次
        }
        taskMapper.insert(task);
        log.info("创建任务 - ID: {}, 名称: {}, 类型: {}", task.getId(), task.getName(), task.getType());
        return task;
    }

    /**
     * 根据ID查询任务
     *
     * 参数说明：
     * - id: 任务ID
     *
     * 返回值：
     * - 任务对象，不存在返回null
     */
    @Override
    public Task findById(String id) {
        return taskMapper.selectById(id);
    }

    /**
     * 查询Agent的所有任务
     *
     * 功能说明：
     * - 查询分配给指定Agent的全部任务
     * - 按创建时间倒序排列
     * - 排除已删除的任务
     *
     * 参数说明：
     * - agentId: Agent唯一标识符
     *
     * 返回值：
     * - 任务列表
     */
    @Override
    public List<Task> findByAgentId(String agentId) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getTargetAgentId, agentId);  // 指定Agent
        wrapper.eq(Task::getDeleted, false);          // 未删除
        wrapper.orderByDesc(Task::getCreatedAt);      // 按创建时间倒序
        return taskMapper.selectList(wrapper);
    }

    /**
     * 查询Agent的待处理任务
     *
     * 功能说明：
     * - 查询指定Agent尚未执行的任务
     * - 先按优先级升序，再按创建时间升序
     *
     * 参数说明：
     * - agentId: Agent唯一标识符
     *
     * 返回值：
     * - 待处理任务列表
     */
    @Override
    public List<Task> findPendingByAgentId(String agentId) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getTargetAgentId, agentId);      // 指定Agent
        wrapper.eq(Task::getStatus, "pending");           // 待执行状态
        wrapper.eq(Task::getDeleted, false);              // 未删除
        wrapper.orderByAsc(Task::getPriority);            // 按优先级升序
        wrapper.orderByAsc(Task::getCreatedAt);           // 按创建时间升序
        return taskMapper.selectList(wrapper);
    }

    /**
     * 分页查询任务列表
     *
     * 功能说明：
     * - 支持按状态和类型筛选
     * - 分页返回任务列表
     *
     * 参数说明：
     * - pageNum: 页码（从1开始）
     * - pageSize: 每页数量
     * - status: 按状态筛选（可选）
     * - type: 按类型筛选（可选）
     *
     * 返回值：
     * - 分页结果（包含数据列表和分页信息）
     */
    @Override
    public IPage<Task> findPage(TaskPageRequest request) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getDeleted, false);
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(Task::getStatus, request.getStatus());
        }
        if (StringUtils.hasText(request.getType())) {
            wrapper.eq(Task::getType, request.getType());
        }
        wrapper.orderByDesc(Task::getCreatedAt);
        Page<Task> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return taskMapper.selectPage(page, wrapper);
    }

    /**
     * 分配任务给Agent
     *
     * 功能说明：
     * - 将任务分配给指定的Agent执行
     * - 更新任务的Agent关联和时间戳
     * - 通过WebSocket发送任务到Agent
     *
     * 参数说明：
     * - taskId: 任务ID
     * - agentId: 目标Agent ID
     *
     * 返回值：
     * - 更新后的任务对象
     *
     * 异常说明：
     * - 任务不存在时抛出BusinessException
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task assignToAgent(String taskId, String agentId) {
        Task task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }

        task.setTargetAgentId(agentId);           // 设置目标Agent
        task.setAssignedAt(LocalDateTime.now());  // 记录分配时间
        taskMapper.updateById(task);

        // 构建任务数据并发送到Agent
        Map<String, Object> taskData = new HashMap<>();
        taskData.put("taskId", task.getId());
        taskData.put("name", task.getName());
        taskData.put("type", task.getType());
        taskData.put("params", parseParams(task.getParams()));
        taskData.put("priority", task.getPriority());

        AgentWebSocketEndpoint.sendTaskToAgent(agentId, taskId, taskData);
        log.info("任务已分配给Agent - TaskID: {}, AgentID: {}", taskId, agentId);

        return task;
    }

    /**
     * 开始执行任务
     *
     * 功能说明：
     * - 将任务状态改为running
     * - 记录任务开始时间
     *
     * 参数说明：
     * - taskId: 任务ID
     *
     * 返回值：
     * - 更新后的任务对象
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task start(String taskId) {
        Task task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }

        task.setStatus("running");                      // 状态改为执行中
        task.setStartedAt(LocalDateTime.now());         // 记录开始时间
        taskMapper.updateById(task);

        log.info("任务开始执行 - TaskID: {}", taskId);
        return task;
    }

    /**
     * 标记任务完成
     *
     * 功能说明：
     * - 将任务状态改为completed
     * - 记录任务完成时间和结果
     *
     * 参数说明：
     * - taskId: 任务ID
     * - result: 任务执行结果
     *
     * 返回值：
     * - 更新后的任务对象
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task complete(String taskId, String result) {
        Task task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }

        task.setStatus("completed");                     // 状态改为已完成
        task.setResult(result);                         // 存储结果
        task.setCompletedAt(LocalDateTime.now());       // 记录完成时间
        taskMapper.updateById(task);

        log.info("任务完成 - TaskID: {}", taskId);
        return task;
    }

    /**
     * 标记任务失败
     *
     * 功能说明：
     * - 增加重试次数
     * - 记录错误信息
     * - 判断是否需要重试或标记为失败
     *
     * 参数说明：
     * - taskId: 任务ID
     * - errorMessage: 错误信息
     *
     * 返回值：
     * - 更新后的任务对象
     *
     * 重试逻辑：
     * - 如果重试次数小于最大重试次数，状态改为pending等待重试
     * - 如果达到最大重试次数，状态改为failed
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task fail(String taskId, String errorMessage) {
        Task task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }

        task.setRetryCount(task.getRetryCount() == null ? 1 : task.getRetryCount() + 1);
        task.setErrorMessage(errorMessage);

        if (task.getRetryCount() < task.getMaxRetries()) {
            task.setStatus("pending");  // 还未达到最大重试次数，设置为待执行
            log.warn("任务失败，准备重试 - TaskID: {}, 重试次数: {}/{}", taskId, task.getRetryCount(), task.getMaxRetries());
        } else {
            task.setStatus("failed");  // 达到最大重试次数，标记为失败
            log.error("任务失败 - TaskID: {}, 错误: {}", taskId, errorMessage);
        }

        taskMapper.updateById(task);
        return task;
    }

    /**
     * 取消任务
     *
     * 功能说明：
     * - 将任务状态改为cancelled
     * - 仅pending状态的任务可以取消
     *
     * 参数说明：
     * - taskId: 任务ID
     *
     * 返回值：
     * - 更新后的任务对象
     *
     * 异常说明：
     * - 任务不存在时抛出BusinessException
     * - 任务状态不是pending时抛出BusinessException
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task cancel(String taskId) {
        Task task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }

        if (!"pending".equals(task.getStatus())) {
            throw new BusinessException(ResultCode.Task.INVALID_STATUS, "只能取消待执行的任务");
        }

        task.setStatus("cancelled");
        taskMapper.updateById(task);

        log.info("任务已取消 - TaskID: {}", taskId);
        return task;
    }

    /**
     * 重试任务
     *
     * 功能说明：
     * - 将failed或pending状态的任务重置为pending
     * - 重置重试计数和错误信息
     *
     * 参数说明：
     * - taskId: 任务ID
     *
     * 返回值：
     * - 更新后的任务对象
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Task retry(String taskId) {
        Task task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }

        if (!"failed".equals(task.getStatus()) && !"pending".equals(task.getStatus())) {
            throw new BusinessException(ResultCode.Task.INVALID_STATUS, "任务状态不允许重试");
        }

        task.setStatus("pending");
        task.setErrorMessage(null);
        task.setRetryCount(0);
        taskMapper.updateById(task);

        log.info("任务已重置为待执行 - TaskID: {}", taskId);
        return task;
    }

    /**
     * 删除任务（软删除）
     *
     * 功能说明：
     * - 将任务的deleted标志设置为true
     * - 物理数据仍然保留在数据库中
     *
     * 参数说明：
     * - id: 任务ID
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String id) {
        Task task = taskMapper.selectById(id);
        if (task == null) {
            throw new BusinessException(ResultCode.Task.NOT_FOUND, "任务不存在");
        }
        task.setDeleted(true);  // 软删除标记
        taskMapper.updateById(task);
        log.info("删除任务 - ID: {}", id);
    }

    /**
     * 根据流媒体账号ID取消任务
     *
     * 功能说明：
     * - 取消指定流媒体账号下所有running状态的任务
     * - 用于停止自动化时调用
     *
     * 参数说明：
     * - streamingAccountId: 流媒体账号ID
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void cancelByStreamingAccountId(String streamingAccountId) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getStreamingAccountId, streamingAccountId)
               .eq(Task::getStatus, "running");
        List<Task> runningTasks = taskMapper.selectList(wrapper);

        for (Task task : runningTasks) {
            task.setStatus("cancelled");
            task.setErrorMessage("被管理员停止");
            task.setCompletedAt(LocalDateTime.now());
            taskMapper.updateById(task);
            log.info("取消流媒体账号任务 - TaskID: {}, StreamingAccountID: {}", task.getId(), streamingAccountId);
        }
    }

    /**
     * 根据流媒体账号ID查询任务
     *
     * 参数说明：
     * - streamingAccountId: 流媒体账号ID
     *
     * 返回值：
     * - 按创建时间倒序排列的任务列表
     */
    @Override
    public List<Task> findByStreamingAccountId(String streamingAccountId) {
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Task::getStreamingAccountId, streamingAccountId)
               .orderByDesc(Task::getCreatedAt);
        return taskMapper.selectList(wrapper);
    }

    /**
     * 解析任务参数字符串为Map
     *
     * 功能说明：
     * - 将JSON格式的参数字符串解析为Java Map
     * - 用于WebSocket发送任务时转换参数格式
     *
     * 参数说明：
     * - paramsJson: JSON格式的参数字符串
     *
     * 返回值：
     * - 解析后的Map对象，解析失败返回空Map
     */
    private Map<String, Object> parseParams(String paramsJson) {
        if (paramsJson == null || paramsJson.isEmpty()) {
            return new HashMap<>();
        }
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().readValue(paramsJson, Map.class);
        } catch (Exception e) {
            log.error("解析任务参数失败: {}", paramsJson);
            return new HashMap<>();
        }
    }
}
