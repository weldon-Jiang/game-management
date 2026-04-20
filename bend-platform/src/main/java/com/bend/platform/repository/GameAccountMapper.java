package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.GameAccount;
import org.apache.ibatis.annotations.Mapper;

/**
 * 游戏账号Mapper接口
 */
@Mapper
public interface GameAccountMapper extends BaseMapper<GameAccount> {
}