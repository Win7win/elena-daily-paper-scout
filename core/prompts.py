"""Prompts dispatcher — re-exports the right language pack based on
``core.persona.LANGUAGE`` (driven by ``ELENA_LANGUAGE`` env var, default ``zh``).

Edit ``core/prompts_zh.py`` or ``core/prompts_en.py`` to retune prompts.
You normally don't need to touch this file.
"""

from __future__ import annotations

from core.persona import LANGUAGE


if LANGUAGE == "en":
    from core.prompts_en import (
        DIGEST_LABELS,
        SERVICE_FALLBACKS,
        compose_digest_system_prompt,
        compose_hf_system_prompt,
        eater_analyze_system_prompt,
        eater_rank_system_prompt,
        fallback_no_signal,
        fallback_overall,
        judge_system_prompt,
        judge_user_prompt,
    )
else:
    from core.prompts_zh import (
        DIGEST_LABELS,
        SERVICE_FALLBACKS,
        compose_digest_system_prompt,
        compose_hf_system_prompt,
        eater_analyze_system_prompt,
        eater_rank_system_prompt,
        fallback_no_signal,
        fallback_overall,
        judge_system_prompt,
        judge_user_prompt,
    )

__all__ = [
    "judge_system_prompt",
    "judge_user_prompt",
    "compose_hf_system_prompt",
    "compose_digest_system_prompt",
    "eater_rank_system_prompt",
    "eater_analyze_system_prompt",
    "fallback_no_signal",
    "fallback_overall",
    "SERVICE_FALLBACKS",
    "DIGEST_LABELS",
]
