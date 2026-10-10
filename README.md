# Research Toolkit 🔬

> 面向学术研究者的高效文献检索、Zotero 个人文库联动与 Google NotebookLM 证据提炼工具链。

`research-toolkit` 专为现代化科研工作流设计，无缝串联 **学术文献多源检索**、**顶刊顶会智能排序**、**Zotero 个人文库本地管理（绕过云配额）** 以及 **Google NotebookLM 逐字溯源问答**。

---

## 🌟 核心特性

- **多源检索与三级级联去重**：
  - 并发检索 **Semantic Scholar**（内置 1 RPS 平滑限流保护）与 **OpenAlex**（自动通过词位倒排索引重建摘要）。
  - 三级级联去重：规范化 DOI $\to$ ArXiv ID $\to$ 模糊标题相似度（Levenshtein $\ge 0.90$ 且年份容差 $\le 1$），智能深度合并元数据。
- **分层综合排序与权威综述置顶**：
  - 综合加权排序：$Score = 0.40 S_{rel} + 0.35 S_{cite} + 0.25 S_{venue} + B_{review}$。
  - 强制分层选择：前 25%~30% 席位优先预留给最新领域权威综述（Review/Survey），辅助快速建立研究全景。
- **内置顶刊顶会离线映射字典（VenueRegistry）**：
  - 收录 *Nature*, *Science*, *Cell*, *IEEE TPAMI*, *JMLR* 等期刊 JCR 影响因子。
  - 将 *CVPR*, *ICCV*, *ECCV*, *NeurIPS*, *ICML*, *ICLR*, *ACL*, *KDD* 等顶级会议赋予顶刊等效加权，避免顶会成果被降级为无影响因子预印本。
- **Zotero 个人文库严格隔离与本地零配额探测**：
  - 严格限制个人文库（`ZOTERO_LIBRARY_TYPE=user`），杜绝污染公共/协作群组（如 `cyber9`）。
  - 持久化规范化标准 DOI（`https://doi.org/{doi}`）。
  - 直接探测本地磁盘目录（`~/Zotero/storage/<key>/*.pdf`），彻底规避 Zotero 云端 300MB 免费配额限制。
  - 自动消解 Zotero Connector 抓取造成的重复条目，智能合并标签并采用带 PDF 的条目。
- **NotebookLM 网关**：
  - 支持持久化安卓主令牌（`master_token.json`）与单行环境变量（`NOTEBOOKLM_AUTH_JSON`），便于跨 VPS 极简迁移。
- **MCP (Model Context Protocol) 原生就绪**：
  - 提供标准 JSON-Schema 清单，可无缝接入 Claude Desktop、Cursor 等支持 MCP 的智能代理。

---

## 🛠️ 安装与配置

### 1. 环境要求
- Python $\ge$ 3.10
- 可选：安装 `rich` 和 `click`（已支持纯标准库环境兜底）

### 2. 配置环境变量
在项目根目录创建 `.env` 文件（或直接复制 `.env.example`）：

```bash
cp .env.example .env
```

在 `.env` 中填入你的配置信息：
```ini
# --- 学术检索 API（建议配置，可享更高频次） ---
SEMANTIC_SCHOLAR_API_KEY=your_s2_api_key
OPENALEX_API_KEY=your_openalex_api_key

# --- Zotero 个人文库 ---
ZOTERO_API_KEY=your_zotero_web_api_key
ZOTERO_USER_ID=your_numeric_user_id
ZOTERO_LIBRARY_TYPE=user
# 本地 PDF 存储路径（通常为 ~/Zotero/storage）
ZOTERO_STORAGE_DIR=/home/ling/Zotero/storage

# --- Google NotebookLM 网关 ---
# Android master token，存放在 ~/.notebooklm/profiles/default/master_token.json
# （由 scripts/setup_notebooklm.sh 写入）。不要设置 NOTEBOOKLM_AUTH_JSON：它只接受浏览器 cookie 登录状态。
NOTEBOOKLM_BACKEND=android
```

> 💡 **快速配置向导**：
> 针对无图形界面的远程 Linux 服务器，直接运行交互式向导即可安全设置 NotebookLM 凭证：
> ```bash
> ./scripts/setup_notebooklm.sh
> ```

### 3. 系统健康自检 (`doctor`)
随时可以通过诊断命令检查所有依赖与密钥连通性：
```bash
PYTHONPATH=src python3 -m research_toolkit.cli doctor
```
当看到各项指标均为 `[PASS]` 时，即代表完全就绪！

---

## 📖 核心命令与工作流指南

完整的科研流程分为三个阶段：**文献检索 $\to$ 检查点确认 $\to$ 来源上传**。

```
[1. search] ──────► [2. checkpoint] ──────► [3. sync-notebook]
 文献检索与排序        本地 PDF 查缺补漏         创建 NotebookLM 并同步
```

### 阶段 1：文献检索与智能排序 (`search`)

```bash
# 试运行（仅检索、去重、排序并打印表格，不写入 Zotero）
PYTHONPATH=src python3 -m research_toolkit.cli search "Graph Neural Networks" --limit 8 --dry-run

# 正式运行并直接同步到 Zotero 个人文库分类
PYTHONPATH=src python3 -m research_toolkit.cli search "Graph Neural Networks" --limit 8 --sync-zotero
```
- 表格第一列标识文献类型：`[REV]` 代表权威综述，`[RES]` 代表原创研究。
- 自动关联 open-access 公开 PDF 链接；收费文献将打上 `checkpoint/awaiting-fulltext` 标签。

---

### 阶段 2：全文检查点验证 (`checkpoint`)

在进行大模型深度阅读前，检查本地磁盘中是否已完整具备对应文献的 PDF 文件：

```bash
PYTHONPATH=src python3 -m research_toolkit.cli checkpoint --status
```
- **输出报告**：
  - 显示当前分类中本地已有 PDF 的论文列表。
  - 列出缺失 PDF 的论文标题与**标准 Canonical DOI 链接**（点击即可直达论文出版商页面）。
- **人工闭环**：
  - 在浏览器打开 DOI 链接，通过校园网/机构权限（如 SSO）访问，点击浏览器扩展 **Zotero Connector** 将 PDF 存入 Zotero。
  - 再次运行 `checkpoint`，系统会自动聚合重复条目并采纳本地 PDF。

---

### 阶段 3：创建研读笔记本并同步来源 (`sync-notebook`)

把一个 Zotero collection 中有 PDF 的条目增量同步到 Gemini Notebook（NotebookLM）：

```bash
# 默认使用与 collection 同名的笔记本，不存在就新建
uv run research-toolkit sync-notebook --collection intelligence-per-kwh

# 指定已有笔记本（完整标题或 UUID；同名有多个时报错，请改用 UUID）
uv run research-toolkit sync-notebook --collection intelligence-per-kwh --notebook <UUID>

# 先预演：只输出计划，不做任何写入（也不新建笔记本）
uv run research-toolkit sync-notebook --collection intelligence-per-kwh --dry-run

# 多个 collection 合并到一个笔记本（必须给 --notebook）；--recursive 包含子 collection
uv run research-toolkit sync-notebook -c 度电智能 -c 数据中心 --recursive --notebook 度电智能

# 重传某一篇（先删旧来源再上传），可重复
uv run research-toolkit sync-notebook --collection intelligence-per-kwh --replace ABCD1234
```
- 每个来源标题为 `[Zotero条目key] 论文标题`；已存在 `[key]` 的条目跳过，重跑即可续传。
- 上传前先算计划：新增、已存在、缺全文、`orphaned`（笔记本里有、输入里没有；只报告，从不删除）。
- 已有来源数 + 新增数超过 300 时一篇都不传；目标笔记本中大部分来源没有 `[key]` 标题（手动维护）时拒绝写入，除非加 `--force`。两种情况都在报告的 `aborted_reason` 中说明。
- stdout 只输出 JSON 报告（`notebook_id`、`notebook_title`、`created`、`dry_run`、`aborted_reason`、`added`、`replaced`、`skipped_existing`、`missing_fulltext`、`orphaned`、`failed`、`extra_attachments`、`source_count`、`projected_source_count`），进度走 stderr。

---

### 辅助命令：密钥生成、网关启动与 MCP Schema 导出

```bash
# 一键生成安全 API 密钥并直接写入 .env
PYTHONPATH=src python3 -m research_toolkit.cli generate-key --write-env

# 启动双协议栈网关守护进程（默认端口 8820，MCP Streamable HTTP / SSE + OpenAPI REST）
PYTHONPATH=src python3 -m research_toolkit.cli serve --port 8820

# 导出 MCP 工具 Schema JSON
PYTHONPATH=src python3 -m research_toolkit.cli mcp-schema
```

---

## 🐳 Docker / 远程 VPS 一键部署 (ADR-0003 & ADR-0006)

> ⚠️ 远程网关已按 [ADR-0007](docs/adr/0007-local-first-agent-execution.md) 冻结、不再部署。日常请在本地 agent（Claude Code / Antigravity CLI）里直接使用 CLI；以下内容仅作存档。

本项目提供 **Toolkit 双协议栈服务 + Caddy 自动化 TLS 反向代理** 的标准编排，专为无头 Linux VPS（如 `do-vps`）打造：

```bash
# 1. 配置 VPS 上的 .env
cp .env.example .env
# 填入 DUCKDNS_DOMAIN=your_subdomain.duckdns.org
# 填入 RESEARCH_TOOLKIT_API_KEY=your_secret_key
# 填入 ZOTERO_API_KEY, ZOTERO_USER_ID, NOTEBOOKLM_AUTH_JSON 等

# 2. 一键构建并后台启动（自动申请 Let's Encrypt 证书并启动 Toolkit）
docker compose up -d --build

# 3. 验证服务状态
curl https://your_subdomain.duckdns.org/health
```

### 接入大模型客户端

#### 1. ChatGPT 在线端 (Custom GPT Actions)
1. 在 ChatGPT 进入 GPT Builder -> **Configure** -> 点击 **Create new action**。
2. **Authentication**：
   - 方式选择 **API Key**，类型选择 **Bearer**。
   - 在 API Key 输入框填入你的 `RESEARCH_TOOLKIT_API_KEY`。
3. **Schema 导入**：
   - 点击 **Import from URL**，输入：`https://<your_subdomain>.duckdns.org/openapi.json`。
   - 自动解析出 `search`, `checkpoint` 两大能力！

#### 2. claude.ai 网页端 / 移动端（自定义连接器，MCP Streamable HTTP）
claude.ai 的自定义连接器无法设置自定义请求头，因此把密钥放在 URL 查询参数里：
1. 进入 **Settings → Connectors → Add custom connector**。
2. **Remote MCP server URL** 填：`https://<your_subdomain>.duckdns.org/mcp/http?token=your_secret_key`
3. OAuth 相关字段留空。

#### 3. Claude Desktop / Claude Code（MCP SSE 或 Streamable HTTP）
在 `~/Library/Application Support/Claude/claude_desktop_config.json`（或 Linux/Windows 对应路径）中加入：
```json
{
  "mcpServers": {
    "research-toolkit": {
      "url": "https://<your_subdomain>.duckdns.org/mcp/sse",
      "headers": {
        "Authorization": "Bearer your_secret_key"
      }
    }
  }
}
```
*(也可把 `url` 换成 Streamable HTTP 端点 `https://<your_subdomain>.duckdns.org/mcp/http`。SSE 传输只能使用 `Authorization` 请求头：服务端回传的 `/mcp/messages/` 地址不携带 `?token=`。)*


---

## 🧠 关于 Obsidian PKM 记忆沉淀的说明

在知识管理哲学上，我们遵循：
- **原始文献与 PDF 由 Zotero 管理**，不将未经研读的浅层文献卡片批量倾倒进 Obsidian，以防污染长期知识库。
- 本地系统已常驻官方 **Obsidian Headless CLI (`ob sync --continuous`)**，任何本地写入均自动跨端实时同步。
- 平时在与 Agent 讨论、阅读与分析中，当你需要沉淀重要的思考、结论或证据时，直接对 Agent 说明 **“沉淀到 PKM”** 或 **“记录到今日 Journal”**，系统将自动激活内建的 **`llm-wiki`** 技能，按规范分流写入对应目录（`20-journal/`、`90-staging/` 或 `30-projects/`）。

---

## 🧪 自动化测试

所有核心模块均由测试驱动开发（TDD）构建：
```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
覆盖多源检索限流、三级级联去重、分层排序、顶刊顶会映射、Zotero 个人文库、本地 PDF 探测及 NotebookLM 双适配器等 41 项自动化测试。
