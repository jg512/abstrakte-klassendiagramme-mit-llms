from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import load_config
from src.runs.output_writer import (
    _safe_name,
    create_run_dir,
    write_static_graph_outputs,
    write_run_outputs,
)
from src.schema.graph import AbstractGraph, Edge, Node, Package


# _safe_name

def test_safe_name_alnum():
    assert _safe_name("schedule") == "schedule"


def test_safe_name_replaces_slashes():
    assert _safe_name("foo/bar") == "foo_bar"


def test_safe_name_keeps_hyphens_underscores():
    assert _safe_name("my-repo_v2") == "my-repo_v2"


def test_safe_name_empty():
    assert _safe_name("") == ""


# create_run_dir

def test_create_run_dir_creates_directory(tmp_path):
    run_dir = create_run_dir(tmp_path, "schedule", "m1", batch_ts="20240101T120000")
    assert run_dir.is_dir()
    # Aufbau: <out>/<batch_ts>/<repo>/<methode>
    assert run_dir.name == "m1"
    assert run_dir.parent.name == "schedule"
    assert run_dir.parent.parent.name == "20240101T120000"


def test_create_run_dir_sanitises_repo_name(tmp_path):
    run_dir = create_run_dir(tmp_path, "my/repo", "m1", batch_ts="20240101T120000")
    assert run_dir.parent.name == "my_repo"


def test_create_run_dir_auto_timestamp(tmp_path):
    run_dir = create_run_dir(tmp_path, "repo", "m1")
    assert run_dir.is_dir()
    # Der Zeitstempel-Ordner sieht aus wie YYYYmmddTHHMMSS (15 Zeichen)
    ts_folder = run_dir.parent.parent.name
    assert len(ts_folder) == 15
    assert "T" in ts_folder


def test_create_run_dir_idempotent(tmp_path):
    run_dir = create_run_dir(tmp_path, "repo", "m1", batch_ts="20240101T120000")
    run_dir2 = create_run_dir(tmp_path, "repo", "m1", batch_ts="20240101T120000")
    assert run_dir == run_dir2


def test_create_run_dir_methods_share_batch_folder(tmp_path):
    m1_dir = create_run_dir(tmp_path, "schedule", "m1", batch_ts="20240101T120000")
    m2_dir = create_run_dir(tmp_path, "schedule", "m2", batch_ts="20240101T120000")
    assert m1_dir.parent.parent == m2_dir.parent.parent  # derselbe Batch-Ordner
    assert m1_dir.parent == m2_dir.parent                # derselbe Repo-Ordner
    assert m1_dir.name != m2_dir.name


# write_run_outputs

def _simple_graph() -> AbstractGraph:
    g = AbstractGraph(repo="schedule", target_nodes=5)
    g.packages.append(Package(name="schedule"))
    g.nodes.append(Node(
        id="schedule.Scheduler",
        name="Scheduler",
        package="schedule",
        attributes=["jobs: list"],
        methods=["run_pending()"],
    ))
    g.edges.append(Edge(source="schedule.Scheduler", target="schedule.Scheduler", type="dependency"))
    return g


def test_write_run_outputs_creates_files(tmp_path):
    config = load_config()
    graph = _simple_graph()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    write_run_outputs(run_dir, graph, config, [], "m1", 3.5)

    assert (run_dir / "graph.json").exists()
    assert (run_dir / "diagram.puml").exists()
    assert (run_dir / "config.yaml").exists()
    assert (run_dir / "summary.md").exists()


def test_write_run_outputs_no_errors_log_when_no_warnings(tmp_path):
    config = load_config()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_outputs(run_dir, _simple_graph(), config, [], "m1", 1.0)
    assert not (run_dir / "errors.log").exists()


def test_write_run_outputs_errors_log_present_when_warnings(tmp_path):
    config = load_config()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_outputs(run_dir, _simple_graph(), config, ["something went wrong"], "m1", 1.0)
    assert (run_dir / "errors.log").exists()
    assert "something went wrong" in (run_dir / "errors.log").read_text()


def test_write_run_outputs_graph_json_valid(tmp_path):
    config = load_config()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_outputs(run_dir, _simple_graph(), config, [], "m1", 1.0)
    data = json.loads((run_dir / "graph.json").read_text())
    assert data["repo"] == "schedule"
    assert len(data["nodes"]) == 1


def test_write_run_outputs_puml_contains_class(tmp_path):
    config = load_config()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_outputs(run_dir, _simple_graph(), config, [], "m1", 1.0)
    puml = (run_dir / "diagram.puml").read_text()
    assert "Scheduler" in puml
    assert "@startuml" in puml


def test_write_run_outputs_summary_contains_key_fields(tmp_path):
    config = load_config()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_outputs(run_dir, _simple_graph(), config, [], "m1", 7.3)
    summary = (run_dir / "summary.md").read_text()
    assert "schedule" in summary
    assert "m1" in summary
    assert "7.3" in summary


def test_write_run_outputs_incomplete_flag(tmp_path):
    config = load_config()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_outputs(run_dir, _simple_graph(), config, [], "m1", 1.0, incomplete=True)
    summary = (run_dir / "summary.md").read_text()
    assert "INCOMPLETE" in summary


# write_static_graph_outputs

def test_write_static_graph_outputs_creates_files(tmp_path):
    graph = AbstractGraph(
        repo="myrepo",
        target_nodes=5,
        nodes=[Node(id="myrepo.A", name="A", package="myrepo", stereotype=None, attributes=[], methods=[])],
        edges=[],
    )
    write_static_graph_outputs(tmp_path, "myrepo", "20240101T120000", graph)
    repo_dir = tmp_path / "20240101T120000" / "myrepo"
    assert (repo_dir / "pyreverse.json").exists()
    assert (repo_dir / "pyreverse.puml").exists()
    data = json.loads((repo_dir / "pyreverse.json").read_text())
    assert data["repo"] == "myrepo"
