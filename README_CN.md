# elena-daily-paper-scout

> 每日论文推荐机器人，扫 arXiv / HuggingFace / GitHub Trending，LLM 打分后通过飞书互动卡片推送，按钮反馈闭环。

一个面向飞书的每日文献推荐机器人。每天定时把 arXiv / HuggingFace Daily Papers / GitHub Trending 扫一遍，由 LLM 做相关性判断和打分，按互动卡片推到指定飞书群里，附带四个反馈按钮：

- **精吃**：异步触发对该论文的深度阅读（PDF 解析 + 重新分析），跑完后把详细结果发回群里。
- **棒** / **一般** / **踩**：记录这篇论文的评价，最近一次评价覆盖之前的，写到 `feedback_latest.json` 给后续调味用。

![每日推送效果](./example_result.png)

当前能力：

- 飞书自建应用 + WebSocket 长连接推送和回调（不需要公网 HTTPS）
- 四张互动卡片：每日摘要 / arXiv / HF Daily Papers / GitHub Trending
- LLM 二段筛选：粗排（标题 + abstract）→ 精读（PDF 全文 / abstract-only）
- 反馈双层存储：`feedback.jsonl` 全量审计 + `feedback_latest.json` 当前评价
- `card.action.trigger` 事件在主线程监听，每日推送在后台 daemon 线程定时跑
- 找不到自建应用凭证时，自动回退到 webhook 纯文本推送

当前限制：

- 飞书卡片模板需要你自己在飞书卡片搭建台导入并发版（提供 `.card` 源文件）
- arXiv 官方接口偶尔 429，需要本地科学上网；可设置 `ELENA_HTTP_PROXY`
- 精吃 PDF 默认走 MinerU，需要单独安装；不装也能跑（自动 fallback）

## 环境要求

- Python 3.11+
- Python 依赖见 `requirements.txt`，核心是：
  - `lark-oapi>=1.5.3`（飞书 SDK）
  - `requests` / `feedparser` / `beautifulsoup4` / `lxml`（抓取）
  - `pydantic` / `python-dotenv` / `tenacity` / `rich` / `pdfplumber`
- 一个 OpenAI 兼容的 LLM endpoint（OpenAI、DeepSeek、Qwen、本地 vLLM 都行）
- 可选：MinerU（精吃 PDF 解析），不装会自动降级为只看摘要

## 安装

### 1. 安装 Python 依赖

```bash
cd /path/to/elena
pip install -r requirements.txt
```

### 2. 注册飞书机器人

1. 打开飞书开发者平台：
   `https://open.feishu.cn/app`
2. 创建企业自建应用。
   飞书个人版也可以创建，但只能供个人使用。
3. 在应用管理后台中，进入 `应用能力` -> `添加能力`，添加 `机器人` 能力。
4. 进入 `开发配置` -> `事件与回调`。
5. 在 `事件配置` 中，将 `订阅方式` 设置为 `长连接`。
6. 在 `事件配置` 中，添加事件 `接收消息` -> `im.message.receive_v1`。
   （只用于第一次拿 `chat_id`，之后可以保留。）
7. 在 `回调配置` 中，点击 `添加回调`，选择 `卡片回传交互 card.action.trigger`。
   这一步是关键 —— 卡片按钮点击都通过这个回调送回来，没配的话精吃和评价按钮都不会触发任何事情。
8. 进入 `开发配置` -> `权限管理`，开通以下应用身份权限：
   - `im:message.p2p_msg:readonly`：读取用户发给机器人的单聊消息（用于第一步拿 chat_id）
   - `im:message:send_as_bot`：以应用的身份发消息（推送卡片）
   - `im:message`：发送/读取消息（卡片是 interactive message）
9. 在后台上方点击 `创建版本`，然后发布应用。
10. 把机器人拉进你想接收推送的群（或单聊）。

发布完成后，就可以在飞书消息列表中看到这个机器人。

### 3. 导入飞书卡片模板

`feishu_cards/` 下有四个 `.card` 文件：

- `Elena 每日扫描.card` —— 每日摘要卡片（顶部那张概览）
- `Arxiv学术论文推荐.card` —— arXiv 列表卡片，每篇论文带 4 个按钮
- `hf_papers_v1.card` —— HuggingFace Daily Papers 卡片
- `gh_daily_v1.card` —— GitHub Trending 卡片

每张卡片都需要单独在飞书卡片搭建台导入并发版：

1. 打开 `https://open.feishu.cn/cardkit`
2. 新建卡片 -> 导入 -> 选择对应的 `.card` 文件
3. 发版（注意记下 `template_id` 和 `template_version`）
4. 把 `template_id` / `template_version` 填到 `.env` 里对应的环境变量

按钮上的 `value` 字段已经在卡片里配好，不用改。如果你想改按钮文案或者增加按钮，参考 arXiv 卡片里的写法：

```json
{
  "tag": "button",
  "text": { "tag": "plain_text", "content": "精吃" },
  "value": {
    "action": "deep_eat",
    "arxiv_id": "${arxiv_id}",
    "title": "${title}",
    "grade": "${grade}",
    "daily_run_id": "${daily_run_id}"
  }
}
```

`value.action` 是机器人侧的派发 key，必须是 `deep_eat` / `up_vote` / `normal` / `down_vote` 中的一个，否则会被当成未知按钮丢掉。

### 4. 填写本地配置

复制配置模板：

```bash
cp .env.example .env
```

至少需要填写：

- `OPENAI_API_KEY`
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
- `FEISHU_DAILY_CHAT_ID`
- 四个 `FEISHU_TEMPLATE_*_ID` 和 `_VERSION`

#### 怎么拿 `FEISHU_DAILY_CHAT_ID`

填好 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 之后，跑：

```bash
python scripts/get_chat_id.py
```

它会建立长连接并等你发一条消息。在飞书里给机器人发"hi"或者在群里 @ 它一下，脚本会打印出 `chat_id` 然后退出。

把这个 `chat_id` 填回 `.env` 的 `FEISHU_DAILY_CHAT_ID`。

### 5. 启动服务

立刻跑一次（不进入常驻模式，验证整条链路）：

```bash
./run_elena_server.sh --once
```

进入常驻模式（推荐放 tmux 里）：

```bash
./run_elena_server.sh
```

常驻模式做两件事：

- **后台调度线程**：按 `DAILY_SCHEDULE_UTC` 每天定时跑一次 daily（默认 02:30 UTC = 10:30 UTC+8）
- **主线程监听**：跑 `card.action.trigger` 长连接，处理按钮点击

如果你只想手动跑 daily、不需要按钮回调，可以加 `--no-listener`：

```bash
./run_elena_server.sh --no-listener
```

如果只测推送、不想真发到飞书：

```bash
./run_elena_server.sh --once --no-push
```

## 自定义

### 切换中英文

人设 / 提示词 / Toast 文案 / 卡片回执文字都同时维护了中文和英文两份，由 `.env` 里的 `ELENA_LANGUAGE` 切换：

```bash
ELENA_LANGUAGE=zh   # 默认，加载 core/persona_zh.py + core/prompts_zh.py
ELENA_LANGUAGE=en   # 加载 core/persona_en.py + core/prompts_en.py
```

`core/persona.py` 和 `core/prompts.py` 是 dispatcher，根据 env 选语言包，正常不需要动。

### 修改人设 / 用户名 / 风格

编辑你正在用的语言包文件 —— 中文用户改 `core/persona_zh.py`：

```python
ASSISTANT_NAME = "Elena"
USER_NAME = "User"
LANGUAGE_INSTRUCTION = "输出自然中文，控制长度，不拖沓。"
PERSONA_PROMPT = f"""你是 {ASSISTANT_NAME}。
你的对象是 {USER_NAME}。
..."""
```

`PERSONA_PROMPT` 是所有 LLM 调用都会拼上的系统提示词。改这一段就能整体调整语气，不影响 prompt 模块。
英文用户对应改 `core/persona_en.py`，两份互不干扰。

### 修改 LLM Prompt

中文 prompt 在 `core/prompts_zh.py`，英文在 `core/prompts_en.py`。两个文件函数一一对应：

- `judge_system_prompt()` —— 第一阶段相关性筛选
- `eater_rank_system_prompt()` —— 粗排选哪几篇值得展开看
- `eater_analyze_system_prompt(mode)` —— 单篇论文的速吃 / 精吃分析
- `compose_digest_system_prompt()` —— 整理 daily 摘要
- `compose_hf_system_prompt()` —— 整理 HF Daily Papers

所有提示词都会自动拼上 `PERSONA_PROMPT`，这里只写"任务规则"，不用重复人设。

### 修改 Toast / 按钮文案

在 `core/persona_zh.py`（或 `_en.py`）里的 `TOAST_MESSAGES` 字典：

```python
TOAST_MESSAGES = {
    "deep_eat": "已加入精吃队列，跑完会推回来",
    "up_vote": "记下了，这种再多来点",
    "normal": "记下了，一般水平",
    "down_vote": "记下了，下次别推这种",
}
```

key 必须和卡片按钮的 `value.action` 一致。

同一文件的 `CARD_ACTION_STRINGS` 控制精吃完成 / 出错时推回来的详细消息文案，包括字段标签（评价 / 技术简介 / 主要贡献 等）。

### 修改 active_topics（你想看什么）

`skills/daily_finder/config.json` 里：

```json
{
  "active_topics": ["coding agents", "terminal tools", "paper triage"],
  "arxiv_days_back": 7,
  "arxiv_fetch_limit": 30,
  "candidate_top_k": 5,
  "basic_pdf_top_k": 5,
  "daily_send_top_k": 5,
  "hf_relevant_top_k": 10,
  "github_trending_top_k": 3
}
```

第一次运行会自动写入默认值。`active_topics` 决定 arXiv 的搜索词；其它字段控制每个阶段保留多少条。

如果不想用 config 文件而是按运行时的 memory 走，把 `active_topics` 留空，pipeline 会用 `data/memory.json` 里的 `recent_focus` 作为兜底。

## 反馈数据

按钮点击会写两个文件（位于 `data/` 或 `ELENA_DATA_DIR` 指定的目录）：

- `feedback.jsonl` —— 追加写，每次点击一行 JSON，全量审计用
- `feedback_latest.json` —— 字典，key 是 `arxiv_id`，value 是最新一次评价（最后一次按钮点击会覆盖前面的）

`deep_eat` 按钮**不算**反馈，只触发后台精吃然后把结果发回来；不会写 `feedback_latest.json`。

后续可以把 `feedback_latest.json` 喂回 ranker / judge 的 prompt 做口味校准，目前只是采集。

## 服务命令行参数

```
./run_elena_server.sh [--once] [--no-push] [--no-listener]
                       [--schedule HH:MM] [--poll-seconds N]
```

- `--once`：立即跑一次 daily 并退出，不进入常驻模式
- `--no-push`：不推送到飞书，只算结果（适合本地调试）
- `--no-listener`：跳过 `card.action.trigger` 监听，只起调度线程
- `--schedule HH:MM`：覆盖 `DAILY_SCHEDULE_UTC`
- `--poll-seconds N`：调度线程轮询间隔（默认 30s）

## 最小 `.env`

```bash
ELENA_LANGUAGE=zh
OPENAI_API_KEY=sk-xxxxxxxxxxxx
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
FEISHU_DAILY_CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_TEMPLATE_DAILY_SUMMARY_ID=AAxxxxxxxxxxx
FEISHU_TEMPLATE_DAILY_SUMMARY_VERSION=1.0.0
FEISHU_TEMPLATE_ARXIV_PAPER_ID=AAxxxxxxxxxxx
FEISHU_TEMPLATE_ARXIV_PAPER_VERSION=1.0.0
FEISHU_TEMPLATE_HF_PAPERS_ID=AAxxxxxxxxxxx
FEISHU_TEMPLATE_HF_PAPERS_VERSION=1.0.0
FEISHU_TEMPLATE_GH_TRENDING_ID=AAxxxxxxxxxxx
FEISHU_TEMPLATE_GH_TRENDING_VERSION=1.0.0
DAILY_SCHEDULE_UTC=02:30
```

## 目录结构

```
.
├── README_CN.md
├── README.md
├── requirements.txt
├── .env.example
├── server.py                  # 调度 + 监听入口
├── run_elena_server.sh        # 启动脚本（设代理/工作目录）
├── core/
│   ├── persona.py             # 语言 dispatcher（按 ELENA_LANGUAGE 选包）
│   ├── persona_zh.py          # ★ 中文人设 / Toast / 卡片回执文案
│   ├── persona_en.py          # ★ 英文人设 / Toast / 卡片回执文案
│   ├── prompts.py             # 提示词 dispatcher
│   ├── prompts_zh.py          # ★ 中文 LLM system prompt 全部
│   ├── prompts_en.py          # ★ 英文 LLM system prompt 全部
│   ├── settings.py            # 环境变量集中读取
│   ├── memory.py              # 长期兴趣 / 最近关注
│   ├── archive.py             # 论文归档
│   ├── feedback.py            # 反馈双层存储
│   ├── card_actions.py        # card.action.trigger 派发
│   ├── feishu_app.py          # 自建应用：发卡片 / 监听
│   ├── feishu.py              # webhook 文本推送（fallback）
│   ├── llm.py                 # OpenAI 兼容客户端
│   └── models.py              # pydantic 数据模型
├── skills/
│   ├── daily_finder/
│   │   ├── run_daily.py       # 主流水线
│   │   ├── arxiv_client.py    # arXiv API
│   │   ├── github_client.py   # GH Trending 抓取
│   │   ├── hf_papers_client.py# HF Daily Papers 抓取
│   │   ├── filter.py          # 关键词粗筛
│   │   ├── judge.py           # LLM 高 precision 选片
│   │   ├── compose.py         # daily digest 组装
│   │   ├── cards.py           # 把结果填进卡片变量
│   │   └── config.py          # active_topics / top_k
│   └── arxiv_eater/
│       ├── service.py         # 速吃 / 精吃
│       ├── pdf_ops.py         # MinerU + pdfplumber
│       ├── section_extract.py # 提取 contribution / framework / results
│       └── config.py          # 并发数 / pdf_mode 等
├── scripts/
│   ├── elena_env.sh
│   ├── get_chat_id.py         # 抓 chat_id
│   ├── listen_card_actions.py # 单独 echo 卡片回调
│   ├── test_card_send.py      # 摘要卡片冒烟
│   ├── test_card_arxiv.py     # arXiv 卡片冒烟（4 按钮）
│   └── test_card_hf_gh.py     # HF + GH 卡片冒烟
└── feishu_cards/              # 卡片导出文件（.card）
```
