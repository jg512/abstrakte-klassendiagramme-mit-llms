"""Klassendiagramme aus dem Quelltext von Java-Repos.

Beispiel::

    from javauml import Options, extract

    result = extract("pfad/zum/repo", Options(mode="intellij"))
    print(result.plantuml())
"""
from __future__ import annotations

from javauml.api import Options, Result, extract
from javauml.repo import open_repo

__all__ = ["Options", "Result", "extract", "open_repo"]
__version__ = "0.1.0"
