"""Persona dispatcher — picks Chinese or English persona pack based on
``ELENA_LANGUAGE`` (``zh`` default, ``en`` to switch).

To customize:
- Edit ``core/persona_zh.py`` for the Chinese pack (default).
- Edit ``core/persona_en.py`` for the English pack.
- Set ``ELENA_LANGUAGE=en`` in ``.env`` to load the English pack.

You normally don't need to touch this file.
"""

from __future__ import annotations

import os


LANGUAGE = (os.getenv("ELENA_LANGUAGE", "zh") or "zh").strip().lower()

if LANGUAGE == "en":
    from core.persona_en import (
        ASSISTANT_NAME,
        CARD_ACTION_STRINGS,
        LANGUAGE_INSTRUCTION,
        PERSONA_PROMPT,
        TOAST_MESSAGES,
        USER_NAME,
    )
else:
    from core.persona_zh import (
        ASSISTANT_NAME,
        CARD_ACTION_STRINGS,
        LANGUAGE_INSTRUCTION,
        PERSONA_PROMPT,
        TOAST_MESSAGES,
        USER_NAME,
    )

__all__ = [
    "LANGUAGE",
    "ASSISTANT_NAME",
    "USER_NAME",
    "LANGUAGE_INSTRUCTION",
    "PERSONA_PROMPT",
    "TOAST_MESSAGES",
    "CARD_ACTION_STRINGS",
]
