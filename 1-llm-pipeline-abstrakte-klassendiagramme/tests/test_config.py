from __future__ import annotations

import pytest
from pathlib import Path

from src.config import Config, ConfigError, load_config


def test_load_defaults_populates_all_fields():
    cfg = load_config()
    assert cfg.backend == "gemini"
    assert cfg.model == "gemini-2.5-pro"
    assert cfg.temperature == 0.1
    assert cfg.num_ctx == 32768
    assert cfg.seed == 42
    assert cfg.target_nodes == 20
    assert cfg.node_tolerance == 0.2
    assert cfg.cleanup is True
    assert "tests" in cfg.filters.exclude_dirs
    assert "test_*.py" in cfg.filters.exclude_files
    assert cfg.size_caps.max_loc == 20000
    assert cfg.size_caps.max_classes == 300
    assert cfg.driver.max_tool_calls == 40
    assert cfg.driver.max_tokens == 30000
    assert cfg.driver.read_file_max_lines == 200
    assert cfg.clustering.max_cluster_size == 40
    assert cfg.clustering.min_cluster_size == 3
    assert cfg.clustering.synthesis_share == 0.25
    assert cfg.output.dir == "runs"
    assert cfg.output.write_pyreverse is True
    assert cfg.dev.verbose is False
    assert cfg.dev.cache_dir == ".cache"


def test_config_is_immutable():
    cfg = load_config()
    with pytest.raises((AttributeError, TypeError)):
        cfg.backend = "openai"  # type: ignore[misc]


def test_override_top_level():
    cfg = load_config(overrides={"target_nodes": 30, "temperature": 0.5})
    assert cfg.target_nodes == 30
    assert cfg.temperature == 0.5
    assert cfg.backend == "gemini"  # Standardwert unverändert


def test_nested_override_merges_siblings():
    cfg = load_config(overrides={"dev": {"verbose": True}})
    assert cfg.dev.verbose is True
    assert cfg.dev.cache_dir == ".cache"  # Nachbarschlüssel bleibt erhalten


def test_custom_config_file(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("target_nodes: 50\ntemperature: 1.0\n", encoding="utf-8")
    cfg = load_config(config_path=custom)
    assert cfg.target_nodes == 50
    assert cfg.temperature == 1.0
    assert cfg.backend == "gemini"  # Standardwert bleibt erhalten


def test_overrides_beat_custom_file(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("target_nodes: 50\n", encoding="utf-8")
    cfg = load_config(config_path=custom, overrides={"target_nodes": 99})
    assert cfg.target_nodes == 99


def test_malformed_yaml_raises_config_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="Malformed YAML"):
        load_config(config_path=bad)


def test_non_mapping_yaml_raises_config_error(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML mapping"):
        load_config(config_path=bad)


def test_missing_config_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(config_path=tmp_path / "nonexistent.yaml")


def test_invalid_target_nodes_zero():
    with pytest.raises(ConfigError, match="target_nodes"):
        load_config(overrides={"target_nodes": 0})


def test_invalid_target_nodes_negative():
    with pytest.raises(ConfigError, match="target_nodes"):
        load_config(overrides={"target_nodes": -5})


def test_invalid_temperature_too_high():
    with pytest.raises(ConfigError, match="temperature"):
        load_config(overrides={"temperature": 2.1})


def test_invalid_temperature_negative():
    with pytest.raises(ConfigError, match="temperature"):
        load_config(overrides={"temperature": -0.1})


def test_invalid_node_tolerance_above_one():
    with pytest.raises(ConfigError, match="node_tolerance"):
        load_config(overrides={"node_tolerance": 1.5})


def test_invalid_num_ctx_too_small():
    with pytest.raises(ConfigError, match="num_ctx"):
        load_config(overrides={"num_ctx": 512})


def test_empty_model_raises():
    with pytest.raises(ConfigError, match="model"):
        load_config(overrides={"model": ""})


def test_empty_backend_raises():
    with pytest.raises(ConfigError, match="backend"):
        load_config(overrides={"backend": ""})


def test_negative_budget_raises():
    with pytest.raises(ConfigError, match="driver"):
        load_config(overrides={"driver": {"max_tool_calls": -1}})


def test_bad_synthesis_share_raises():
    with pytest.raises(ConfigError, match="synthesis_share"):
        load_config(overrides={"clustering": {"synthesis_share": 1.5}})


def test_multiple_validation_errors_reported_together():
    with pytest.raises(ConfigError) as exc_info:
        load_config(overrides={"target_nodes": 0, "temperature": 5.0})
    msg = str(exc_info.value)
    assert "target_nodes" in msg
    assert "temperature" in msg
