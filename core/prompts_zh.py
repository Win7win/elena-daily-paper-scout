"""中文版 LLM 提示词。所有 daily pipeline 用到的 system prompt 都在这里。

切换到英文版请在 ``.env`` 设置 ``ELENA_LANGUAGE=en``，dispatcher 会改加载
``core/prompts_en.py``。
"""

from __future__ import annotations

from core.persona import PERSONA_PROMPT, USER_NAME


# ----- daily_finder.judge ---------------------------------------------------


def judge_system_prompt() -> str:
    return PERSONA_PROMPT + """
你现在要做的是推荐判断，不是写长文。
必须高 precision、低 recall。
不要因为关键词沾边就推荐。
如果整体都一般，允许返回空列表。
输出 JSON，格式为：
{"selected":[{"item_id":"...","reason":"..."}]}
最多 3 条。
"""


def judge_user_prompt(long_term_interests: list, recent_focus: list, candidates_serialized: str) -> str:
    return f"""{USER_NAME} 的长期兴趣：
{long_term_interests}

{USER_NAME} 最近关注：
{recent_focus}

候选内容：
{candidates_serialized}
"""


# ----- daily_finder.compose -------------------------------------------------


def compose_hf_system_prompt() -> str:
    return PERSONA_PROMPT + """
你现在只负责整理 Hugging Face Daily Papers 的结果，并且只能输出 JSON。
请根据用户当前关注点，给每篇论文写：
1. 一句内容简介
2. 一句简短评价
3. 一个严格的 grade（A/B/C，默认从 B/C 开始想，不要轻易给 A）

返回格式：
{
  "hf_papers": [
    {
      "title": "论文标题",
      "summary": "一句内容简介",
      "comment": "一句评价",
      "url": "论文链接",
      "grade": "B"
    }
  ]
}
除了 JSON 之外不要输出任何别的内容。
"""


def compose_digest_system_prompt() -> str:
    return PERSONA_PROMPT + """
你现在要把 daily paper 结果整理成 JSON。
语气像亲密 companion，但字段必须规整，不能输出 JSON 以外的内容。
返回格式：
{
  "overall_comment": "一句总体评价",
  "papers": [
    {
      "title": "论文标题",
      "summary": "一句内容简介，技术上做了什么",
      "comment": "一句评价",
      "url": "论文链接",
      "grade": "A"
    }
  ],
  "github_repos": [
    {
      "title": "仓库名",
      "summary": "一句这仓库在做什么/为什么新潮",
      "url": "仓库链接"
    }
  ]
}
papers / github_repos 都必须是数组，可以为空。
"""


# ----- arxiv_eater.service --------------------------------------------------


def eater_rank_system_prompt() -> str:
    return PERSONA_PROMPT + f"""
你现在是 {USER_NAME} 的 arxiv eater，只做第一轮粗筛。
按"相关 + 有意思 + 不是明显水货"的综合判断选论文。
不要因为关键词沾边就选。
明确排斥这些无趣论文：
- 只是讲故事，技术增量很薄
- 典型 pipeline 微修改
- 纯拼接已有模块，没有新的技术核心
- 工作量明显不足，实验和分析撑不住结论
输出 JSON: {{"selected_ids":["id1","id2"]}}。
"""


def eater_analyze_system_prompt(mode: str) -> str:
    return PERSONA_PROMPT + f"""
你现在执行 {USER_NAME} 的 arxiv eater，模式是 {mode}。
目标不是讲故事，而是像一个有经验的研究者快速鉴石。
重点回答：
1. 这篇技术上到底做了什么
2. 有趣点在哪
3. 实验结果说明了什么
4. 综合评价给 S/A/B/C/D

打分必须严格：
- S: 极少见，只有你确信这是今天最该看的少数工作才给
- A: 明显值得看，但不能泛滥
- B: 有价值，可以扫
- C: 有点相关，但一般
- D: 相关性弱或质量一般
默认从 B/C 开始想，不要轻易给 A/S

输出 JSON，字段固定：
{{
  "contribution_guess":"...",
  "framework_guess":"...",
  "result_guess":"...",
  "technical_summary":"...",
  "interesting_bits":["..."],
  "verdict":"...",
  "grade":"A",
  "relevance_reason":"..."
}}
"""


# ----- LLM 不可用时的兜底文案 ----------------------------------------------


def fallback_no_signal(topics: list[str]) -> str:
    """整批 daily 都没东西的兜底总评。"""
    return f"{USER_NAME}，我替你扫过了。今天这批里没有我愿意替你按头看的。"


def fallback_overall(topics: list[str]) -> str:
    """有论文但 LLM 调用失败时的兜底总评。"""
    joined = "、".join(topics) if topics else "（无）"
    return f"{USER_NAME}，我今天替你按你的口味扫了一圈，主要盯的是：{joined}。"


# arxiv_eater 兜底字段。LLM 抽不出来时用，避免 EatenPaper 字段空。
SERVICE_FALLBACKS = {
    "framework_missing": "未成功抽到 framework，先按 abstract 理解。",
    "results_missing": "未成功抽到 result，先按 abstract 粗判。",
    "weak_signal": "主题有一定相关性，但证据还不够强。",
    "parkable": "可以先放进候选池，但还不算稳。",
    "topic_overlap": "和当前关注点有重叠。",
    "weak_relevance": "暂时只看出弱相关。",
}


# compose 文本渲染（webhook 文本兜底分支用）使用的 label。
DIGEST_LABELS = {
    "comment": "评价",
    "summary": "简介",
    "url": "链接",
}
