package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.PermissionCreateRequest;
import com.bend.platform.entity.MerchantPermission;

/**
 * 商户使用权限(Permission)服务（总控侧）
 *
 * <p>与 License(软件授权)解耦: License 控制软件合法性, Permission 控制服务可用性。
 */
public interface PermissionService {

    /** 为商户创建/激活使用权限（安装激活时调用，或总控管理员手动创建） */
    MerchantPermission createOrRenew(PermissionCreateRequest request);

    /** 续期：指定精确到期时间（自定义日期兜底，expired → active） */
    void renew(String permissionId, java.time.LocalDateTime newExpireAt);

    /**
     * 续期：按套餐时长，从当前到期日(已过期则从当前时间)往后加。
     * @param durationCode 套餐码，见 {@link com.bend.platform.dto.PermissionDuration}
     */
    void renewByDuration(String permissionId, String durationCode);

    /** 停用（暂停商户使用，active → suspended） */
    void suspend(String permissionId);

    /** 启用（解除停用，suspended → active） */
    void resume(String permissionId);

    /** 查询商户的权限 */
    MerchantPermission findByMerchantId(String merchantId);

    /** 根据ID查询 */
    MerchantPermission findById(String id);

    /** 分页查询（总控后台用） */
    IPage<MerchantPermission> page(int pageNum, int pageSize, String merchantId, String status);
}
