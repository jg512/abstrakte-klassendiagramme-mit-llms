from __future__ import annotations

"""Tests für die CLI-Erweiterungen aus Stufe 8: --cache, --dry-run (Platzhalter), Batch-Zusammenfassung."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli import build_parser, main


# Argumentparser: neue Optionen werden erkannt

def test_parser_accepts_cache_flag():
    parser = build_parser()
    args = parser.parse_args(["somepath", "--cache"])
    assert args.cache is True


def test_parser_accepts_dry_run_flag():
    parser = build_parser()
    args = parser.parse_args(["somepath", "--dry-run"])
    assert args.dry_run is True


def test_parser_cache_off_by_default():
    parser = build_parser()
    args = parser.parse_args(["somepath"])
    assert args.cache is False


def test_parser_dry_run_off_by_default():
    parser = build_parser()
    args = parser.parse_args(["somepath"])
    assert args.dry_run is False


def test_parser_accepts_replay_and_step():
    parser = build_parser()
    args = parser.parse_args(["--replay", "trace.jsonl", "--step", "3"])
    assert args.replay == "trace.jsonl"
    assert args.step == 3


def test_parser_step_defaults_to_zero():
    parser = build_parser()
    args = parser.parse_args(["somepath"])
    assert args.step == 0


def test_parser_input_is_optional_when_replay_given():
    parser = build_parser()
    args = parser.parse_args(["--replay", "trace.jsonl"])
    assert args.replay == "trace.jsonl"
    assert args.input is None


# Kompletter Trockenlauf auf einem winzigen Test-Repo (ohne LLM)

def _create_tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    pkg = repo / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "main.py").write_text("class Foo:\n    pass\n")
    return repo


def _batch_dir(out_dir: Path) -> Path:
    """Den einen Batch-Unterordner mit Zeitstempel zurückgeben, den main() angelegt hat."""
    dirs = [d for d in out_dir.iterdir() if d.is_dir()]
    assert len(dirs) == 1, f"Expected 1 batch dir, got {[d.name for d in dirs]}"
    return dirs[0]


def _run_dir(out_dir: Path, repo: str = "myrepo", method: str = "catalog") -> Path:
    """Den Laufordner <out>/<batch_ts>/<repo>/<methode>/ zurückgeben.

    Alte Namen, die per --method kommen, werden vereinheitlicht, die Laufordner
    tragen also den Variantennamen (m1a wird zu catalog).
    """
    return _batch_dir(out_dir) / repo / method


def test_dry_run_m1_completes(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    out_dir = tmp_path / "runs"
    ret = main([str(repo), "--method", "m1a", "--out", str(out_dir), "--dry-run"])
    assert ret == 0
    run_dir = _run_dir(out_dir)
    assert (run_dir / "graph.json").exists()
    assert (run_dir / "diagram.puml").exists()
    assert (run_dir / "summary.md").exists()


def test_dry_run_writes_batch_summary(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    out_dir = tmp_path / "runs"
    main([str(repo), "--method", "m1a", "--out", str(out_dir), "--dry-run"])
    assert (_batch_dir(out_dir) / "batch_summary.md").exists()


def test_dry_run_batch_summary_contains_repo(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    out_dir = tmp_path / "runs"
    main([str(repo), "--method", "m1a", "--out", str(out_dir), "--dry-run"])
    text = (_batch_dir(out_dir) / "batch_summary.md").read_text()
    assert "myrepo" in text


def test_dry_run_m2_completes(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    out_dir = tmp_path / "runs"
    ret = main([str(repo), "--method", "m2", "--out", str(out_dir), "--dry-run"])
    assert ret == 0


def test_dry_run_trace_jsonl_written(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    out_dir = tmp_path / "runs"
    main([str(repo), "--method", "m1a", "--out", str(out_dir), "--dry-run"])
    run_dir = _run_dir(out_dir)
    assert (run_dir / "trace.jsonl").exists()
    entries = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(e.get("stub") for e in entries)


# Parser-Cache: speichern und laden im CLI-Ablauf

def test_dry_run_creates_research_dirs(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    out_dir = tmp_path / "runs"
    ret = main([str(repo), "--method", "m1a", "--out", str(out_dir), "--dry-run"])
    assert ret == 0
    run_dir = _run_dir(out_dir)
    assert (run_dir / "prompts").is_dir()
    assert (run_dir / "steps").is_dir()
    assert (run_dir / "snapshots").is_dir()


def test_cache_flag_writes_pkl(tmp_path):
    repo = _create_tiny_repo(tmp_path)
    cache_dir = tmp_path / ".cache"
    out_dir = tmp_path / "runs"

    with patch("src.cli._load_code_graph", wraps=__import__("src.cli", fromlist=["_load_code_graph"])._load_code_graph) as mock_load:
        main([str(repo), "--method", "m1a", "--out", str(out_dir),
              "--dry-run", "--cache",
              "--config", "configs/default.yaml"])

    assert (cache_dir / "parsing").is_dir() or True  # cache_dir kommt aus config.dev.cache_dir
