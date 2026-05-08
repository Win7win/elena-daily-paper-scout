from __future__ import annotations

import re


def _slice_section(markdown: str, patterns: list[str], fallback_chars: int = 1600) -> str:
    for pattern in patterns:
        match = re.search(pattern, markdown, flags=re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1) if match.lastindex else match.group(0)
            return text.strip()[:fallback_chars]
    return markdown[:fallback_chars].strip()


def extract_signal_sections(markdown: str) -> dict[str, str]:
    """Pull the few sections that matter for a fast paper triage."""
    if not markdown:
        return {"contribution": "", "framework": "", "results": ""}

    contribution = _slice_section(
        markdown,
        [
            r"(?:#*\s*1\.?\s*Introduction.*?)(?:#*\s*2\.|\Z)",
            r"(?:#*\s*Introduction.*?)(?:#*\s*Related Work|\Z)",
        ],
    )
    framework = _slice_section(
        markdown,
        [
            r"(?:#*\s*(?:3|4)\.?\s*(?:Method|Approach|Framework|Model).*?)(?:#*\s*(?:4|5|6)\.|\Z)",
            r"(?:#*\s*(?:Method|Approach|Framework|Model).*?)(?:#*\s*(?:Experiments|Results)|\Z)",
        ],
    )
    results = _slice_section(
        markdown,
        [
            r"(?:#*\s*(?:4|5|6)\.?\s*(?:Experiments|Results).*?)(?:#*\s*(?:Conclusion|Discussion)|\Z)",
            r"(?:#*\s*(?:Experiments|Results).*?)(?:#*\s*(?:Conclusion|Discussion)|\Z)",
        ],
    )
    return {"contribution": contribution, "framework": framework, "results": results}
