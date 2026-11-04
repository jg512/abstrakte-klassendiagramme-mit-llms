from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class TraceLogger:
    path: Path | None = None
    _context: dict = field(default_factory=dict, init=False, repr=False)
    # Summen über den ganzen Lauf (Driver und Cleanup) für die Kostenauswertung.
    calls: int = field(default=0, init=False)
    tokens_in: int = field(default=0, init=False)
    tokens_out: int = field(default=0, init=False)

    def set_context(self, ctx: dict) -> None:
        self._context = dict(ctx)

    def clear_context(self) -> None:
        self._context = {}

    def log(self, event: dict) -> None:
        self.calls += 1
        self.tokens_in += event.get("tokens_in", 0) or 0
        self.tokens_out += event.get("tokens_out", 0) or 0
        if self.path is None:
            return
        try:
            merged = {**self._context, **event}
            with self.path.open("a") as f:
                f.write(json.dumps(merged) + "\n")
        except OSError as e:
            log.warning("Trace write failed: %s", e)
