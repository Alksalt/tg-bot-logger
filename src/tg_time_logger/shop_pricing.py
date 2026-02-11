from __future__ import annotations

import re

_NOK_BEFORE = re.compile(r"(?i)\b(?:nok|kr)\s*([0-9][0-9\s.,']{0,14})\b")
_NOK_AFTER = re.compile(r"(?i)\b([0-9][0-9\s.,']{0,14})\s*(?:nok|kr)\b")


def _parse_number(value: str) -> float | None:
    raw = value.strip().replace("\u00a0", " ")
    if not raw:
        return None
    compact = raw.replace(" ", "").replace("'", "")
    if compact.count(",") == 1 and compact.count(".") == 0:
        left, right = compact.split(",", maxsplit=1)
        if len(right) == 3:
            compact = f"{left}{right}"
        else:
            compact = f"{left}.{right}"
    else:
        compact = compact.replace(",", "")
    try:
        parsed = float(compact)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def parse_nok_literal(token: str) -> float | None:
    lowered = token.strip().lower()
    if lowered.startswith("nok"):
        return _parse_number(lowered[3:])
    if lowered.startswith("kr"):
        return _parse_number(lowered[2:])
    if lowered.endswith("nok"):
        return _parse_number(lowered[:-3])
    if lowered.endswith("kr"):
        return _parse_number(lowered[:-2])
    return None


def extract_nok_candidates(text: str) -> list[float]:
    ordered: list[tuple[int, float]] = []
    for pat in (_NOK_BEFORE, _NOK_AFTER):
        for m in pat.finditer(text):
            parsed = _parse_number(m.group(1))
            if parsed is None:
                continue
            if parsed < 10 or parsed > 1_000_000:
                continue
            ordered.append((m.start(), parsed))
    ordered.sort(key=lambda item: item[0])
    return [v for _, v in ordered]


def pick_nok_candidate(text: str) -> float | None:
    candidates = extract_nok_candidates(text)
    if not candidates:
        return None
    return candidates[0]


def nok_to_fun_minutes(nok_value: float, minutes_per_nok: int) -> int:
    ratio = max(1, int(minutes_per_nok))
    return max(1, int(round(float(nok_value) * ratio)))
