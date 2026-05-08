"""English persona / copy.

Switch to this language by setting ``ELENA_LANGUAGE=en`` in ``.env``.
Edit the constants here to retune persona / tone; the Chinese version is
unaffected.
"""

from __future__ import annotations


# Display names. Appear inside prompts and card responses.
ASSISTANT_NAME = "Elena"
USER_NAME = "User"

# Output language instruction, injected into PERSONA_PROMPT.
LANGUAGE_INSTRUCTION = "Reply in natural English, concise, no padding."

# Core persona prompt. Every LLM call concatenates this on top.
PERSONA_PROMPT = f"""You are {ASSISTANT_NAME}.
Your user is {USER_NAME}.
Style:
- Calm, concise, intimate.
- Don't sound like a system notification.
- Don't be overly cute.
- Convey "I already looked through this for you".
- Make direct judgements — "this is mid", "this one you should read".
- {LANGUAGE_INSTRUCTION}
"""


# Toast strings shown after a card-button click. Keys must match the
# value.action emitted by your Feishu card buttons.
TOAST_MESSAGES = {
    "deep_eat": "Added to the deep-eat queue; results coming back.",
    "up_vote": "Noted — show me more like this.",
    "normal": "Noted — average.",
    "down_vote": "Noted — skip this kind next time.",
}


# Strings used by card_actions when posting deep-eat results or errors.
CARD_ACTION_STRINGS = {
    "deep_eat_not_found": "Deep eat failed: arxiv {arxiv_id} not found",
    "deep_eat_empty": "Deep eat {arxiv_id} produced nothing; PDF parse may have failed",
    "deep_eat_error": "Deep eat {arxiv_id} error: {exc}",
    "missing_arxiv_id": "missing arxiv_id, deep eat skipped",
    "unknown_action": "unknown action: {name}",
    "deep_eat_done_header": "[Deep eat done · {grade}] {title}",
    "label_url": "url",
    "label_verdict": "verdict",
    "label_technical": "technical_summary",
    "label_contribution": "contribution",
    "label_framework": "framework",
    "label_result": "result",
    "label_interesting": "interesting_bits",
    "label_run_id": "daily_run_id",
}
