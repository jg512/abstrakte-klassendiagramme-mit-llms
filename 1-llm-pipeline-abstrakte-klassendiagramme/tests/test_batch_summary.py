from __future__ import annotations

from pathlib import Path

import pytest

from src.runs.batch_summary import RunRecord, write_batch_summary


def _record(repo="sched", method="m1", incomplete=False, warnings=0) -> RunRecord:
    return RunRecord(
        repo=repo,
        method=method,
        run_dir=Path("runs/fake"),
        node_count=10,
        edge_count=5,
        elapsed_s=3.2,
        warnings=warnings,
        incomplete=incomplete,
    )


# write_batch_summary

def test_write_creates_file(tmp_path):
    path = write_batch_summary(tmp_path, [_record()])
    assert path.exists()
    assert path.name == "batch_summary.md"


def test_write_creates_out_dir_if_missing(tmp_path):
    out = tmp_path / "new_dir"
    write_batch_summary(out, [])
    assert out.is_dir()


def test_summary_contains_repo_and_method(tmp_path):
    path = write_batch_summary(tmp_path, [_record(repo="schedule", method="m2")])
    text = path.read_text()
    assert "schedule" in text
    assert "m2" in text


def test_summary_counts(tmp_path):
    records = [_record(), _record(repo="loguru", method="m2", incomplete=True)]
    path = write_batch_summary(tmp_path, records)
    text = path.read_text()
    assert "Total runs: 2" in text
    assert "Complete: 1" in text
    assert "Failed/incomplete: 1" in text


def test_summary_empty_records(tmp_path):
    path = write_batch_summary(tmp_path, [])
    text = path.read_text()
    assert "Total runs: 0" in text


def test_summary_incomplete_flag_visible(tmp_path):
    path = write_batch_summary(tmp_path, [_record(incomplete=True)])
    text = path.read_text()
    assert "INCOMPLETE" in text


def test_summary_ok_status_for_complete(tmp_path):
    path = write_batch_summary(tmp_path, [_record(incomplete=False)])
    text = path.read_text()
    assert "| ok |" in text


def test_summary_table_present(tmp_path):
    path = write_batch_summary(tmp_path, [_record()])
    text = path.read_text()
    assert "| Repo |" in text


def test_summary_failed_section_only_when_failures(tmp_path):
    path_ok = write_batch_summary(tmp_path / "ok", [_record()])
    path_fail = write_batch_summary(tmp_path / "fail", [_record(incomplete=True)])
    assert "## Failed runs" not in path_ok.read_text()
    assert "## Failed runs" in path_fail.read_text()
