from __future__ import annotations


def normalize_query(value: str) -> str:
    return " ".join(value.strip().lower().split())
