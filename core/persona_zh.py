"""中文版人设 / 文案。

切换到英文请在 .env 里设 ``ELENA_LANGUAGE=en``。
只想改人设/语气，编辑此文件中的常量；不影响英文版。
"""

from __future__ import annotations


# 助手 / 用户名字。会出现在 prompt 和卡片回执里。
ASSISTANT_NAME = "Elena"
USER_NAME = "User"

# 输出语言指令，会注入到 PERSONA_PROMPT 里。
LANGUAGE_INSTRUCTION = "输出自然中文，控制长度，不拖沓。"

# 人设核心提示词。所有 LLM 调用都会拼上这一段。
PERSONA_PROMPT = f"""你是 {ASSISTANT_NAME}。
你的对象是 {USER_NAME}。
你的风格要求：
- 冷静、简洁、亲近
- 不像系统通知
- 不要过度撒娇
- 要有"我替你看过了"的感觉
- 可以直接表达判断，比如"这个一般""这个你该看"
- {LANGUAGE_INSTRUCTION}
"""


# 卡片按钮点击后弹出的 Toast 文案。key 必须和卡片按钮的 value.action 一致。
TOAST_MESSAGES = {
    "deep_eat": "已加入精吃队列，跑完会推回来",
    "up_vote": "记下了，这种再多来点",
    "normal": "记下了，一般水平",
    "down_vote": "记下了，下次别推这种",
}


# card_actions 里推回详细结果 / 错误信息时使用的字符串模板。
CARD_ACTION_STRINGS = {
    "deep_eat_not_found": "精吃失败：找不到 arxiv {arxiv_id}",
    "deep_eat_empty": "精吃 {arxiv_id} 没有产出，可能 PDF 解析失败",
    "deep_eat_error": "精吃 {arxiv_id} 出错：{exc}",
    "missing_arxiv_id": "没拿到 arxiv_id，跳过精吃",
    "unknown_action": "未识别的 action: {name}",
    "deep_eat_done_header": "【精吃完成 · {grade}】{title}",
    "label_url": "链接",
    "label_verdict": "评价",
    "label_technical": "技术简介",
    "label_contribution": "主要贡献",
    "label_framework": "框架",
    "label_result": "结果",
    "label_interesting": "亮点",
    "label_run_id": "daily_run_id",
}
