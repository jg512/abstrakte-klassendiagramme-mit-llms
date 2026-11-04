from __future__ import annotations


def estimate_tokens(s: str) -> int:
    """Grobe Token-Schätzung (Zeichen // 4) für die Warnungen zum Kontextbudget."""
    return len(s) // 4
