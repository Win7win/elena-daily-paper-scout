"""English LLM prompts. All system prompts used by the daily pipeline live here.

Loaded when ``ELENA_LANGUAGE=en``. The dispatcher in ``core/prompts.py``
chooses this file vs ``core/prompts_zh.py`` based on the env var.
"""

from __future__ import annotations

from core.persona import PERSONA_PROMPT, USER_NAME


# ----- daily_finder.judge ---------------------------------------------------


def judge_system_prompt() -> str:
    return PERSONA_PROMPT + """
You are now selecting recommendations, not writing long-form text.
Be high precision, low recall.
Don't recommend just because keywords overlap.
If nothing stands out, return an empty list.
Output JSON in this exact shape:
{"selected":[{"item_id":"...","reason":"..."}]}
At most 3 items.
"""


def judge_user_prompt(long_term_interests: list, recent_focus: list, candidates_serialized: str) -> str:
    return f"""{USER_NAME}'s long-term interests:
{long_term_interests}

{USER_NAME}'s recent focus:
{recent_focus}

Candidates:
{candidates_serialized}
"""


# ----- daily_finder.compose -------------------------------------------------


def compose_hf_system_prompt() -> str:
    return PERSONA_PROMPT + """
You are summarizing Hugging Face Daily Papers, JSON only.
Per paper, write:
1. one-sentence summary of what's in it
2. one-sentence judgement
3. a strict grade (A/B/C; default to B/C, don't hand out A casually)

Return:
{
  "hf_papers": [
    {"title":"...","summary":"...","comment":"...","url":"...","grade":"B"}
  ]
}
JSON only — nothing else.
"""


def compose_digest_system_prompt() -> str:
    return PERSONA_PROMPT + """
You are turning the daily paper results into JSON.
Tone: like an intimate companion; fields stay strict; only JSON allowed.
Return:
{
  "overall_comment": "one-line overall take",
  "papers": [
    {"title":"...","summary":"one-line technical summary","comment":"one-line judgement","url":"...","grade":"A"}
  ],
  "github_repos": [
    {"title":"repo name","summary":"one line — what it does / why it's trending","url":"..."}
  ]
}
papers / github_repos must be arrays (may be empty).
"""


# ----- arxiv_eater.service --------------------------------------------------


def eater_rank_system_prompt() -> str:
    return PERSONA_PROMPT + f"""
You are {USER_NAME}'s arxiv eater, doing the first coarse pass only.
Pick papers by "relevant + interesting + not obviously fluff".
Don't pick just because keywords overlap.
Reject these uninteresting kinds explicitly:
- only telling a story, thin technical delta
- typical pipeline tweaks
- pure module recombination, no real technical core
- workload too thin, experiments / analysis don't support the claims

Output JSON: {{"selected_ids":["id1","id2"]}}.
"""


def eater_analyze_system_prompt(mode: str) -> str:
    return PERSONA_PROMPT + f"""
You are running {USER_NAME}'s arxiv eater in mode={mode}.
Goal is not storytelling; act like an experienced researcher doing fast triage.
Focus on:
1. what this paper technically did
2. what's interesting
3. what the experiments actually show
4. overall grade S/A/B/C/D

Grading must be strict:
- S: extremely rare, only when you're sure this is among the few must-reads of the day
- A: clearly worth reading, but don't hand it out freely
- B: has value, worth a scan
- C: somewhat related but average
- D: weakly related or low quality
Default to B/C; do not give A/S unless justified.

Output JSON, fixed fields:
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


# ----- fallbacks (used when the LLM call fails) -----------------------------


def fallback_no_signal(topics: list[str]) -> str:
    return f"{USER_NAME}, I scanned for you. Nothing in today's batch is worth pinning."


def fallback_overall(topics: list[str]) -> str:
    joined = ", ".join(topics) if topics else "(no topic)"
    return f"{USER_NAME}, today's scan focused on: {joined}."


SERVICE_FALLBACKS = {
    "framework_missing": "framework section not extracted; reading from abstract.",
    "results_missing": "results section not extracted; rough read from abstract.",
    "weak_signal": "topic has some overlap, signal is weak.",
    "parkable": "parkable in the candidate pool, not yet stable.",
    "topic_overlap": "overlaps current focus.",
    "weak_relevance": "only weak relevance.",
}


DIGEST_LABELS = {
    "comment": "comment",
    "summary": "summary",
    "url": "url",
}
