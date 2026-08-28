# astrbot_plugin_arxiv

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 设计的 arXiv 论文检索插件。

按关键词、作者或分类检索 arXiv 论文，并支持订阅后每日定时推送最新论文。

**无需任何 API Key**：arXiv 官方 API 免费公开，安装即可使用。

## ✨ 功能

- `/paper <查询>` 检索论文，返回标题、作者、发表时间与链接
- 支持作者（`au:`）、分类（`cat:`）、关键词等 arXiv 查询语法
- `/paper sub <查询>` 订阅，每天定时推送最新论文到当前会话
- 订阅、退订、列表、清空管理
- 可配置检索数量与每日推送时间

## 📦 安装

在 AstrBot 插件市场搜索 `astrbot_plugin_arxiv` 安装，或：

1. 将本仓库克隆到 `AstrBot/data/plugins/` 目录下
2. 安装依赖：`pip install -r requirements.txt`（或让 AstrBot 自动安装）
3. 在 WebUI 中启用插件

## 🚀 使用

```
/paper attention is all you need 5   # 检索关键词，返回 5 条
/paper au:Yoshua Bengio              # 按作者检索
/paper latest transformer 5          # 按最新发表时间检索，返回 5 条
/paper cat:cs.CL 10                  # 按分类检索，返回 10 条
/paper sub cat:cs.AI                 # 订阅该分类，每天推送最新论文
/paper unsub cat:cs.AI               # 取消订阅
/paper list                          # 查看我的订阅
/paper clear                         # 清空我的订阅
/paper help                          # 帮助
```

### arXiv 查询技巧

| 用途 | 写法 |
|---|---|
| 作者 | `au:Yoshua Bengio` |
| 分类 | `cat:cs.AI`、`cat:cs.CL` |
| 关键词 | `transformer` 或 `all:transformer` |
| 组合 | `au:Bengio AND cat:cs.AI` |

## ⚙️ 配置

在 WebUI 插件配置中可设置：

- `max_results`：检索默认返回数量（默认 5）
- `push_enabled`：是否开启每日订阅推送（默认开启）
- `push_time`：每日推送时间，服务器时区（默认 08:00）

## 📄 许可

MIT License
