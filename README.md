# ☀️ Malaysia Solar News Collector

马来西亚太阳能产业**政策 / 市场 / 项目新闻自动收集器**：
每小时抓取 → 相关性过滤去重 → Dashboard 展示 → Telegram 推送，形成闭环。

```
┌─────────────────────────────────────────────────────────────┐
│  信息源层                                                    │
│  Google News RSS × 9 组关键词  +  pv magazine 等 4 个直连 RSS │
│  + 任意工具 POST /webhook（n8n / changedetection.io / 自建）  │
└──────────────────────────┬──────────────────────────────────┘
                           ▼ 每 60 分钟
┌─────────────────────────────────────────────────────────────┐
│  管道 pipeline.py                                           │
│  抓取 → 关键词相关性评分(GEO∧TOPIC) → URL/标题去重 → SQLite   │
│  → 新文章打包推送 Telegram → 导出 articles.json 快照          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  消费层                                                      │
│  ① Dashboard（本机 http://localhost:8000 或 GitHub Pages）    │
│  ② Telegram 卡片推送（🚨 高分政策类置顶标记）                  │
│  ③ data/articles.json 快照（可对接任何下游）                   │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始（本机）

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # 填入 Telegram token（可先留空）

# 跑一次抓取（首次约 360 条相关新闻入库）
.venv/bin/python -m app.pipeline

# 启动 Dashboard + 每小时自动抓取（一个进程搞定）
.venv/bin/uvicorn app.web:app --port 8000
# 打开 http://127.0.0.1:8000
```

页面上的 **▶ 立即抓取** 按钮可随时手动触发一轮。

## Telegram 推送配置（5 分钟）

1. 在 Telegram 找 **@BotFather** → `/newbot` → 得到 `TELEGRAM_BOT_TOKEN`
2. 给你的新 bot 随便发一条消息
3. 浏览器打开 `https://api.telegram.org/bot<TOKEN>/getUpdates`，抄下 `chat.id` → `TELEGRAM_CHAT_ID`
4. 写进 `.env`，重启服务。新新闻会以卡片形式（标题/来源/时间/链接/#标签）推送给你，
   每篇文章按权重分换算成 **★～★★★★★ 五级星级**（5分=★，6-7=★★，8-9=★★★，10-11=★★★★，≥12=★★★★★），
   **★★★ 以上（score ≥ 8）的政策类重磅新闻用 🚨 标记**，卡片显示 ★ 星级。

验证：`.venv/bin/python -m app.pipeline`（配置正确即会推送）。

## 让它在「电脑关机时也照跑」（云端，免费）

**方案 A：GitHub Actions（推荐，零服务器）**

项目内置 [.github/workflows/collect.yml](.github/workflows/collect.yml)，
托管到 GitHub 后每小时在云端跑一次，电脑关机不影响：

1. `git init && git add -A && git commit -m "solar news bot" && git push` 到你的仓库
2. 仓库 **Settings → Secrets and variables → Actions** 添加：
   `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`（可选 `WEBHOOK_TOKEN`）
3. **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**
   → 云端每次抓取后自动更新 `docs/index.html + articles.json`，你随时打开
   `https://<你>.github.io/<仓库名>/` 看 Dashboard
4. 每次抓取的状态通过 `data/articles.json` 快照在云端间传递（去重不丢）

**方案 B：Docker + 任意 VPS**

```bash
cp .env.example .env   # 填好 token
docker compose up -d --build
# Dashboard + 每小时调度跑在 8000 端口，restart: unless-stopped 崩了自动拉起
```

**方案 C：本机 cron / launchd**（保持开机即可）

```
17 * * * * cd /path/to/project && .venv/bin/python -m app.pipeline >> data/cron.log 2>&1
```

## 公网部署与安全（给外界一个 URL）

**不需要 VPS，有 0 成本方案。** 三种方案对比：

| 方案 | 成本 | 关机可跑 | 公网 URL | 实时看板 | 接收 webhook | 数据持久 |
|---|---|---|---|---|---|---|
| **A. GitHub Actions + Pages**（已内置） | **￥0，无限用** | ✅ | ✅ `user.github.io/repo/` | ❌ 每小时快照 | ❌（静态托管无后端） | ✅ 仓库存快照 |
| **B. 免费 PaaS**（Render/Koyeb，用自带 Dockerfile） | ￥0（有限制） | ✅ | ✅ `xxx.onrender.com` | ✅ 完整功能 | ✅ | ⚠️ 免费档磁盘易失 |
| **C. 免费 VPS**（甲骨文云 Always Free） | ￥0（需绑卡） | ✅ | ✅ | ✅ | ✅ | ✅ |
| （参考）普通 VPS（DigitalOcean 等） | ~$5/月 | ✅ | ✅ | ✅ | ✅ | ✅ |

**推荐路径：先 A（10 分钟上线，零成本零运维），需要实时 webhook 再补 B。**

### 方案 A 步骤

```bash
# 1. 在 github.com 新建仓库（选 Public，名字如 malaysia-solar-news），然后：
git remote add origin https://github.com/<你的用户名>/malaysia-solar-news.git
git push -u origin main

# 2. 仓库 Settings → Secrets and variables → Actions 添加：
#    TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / WEBHOOK_TOKEN（可选）
# 3. Settings → Pages → Source: Deploy from a branch → main / docs
# 4. Actions 页签 → hourly-collect → Run workflow 手动跑第一次
#    （之后每小时第 17 分钟自动跑，关机不影响；若 push 回写失败，
#     到 Settings → Actions → Workflow permissions 勾 Read and write）
```

得到 `https://<用户名>.github.io/malaysia-solar-news/` 公网看板；
首次云端抓取会导入本地361 条快照，**只推送真正的新文章**，不会刷屏。

### 公网安全（已内置并实测）

| 防线 | 配置 | 实测 |
|---|---|---|
| 看板/API 访问鉴权 | `.env` 设 `WEB_ACCESS_TOKEN`，浏览器访问 `/?key=密钥` 一次（种 cookie） | 无密钥 401 / 对密钥 200 / 错密钥 401 |
| Webhook 鉴权 | `WEBHOOK_TOKEN` → 必须带 `X-Webhook-Token` header | 无 token 401 / 对 token 200 |
| Webhook 限流 | 每 IP 每小时 60 次，超出 429 | 65 连发 → 超限全部 429 |
| Secrets 不进代码 | `.env` 已 gitignore；云端用 GitHub Secrets/平台环境变量 | ✅ |
| HTTPS | Pages / PaaS 自动；VPS 用 Caddy 或 Cloudflare | ✅ |

进阶：在前面套一层 **Cloudflare**（免费 CDN + WAF，Zero Trust Access 免费 50 用户可给看板加 Google 登录）。

> 注意：方案 A 的静态看板无法用 `WEB_ACCESS_TOKEN`（无后端），公开仓库下新闻列表对所有人可见（内容本身不敏感）；需要真正的访问控制就用方案 B/C。

## Webhook 接入（把任何信息源喂进来）

系统内置 `POST /webhook`，可接收单个对象或数组：

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_TOKEN" \
  -d '{"title":"SEDA opens LSS6 bidding","url":"https://...","source":"seda","summary":"..."}'
```

- 设置了 `WEBHOOK_TOKEN` 后必须带同名 header，否则 401
- 字段兼容 `name/link/content` 别名（changedetection.io 等工具的格式）
- 可选字段 `topic`（`solar` / `ai`）指定文章归属主题，不传默认归 `solar`
- 入库即自动去重 + 推送 Telegram + 更新 Dashboard
- 典型用法：用 changedetection.io 监控 SEDA/TNB 官网页面变动 → 它的 webhook 打到这里

## 调优抓取内容

一切规则在 [app/config.py](app/config.py) 的 `TOPICS` 字典里，**每个主题各自一份**：

- `queries` — Google News 搜索式（支持 `OR`、引号短语）
- `rss` — 直连 RSS 源，随便加
- `geo_terms` / `topic_terms` — **必须同时命中 ≥1 个地理词 + ≥1 个主题词** 才会收录
  （主题级 `require_geo: false` 可改为只看主题词）
- `bonus_terms` — 加分词（quota、tariff、policy…），影响星级与 🚨 标记

> **五星级换算**：星级 = `clamp(四舍五入((score-3)/2), 1, 5)`，权重算法不变，仅展示层换算；
> 鼠标悬停看板上的 ★ 徽章可看到原始 score。
- `ignore_terms` — 一票否决（solar eclipse 等噪音）
- `COLLECT_INTERVAL_MIN` — 抓取频率（默认 60 分钟）

现有两个主题：`solar`（马来西亚太阳能 ☀️）与 `ai`（马来西亚 AI 🤖），看板顶部按钮切换。
新增主题只需在 `TOPICS` 加一段配置 + 前端 `TOPICS` 加同名条目，无需改逻辑。
抓取：`python -m app.pipeline`（全部主题）或 `python -m app.pipeline --topic ai`（单主题）。

---

## 你还能做什么？——闭环增强建议

已实现：**收集 → 过滤 → 存储 → 推送 → 看板**。以下按价值排序的下一步：

1. **AI 摘要 + 影响力分级**：每天用 LLM 把新增新闻压成一份中文日报（Telegram 一条消息），
   并标注"对我方业务的影响"（政策变更 / 招标 / 竞争对手动向）。
2. **每周 digest 而非每条推送**：政策新闻频率低，每条推送容易"狼来了"。
   建议分两级——🚨 重磅即时推，普通新闻攒进每晚 8 点日报。
3. **监控源从"新闻"扩到"官网原文"**：SEDA（LSS 招标）、TNB（tariff 公告）、
   Energy Commission（第三 party access 政策）常先于新闻发布 PDF。用 changedetection.io
   监控这些页面 → webhook 打进本系统，你比媒体早知道。
4. **实体追踪**：把竞争对手/客户名（Gentari、Samaiden、Ranhill、Cypark、TNB…）加进
   配置做单独分组，专属标签页 + 单独推送。
5. **结构化入库**：现在存的是新闻，下一步抽取"配额数字、日期、电价"等字段，
   配额/电价一变自动生成对比表——这就是产业情报而非新闻剪报了。
6. **搜索与回溯**：SQLite 全文检索（FTS5）+ dashboard 全文搜索，政策溯源一键完成。
7. **多渠道**：WhatsApp（Meta Cloud API）预留了 notify 层接口，加一个 `notify_whatsapp()`
   即可双通道；邮件 digest 也只需一个 SMTP 函数。
8. **数据外送**：`data/articles.json` 是稳定接口，可直接喂给 Notion 数据库、
   Google Sheets、飞书多维表格做周报素材。

## 可参考的开源项目（同类轮子）

| 项目 | 定位 | 对你的启发 |
|---|---|---|
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 网页变更监控，支持 Webhook/Telegram 通知 | **最接近你的需求**；监控 SEDA/TNB 官网原文，webhook 打进本系统 |
| [Huginn](https://github.com/huginn/huginn) | 自动化"agent"系统，构建事件流水线并 webhook 推送 | 复杂事件规则引擎，适合"命中某关键词→多路分发" |
| [n8n](https://github.com/n8n-io/n8n) | 可视化自动化（类 Zapier），自带 webhook 节点 | 不写代码串起 RSS→AI→Telegram/WhatsApp |
| [RSS-to-Telegram-Bot](https://github.com/Rongronggg9/RSS-to-Telegram-Bot) | RSS 推 Telegram 专用 bot | 推送格式/分批的实现可直接借鉴 |
| [RSSHub](https://github.com/DIYgod/RSSHub) | 把无 RSS 的站点变成 RSS | 给没有 feed 的马来西亚站点（如 The Edge）造 feed |
| [Miniflux](https://github.com/miniflux/miniflux) / FreshRSS | 自托管 RSS 阅读器 | 若新闻量大，可先过一遍阅读器再入库 |

本项目选择**自建**而非直接部署上述工具，是因为需要"评分 + 中文推送 + 定制看板 + webhook 汇聚"
四件事组合，拼装成本高于 500 行定制代码；但第 3 条建议（官网监控）强烈推荐直接用
changedetection.io 与本系统组合。

## 文件结构

```
app/
  config.py      # 信源、关键词、环境变量（唯一需要经常改的文件）
  collectors.py  # Google News RSS + 直连 RSS 抓取与相关性评分
  db.py          # SQLite 存储 / 去重 / 快照导入导出
  pipeline.py    # 一轮完整抓取：python -m app.pipeline
  notify.py      # Telegram 卡片推送（分批、429 重试）
  scheduler.py   # 独立整点调度：python -m app.scheduler
  web.py         # FastAPI：Dashboard + API + /webhook + 内嵌每小时调度
static/index.html  # 单文件看板（API / GitHub Pages 双模式自适应）
.github/workflows/collect.yml  # 云端每小时抓取 + 自动发布 Pages 看板
Dockerfile / docker-compose.yml
data/news.db         # SQLite（gitignore）
data/articles.json   # 快照（云端去重 + Pages 数据源）
```
