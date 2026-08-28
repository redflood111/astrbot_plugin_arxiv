# astrbot_plugin_arxiv

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 设计的 arXiv 论文检索插件。

按关键词、作者或分类检索 arXiv 论文，支持多种排序方式，并可用 LLM 翻译标题、订阅后每日定时推送最新论文。

**无需任何 API Key**：arXiv 官方 API 免费公开，安装即可使用。

## ✨ 功能

- 四种检索方式：相关性 / 最新 / 相关+新 / 标题翻译
- 支持作者（`au:`）、分类（`cat:`）、关键词等 arXiv 查询语法
- `/paper zh` 用 AstrBot 已配置的 LLM 翻译论文标题
- `/paper abs` 翻译上次检索结果中指定编号论文的摘要
- `/paper cats` 查看常用 arXiv 分类代码
- `/paper sub` 订阅，每天定时推送最新论文到当前会话
- 订阅、退订、列表、清空管理
- 可配置检索数量与每日推送时间

## 📦 安装

在 AstrBot 插件市场搜索 `astrbot_plugin_arxiv` 安装，或：

1. 将本仓库克隆到 `AstrBot/data/plugins/` 目录下
2. 安装依赖：`pip install -r requirements.txt`（或让 AstrBot 自动安装）
3. 在 WebUI 中启用插件

## 🚀 使用

```
/paper attention is all you need 5   # 按相关性检索，返回 5 条
/paper au:Yoshua Bengio              # 按作者检索
/paper latest transformer 5          # 按最新发表时间检索
/paper recent transformer 5          # 相关 + 较新检索
/paper zh transformer 5              # 检索并用 LLM 翻译标题
/paper cat:cs.CL 10                  # 按分类检索，返回 10 条
/paper sub cat:cs.AI                 # 订阅该分类，每天推送最新论文
/paper unsub cat:cs.AI               # 取消订阅
/paper list                          # 查看我的订阅
/paper abs 2                         # 翻译上次检索中第 2 篇的摘要
/paper cats                         # 查看常用分类代码
/paper clear                         # 清空我的订阅
/paper help                          # 帮助
```

### 四种检索方式对比

| 指令 | 排序逻辑 | 适用场景 |
|---|---|---|
| `/paper <查询>` | 相关性 | 查经典、最匹配的论文 |
| `/paper latest <查询>` | 最新提交 | 追最新（可能混入少量无关论文） |
| `/paper recent <查询>` | 相关 + 新 | 又新又准（推荐） |
| `/paper zh <查询>` | 相关性 + 翻译标题 | 想要中文标题 |

> `/paper zh` 依赖 AstrBot 已配置的对话模型（LLM）。若未配置或翻译失败，会自动降级为英文结果并给出提示。

### arXiv 查询技巧

| 用途 | 写法 |
|---|---|
| 作者 | `au:Yoshua Bengio` |
| 分类 | `cat:cs.AI`、`cat:cs.CL` |
| 关键词 | `transformer` 或 `all:transformer` |
| 组合 | `au:Bengio AND cat:cs.AI` |

> 完整分类代码列表：https://arxiv.org/category_taxonomy

## ⚙️ 配置

在 WebUI 插件配置中可设置：

- `max_results`：检索默认返回数量（默认 5）
- `push_enabled`：是否开启每日订阅推送（默认开启）
- `push_time`：每日推送时间，服务器时区（默认 08:00）

## 📝 更新日志

### v1.2.0

- 新增 `/paper abs <编号>`：翻译上次检索结果中指定编号论文的摘要
- 检索结果会按会话记住，供摘要翻译引用

### v1.1.0

- 新增 `/paper zh`：检索并用 LLM 翻译论文标题
- 新增 `/paper cats`：查看常用 arXiv 分类代码
- 未配置 LLM 或翻译失败时自动降级为英文结果

### v1.0.0

- 初始版本：相关性 / 最新 / 相关+新 三种检索方式
- 订阅每日定时推送最新论文

## 📄 许可

MIT License
