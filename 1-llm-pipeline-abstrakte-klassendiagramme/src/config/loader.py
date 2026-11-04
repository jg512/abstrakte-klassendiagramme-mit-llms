from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml

from src.parsing.languages import DEFAULT_LANGUAGE, LANGUAGES

from .models import (
    ClusteringConfig,
    Config,
    DevConfig,
    DriverConfig,
    FiltersConfig,
    JavaConfig,
    OutputConfig,
    SizeCapsConfig,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "configs" / "default.yaml"


class ConfigError(ValueError):
    pass


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file {path} must be a YAML mapping, got {type(data).__name__}"
        )
    return data


def _validate(d: dict[str, Any]) -> None:
    errors: list[str] = []

    language = str(d.get("language", DEFAULT_LANGUAGE)).strip().lower()
    if language not in LANGUAGES:
        errors.append(
            f"'language' must be one of {', '.join(sorted(LANGUAGES))}, got {language!r}"
        )

    if not d.get("model"):
        errors.append("'model' must be non-empty")

    if not d.get("backend"):
        errors.append("'backend' must be non-empty")

    temperature = d.get("temperature", 0)
    if not (0 <= float(temperature) <= 2):
        errors.append(f"'temperature' must be between 0 and 2, got {temperature}")

    num_ctx = d.get("num_ctx", 2048)
    if int(num_ctx) <= 1024:
        errors.append(f"'num_ctx' must be > 1024, got {num_ctx}")

    target_nodes = d.get("target_nodes", 0)
    if not _is_open_target(target_nodes):
        if not d.get("auto_target_nodes", False) and int(target_nodes) <= 0:
            errors.append(f"'target_nodes' must be > 0 or 'open', got {target_nodes}")

    max_nodes = d.get("max_nodes", 40)
    if int(max_nodes) <= 0:
        errors.append(f"'max_nodes' must be > 0, got {max_nodes}")

    node_tolerance = d.get("node_tolerance", 0)
    if not (0 <= float(node_tolerance) <= 1):
        errors.append(f"'node_tolerance' must be between 0 and 1, got {node_tolerance}")

    driver = d.get("driver", {})
    if isinstance(driver, dict):
        for field, val in driver.items():
            if isinstance(val, (int, float)) and val < 0:
                errors.append(f"driver.{field} must be non-negative, got {val}")

    clustering = d.get("clustering", {})
    if isinstance(clustering, dict):
        share = clustering.get("synthesis_share", 0.25)
        if not (0 < float(share) < 1):
            errors.append(f"clustering.synthesis_share must be between 0 and 1, got {share}")
        for field in ("max_cluster_size", "min_cluster_size"):
            val = clustering.get(field, 1)
            if isinstance(val, (int, float)) and val < 1:
                errors.append(f"clustering.{field} must be >= 1, got {val}")

    java = d.get("java", {})
    if isinstance(java, dict):
        source_sets = str(java.get("source_sets", "auto"))
        if source_sets not in {"auto", "all"}:
            errors.append(f"java.source_sets must be 'auto' or 'all', got {source_sets!r}")
        profile = str(java.get("member_profile", "summary"))
        if profile not in {"structure", "summary", "public-api", "full"}:
            errors.append(
                "java.member_profile must be structure, summary, public-api, or full, "
                f"got {profile!r}"
            )
        solver = str(java.get("symbol_solver", "source"))
        if solver not in {"source", "javac"}:
            errors.append(f"java.symbol_solver must be 'source' or 'javac', got {solver!r}")
        style = str(java.get("relation_style", "literal"))
        if style not in {"literal", "intellij"}:
            errors.append(f"java.relation_style must be 'literal' or 'intellij', got {style!r}")

    if errors:
        raise ConfigError(
            "Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


def _build(d: dict[str, Any]) -> Config:
    flt = d.get("filters", {})
    caps = d.get("size_caps", {})
    drv = d.get("driver", {})
    clu = d.get("clustering", {})
    out = d.get("output", {})
    dev = d.get("dev", {})
    java = d.get("java", {})

    return Config(
        language=str(d.get("language", DEFAULT_LANGUAGE)).strip().lower(),
        backend=d["backend"],
        model=d["model"],
        base_url=str(d.get("base_url", "")),
        api_key_env=str(d.get("api_key_env", "")),
        temperature=float(d.get("temperature", 0)),
        num_ctx=int(d.get("num_ctx", 32768)),
        seed=int(d.get("seed", 42)),
        request_timeout=int(d.get("request_timeout", 0)),
        target_nodes=None if _is_open_target(d["target_nodes"]) else int(d["target_nodes"]),
        max_nodes=int(d.get("max_nodes", 40)),
        node_tolerance=float(d["node_tolerance"]),
        cleanup=bool(d.get("cleanup", True)),
        auto_target_nodes=bool(d.get("auto_target_nodes", False)),
        context_budget=int(d.get("context_budget", 24_000)),
        driver=DriverConfig(
            max_tool_calls=int(drv.get("max_tool_calls", 40)),
            max_tokens=int(drv.get("max_tokens", 30_000)),
            read_file_max_lines=int(drv.get("read_file_max_lines", 200)),
            compress_every_n_turns=int(drv.get("compress_every_n_turns", 0)),
        ),
        clustering=ClusteringConfig(
            max_cluster_size=int(clu.get("max_cluster_size", 40)),
            min_cluster_size=int(clu.get("min_cluster_size", 3)),
            synthesis_share=float(clu.get("synthesis_share", 0.25)),
        ),
        filters=FiltersConfig(
            exclude_dirs=tuple(flt.get("exclude_dirs", [])),
            exclude_files=tuple(flt.get("exclude_files", [])),
        ),
        size_caps=SizeCapsConfig(
            max_loc=int(caps.get("max_loc", 20000)),
            max_classes=int(caps.get("max_classes", 300)),
        ),
        output=OutputConfig(
            dir=str(out.get("dir", "runs")),
            write_pyreverse=bool(out.get("write_pyreverse", True)),
            trace_jsonl=bool(out.get("trace_jsonl", True)),
            trace_messages=bool(out.get("trace_messages", False)),
        ),
        dev=DevConfig(
            cache_dir=str(dev.get("cache_dir", ".cache")),
            verbose=bool(dev.get("verbose", False)),
        ),
        java=JavaConfig(
            source_sets=str(java.get("source_sets", "auto")),
            include_generated=bool(java.get("include_generated", False)),
            member_profile=str(java.get("member_profile", "summary")),
            include_external_supertypes=bool(java.get("include_external_supertypes", True)),
            include_method_dependencies=bool(java.get("include_method_dependencies", False)),
            symbol_solver=str(java.get("symbol_solver", "source")),
            classpath=tuple(str(p) for p in java.get("classpath", [])),
            relation_style=str(java.get("relation_style", "literal")),
            ide_jdk=bool(java.get("ide_jdk", True)),
            ide_same_package=bool(java.get("ide_same_package", True)),
            diagram_classes=tuple(str(c) for c in java.get("diagram_classes", [])),
        ),
    )


def load_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Konfiguration laden und prüfen.

    Vorrang (hoch nach niedrig): overrides, dann config_path, dann Standardwerte.
    """
    data = _load_yaml(_DEFAULT_CONFIG)

    if config_path is not None:
        user_data = _load_yaml(Path(config_path))
        data = _deep_merge(data, user_data)

    if overrides:
        data = _deep_merge(data, overrides)

    _validate(data)
    cfg = _build(data)
    logger.debug("Config loaded: backend=%s model=%s target_nodes=%s", cfg.backend, cfg.model, cfg.target_nodes)
    return cfg


def _is_open_target(value: Any) -> bool:
    """target_nodes: 'open' (oder null) heißt, das Modell wählt die Größe des Graphen selbst."""
    return value is None or (isinstance(value, str) and value.strip().lower() == "open")
