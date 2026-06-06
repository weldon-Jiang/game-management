# 用户账号模板说明

## 概述

用户账号模板是针对每个游戏账号个性化定制的场景识别模板。由于不同玩家的游戏界面可能存在细微差异（如账号名称、进度显示位置等），需要为每个游戏账号单独保存其专属的模板。

## 目录结构

```
templates/
└── user_account_template/           # 用户账号模板目录
    ├── email_1_AT_example_DOT_com/  # 玩家A的模板
    │   ├── 50.1.json               # 场景50的模板1
    │   ├── 50.1.png                # 模板图片
    │   └── 56.1.json               # 场景56的模板1
    ├── email_2_AT_example_DOT_com/  # 玩家B的模板
    │   └── ...
    └── email_3_AT_example_DOT_com/  # 玩家C的模板
        └── ...
```

## 文件夹命名规则

由于Windows系统文件夹名不支持 `@` 和 `.` 字符，邮箱地址需要转义：

| 原始邮箱 | 转义后的文件夹名 |
|---------|----------------|
| `player1@example.com` | `player1_AT_example_DOT_com` |
| `player2@test.cn` | `player2_AT_test_DOT_cn` |
| `user.name@domain.com` | `user_DOT_name_AT_domain_DOT_com` |

### 转义规则

```
@  →  _AT_
.  →  _DOT_
```

这样既保证了文件夹名合法，又让人能一眼看出是哪个邮箱。

## JSON配置文件

每个模板对应一个JSON配置文件，例如 `50.1.json`：

```json
{
  "scene_id": 50,
  "template_id": 1,
  "email": "player1@example.com",
  "template_left": 0,
  "template_top": 0,
  "template_right": 100,
  "template_bottom": 50,
  "search_left": 0,
  "search_top": 0,
  "search_right": 960,
  "search_bottom": 540,
  "likeness": 90,
  "algorithm": 3,
  "version": 1
}
```

### 配置说明

| 字段 | 说明 |
|------|------|
| `scene_id` | 场景编号，用于标识是哪个游戏界面 |
| `template_id` | 模板编号，同一场景可能有多个模板 |
| `email` | 对应的游戏账号邮箱（原始邮箱，方便人工查看） |
| `template_left/top/right/bottom` | 模板图片在原图中的裁剪区域 |
| `search_left/top/right/bottom` | 在游戏画面中搜索这个模板的区域范围 |
| `likeness` | 相似度阈值，范围0-100，数值越高要求越精确 |
| `algorithm` | 匹配算法，3为推荐的标准算法 |
| `version` | 模板版本号 |

## 模板同步机制

当平台下发自动化任务时，会同时将该游戏账号的所有模板一并下发。Agent收到后：

1. 保存模板图片到对应目录
2. 生成JSON配置文件
3. 加载配置供场景识别使用

```
平台                          Agent
 │                             │
 │   下发任务 + 模板数据        │
 │ ──────────────────────────► │
 │                             │
 │                    保存到 user_account_template/
 │                    目录下对应账号文件夹
 │                             │
 │                    加载配置供自动化使用
```

## 常见问题

### Q: 为什么需要为每个账号单独保存模板？

A: 不同玩家的游戏界面可能存在细微差异，例如：
- 账号名称显示不同
- 进度条位置可能有偏移
- 部分玩家界面可能有自定义设置

为每个账号保存专属模板，可以提高场景识别的准确率。

### Q: 模板图片是什么格式？

A: PNG格式，分辨率与游戏画面一致（960×540）。

### Q: 如何手动查看某个账号的模板？

A: 找到 `templates/user_account_template/` 目录下对应的邮箱文件夹（注意是转义后的名字），里面就是该账号的所有模板。

### Q: 转义后的文件夹名太长怎么办？

A: 可以通过JSON文件中的 `email` 字段确认原始邮箱，每个JSON文件的第一行都记录了对应的原始邮箱地址。

---

*更新时间: 2026-06-04*
