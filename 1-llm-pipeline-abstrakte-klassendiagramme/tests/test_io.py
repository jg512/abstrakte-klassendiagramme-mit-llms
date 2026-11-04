from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.config.models import FiltersConfig, JavaConfig, SizeCapsConfig
from src.io.filters import collect_python_files, collect_source_files
from src.io.preflight import PreflightError, PreflightResult, run_preflight
from src.io.repo_loader import RepoLoadError, load_repo


# Hilfsfunktionen


def _make_filters(**kwargs) -> FiltersConfig:
    defaults = dict(
        exclude_dirs=("tests", "test", "**/test_*", ".venv", "__pycache__"),
        exclude_files=("test_*.py", "*_test.py", "conftest.py", "setup.py"),
    )
    defaults.update(kwargs)
    return FiltersConfig(**defaults)


def _make_caps(**kwargs) -> SizeCapsConfig:
    defaults = dict(max_loc=20_000, max_classes=300)
    defaults.update(kwargs)
    return SizeCapsConfig(**defaults)


# repo_loader


class TestLoadRepo:
    def test_local_path_exists(self, tmp_path):
        result = list(load_repo(str(tmp_path)))
        assert result == [tmp_path]

    def test_local_path_missing_raises(self, tmp_path):
        missing = str(tmp_path / "does_not_exist")
        with pytest.raises(RepoLoadError, match="Path not found"):
            list(load_repo(missing))

    def test_batch_file_yields_local_paths(self, tmp_path):
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        batch = tmp_path / "repos.txt"
        batch.write_text(
            textwrap.dedent(f"""\
                # this is a comment
                {repo_a}

                {repo_b}
                # another comment
            """)
        )

        result = list(load_repo(str(batch)))
        assert result == [repo_a, repo_b]

    def test_batch_file_missing_raises(self, tmp_path):
        with pytest.raises(RepoLoadError, match="Batch file not found"):
            list(load_repo(str(tmp_path / "missing.txt")))

    def test_batch_file_with_missing_entry_raises(self, tmp_path):
        batch = tmp_path / "repos.txt"
        batch.write_text("/nonexistent/path\n")
        with pytest.raises(RepoLoadError, match="Path not found"):
            list(load_repo(str(batch)))

    def test_url_detection_https(self):
        # Getestet wird nur die Erkennung, nicht das echte Klonen (das wäre ein Netztest).
        # subprocess wird ersetzt, damit nichts wirklich geklont wird.
        import unittest.mock as mock

        fake_tmp = Path("/tmp/fake_clone")
        with mock.patch("src.io.repo_loader.subprocess.run") as mock_run, \
             mock.patch("src.io.repo_loader.tempfile.mkdtemp", return_value=str(fake_tmp)):
            mock_run.return_value = mock.Mock(returncode=0, stderr="")
            result = list(load_repo("https://github.com/dbader/schedule"))
        mock_run.assert_called_once()
        # Der Repo-Name kommt vom Ende der URL, clone_path = tmp_parent / repo_name
        assert result == [fake_tmp / "schedule"]

    def test_url_detection_github_dot_com(self):
        import unittest.mock as mock

        fake_tmp = Path("/tmp/fake_clone2")
        with mock.patch("src.io.repo_loader.subprocess.run") as mock_run, \
             mock.patch("src.io.repo_loader.tempfile.mkdtemp", return_value=str(fake_tmp)):
            mock_run.return_value = mock.Mock(returncode=0, stderr="")
            result = list(load_repo("github.com/dbader/schedule"))
        mock_run.assert_called_once()
        assert result == [fake_tmp / "schedule"]

    def test_clone_failure_raises(self):
        import unittest.mock as mock

        with mock.patch("src.io.repo_loader.subprocess.run") as mock_run, \
             mock.patch("src.io.repo_loader.tempfile.mkdtemp", return_value="/tmp/x"):
            mock_run.return_value = mock.Mock(returncode=128, stderr="not a git repo")
            with pytest.raises(RepoLoadError, match="git clone failed"):
                list(load_repo("https://github.com/nonexistent/repo"))

    def test_atexit_registers_cleanup_for_temp_dir(self):
        import shutil
        import unittest.mock as mock

        fake_tmp = Path("/tmp/fake_atexit_test")
        with mock.patch("src.io.repo_loader.subprocess.run") as mock_run, \
             mock.patch("src.io.repo_loader.tempfile.mkdtemp", return_value=str(fake_tmp)), \
             mock.patch("src.io.repo_loader.atexit.register") as mock_atexit:
            mock_run.return_value = mock.Mock(returncode=0, stderr="")
            list(load_repo("https://github.com/dbader/schedule"))
        mock_atexit.assert_called_once_with(shutil.rmtree, fake_tmp, True)

    @pytest.mark.network
    def test_clone_real_repo(self, tmp_path):
        """Das kleinste der Entwicklungs-Repos flach klonen."""
        results = list(load_repo("https://github.com/dbader/schedule"))
        assert len(results) == 1
        root = results[0]
        assert (root / "schedule").exists() or any(root.rglob("*.py"))


# filters


class TestCollectPythonFiles:
    def _make_tree(self, tmp_path: Path) -> dict[str, Path]:
        """Einen minimalen Verzeichnisbaum wie in einem Repo anlegen."""
        (tmp_path / "mypackage").mkdir()
        (tmp_path / "mypackage" / "__init__.py").write_text("")
        (tmp_path / "mypackage" / "core.py").write_text("class Core: pass\n")
        (tmp_path / "mypackage" / "utils.py").write_text("def helper(): pass\n")

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_core.py").write_text("def test_x(): pass\n")

        (tmp_path / "test_stuff").mkdir()
        (tmp_path / "test_stuff" / "helper.py").write_text("")

        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib.py").write_text("")

        (tmp_path / "setup.py").write_text("")
        (tmp_path / "conftest.py").write_text("")

        return {
            "core": tmp_path / "mypackage" / "core.py",
            "utils": tmp_path / "mypackage" / "utils.py",
            "init": tmp_path / "mypackage" / "__init__.py",
        }

    def test_excludes_test_directory(self, tmp_path):
        keep = self._make_tree(tmp_path)
        filters = _make_filters()
        found = collect_python_files(tmp_path, filters)
        paths = set(found)
        assert tmp_path / "tests" / "test_core.py" not in paths

    def test_excludes_venv_directory(self, tmp_path):
        self._make_tree(tmp_path)
        filters = _make_filters()
        found = collect_python_files(tmp_path, filters)
        assert tmp_path / ".venv" / "lib.py" not in found

    def test_excludes_glob_dir_pattern(self, tmp_path):
        self._make_tree(tmp_path)
        filters = _make_filters()
        found = collect_python_files(tmp_path, filters)
        assert tmp_path / "test_stuff" / "helper.py" not in found

    def test_excludes_test_files(self, tmp_path):
        self._make_tree(tmp_path)
        filters = _make_filters()
        found = collect_python_files(tmp_path, filters)
        names = {f.name for f in found}
        assert "test_core.py" not in names
        assert "conftest.py" not in names
        assert "setup.py" not in names

    def test_keeps_package_files(self, tmp_path):
        keep = self._make_tree(tmp_path)
        filters = _make_filters()
        found = set(collect_python_files(tmp_path, filters))
        assert keep["core"] in found
        assert keep["utils"] in found
        assert keep["init"] in found

    def test_no_filters_returns_all(self, tmp_path):
        self._make_tree(tmp_path)
        no_filters = FiltersConfig(exclude_dirs=(), exclude_files=())
        found = collect_python_files(tmp_path, no_filters)
        assert len(found) == 8  # alle .py-Dateien im Baum

    def test_empty_directory(self, tmp_path):
        filters = _make_filters()
        assert collect_python_files(tmp_path, filters) == []


class TestCollectJavaSourceSets:
    def test_auto_prefers_all_module_main_roots(self, tmp_path):
        main_a = tmp_path / "a/src/main/java/p/A.java"
        main_b = tmp_path / "b/src/main/java/p/B.java"
        generated = tmp_path / "a/src/generated/java/p/A.java"
        android_test = tmp_path / "a/src/androidTest/java/p/ATest.java"
        legacy = tmp_path / "misc/Legacy.java"
        for path in (main_a, main_b, generated, android_test, legacy):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("class X {}")
        found = collect_source_files(
            tmp_path, FiltersConfig((), ()), "java", JavaConfig(source_sets="auto")
        )
        assert found == [main_a, main_b]

    def test_auto_falls_back_for_legacy_layout(self, tmp_path):
        source = tmp_path / "src/p/A.java"
        source.parent.mkdir(parents=True)
        source.write_text("class A {}")
        assert collect_source_files(
            tmp_path, FiltersConfig((), ()), "java", JavaConfig(source_sets="auto")
        ) == [source]

    def test_all_keeps_nonstandard_and_generated_roots(self, tmp_path):
        paths = [
            tmp_path / "src/main/java/p/A.java",
            tmp_path / "src/generated/java/p/A.java",
            tmp_path / "legacy/B.java",
        ]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("class X {}")
        assert collect_source_files(
            tmp_path, FiltersConfig((), ()), "java", JavaConfig(source_sets="all")
        ) == sorted(paths)

    def test_auto_honors_maven_custom_source_directory(self, tmp_path):
        custom = tmp_path / "domain/code/p/A.java"
        ignored = tmp_path / "misc/B.java"
        custom.parent.mkdir(parents=True)
        ignored.parent.mkdir(parents=True)
        custom.write_text("class A {}")
        ignored.write_text("class B {}")
        (tmp_path / "pom.xml").write_text("""\
            <project><build><sourceDirectory>domain/code</sourceDirectory></build></project>
        """)
        assert collect_source_files(
            tmp_path, FiltersConfig((), ()), "java", JavaConfig(source_sets="auto")
        ) == [custom]

    def test_auto_honors_gradle_custom_main_source_directory(self, tmp_path):
        custom = tmp_path / "src/core/p/A.java"
        ignored = tmp_path / "src/test/java/p/ATest.java"
        custom.parent.mkdir(parents=True)
        ignored.parent.mkdir(parents=True)
        custom.write_text("class A {}")
        ignored.write_text("class ATest {}")
        (tmp_path / "build.gradle").write_text("""\
            sourceSets {
                main { java { srcDirs = ['src/core'] } }
                test { java { srcDirs = ['src/test/java'] } }
            }
        """)
        assert collect_source_files(
            tmp_path, FiltersConfig((), ()), "java", JavaConfig(source_sets="auto")
        ) == [custom]


# preflight


class TestRunPreflight:
    def _make_py_files(self, tmp_path: Path, sources: list[str]) -> list[Path]:
        files = []
        for i, src in enumerate(sources):
            f = tmp_path / f"mod_{i}.py"
            f.write_text(src)
            files.append(f)
        return files

    def test_happy_path(self, tmp_path):
        sources = [
            "class A: pass\nclass B: pass\n",
            "def func(): pass\n",
        ]
        files = self._make_py_files(tmp_path, sources)
        caps = _make_caps()
        result = run_preflight(tmp_path, files, caps)
        assert isinstance(result, PreflightResult)
        assert result.root == tmp_path
        assert result.source_files == files
        assert result.class_count == 2
        assert result.loc == 3  # 2 Klassen + 1 Funktion = 3 Quellzeilen

    def test_empty_files_list_raises(self, tmp_path):
        with pytest.raises(PreflightError, match="No Python files found"):
            run_preflight(tmp_path, [], _make_caps())

    def test_over_loc_cap_raises(self, tmp_path):
        # 3 Zeilen pro Datei, Grenze bei 2
        files = self._make_py_files(tmp_path, ["a\nb\nc\n"] * 3)
        caps = _make_caps(max_loc=2)
        with pytest.raises(PreflightError, match="LOC count"):
            run_preflight(tmp_path, files, caps)

    def test_over_class_cap_raises(self, tmp_path):
        sources = ["class A: pass\nclass B: pass\n"] * 5
        files = self._make_py_files(tmp_path, sources)
        caps = _make_caps(max_classes=5)
        with pytest.raises(PreflightError, match="Class count"):
            run_preflight(tmp_path, files, caps)

    def test_syntax_error_file_counted_as_zero_classes(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def (broken syntax:\n")
        good = tmp_path / "good.py"
        good.write_text("class X: pass\n")
        caps = _make_caps()
        result = run_preflight(tmp_path, [bad, good], caps)
        assert result.class_count == 1

    def test_exactly_at_caps_is_ok(self, tmp_path):
        # Genau auf der Grenze darf nichts geworfen werden.
        sources = ["class A: pass\n"] * 3  # 3 Klassen, 3 LOC
        files = self._make_py_files(tmp_path, sources)
        caps = _make_caps(max_loc=3, max_classes=3)
        result = run_preflight(tmp_path, files, caps)
        assert result.class_count == 3
        assert result.loc == 3

    def test_nested_classes_counted(self, tmp_path):
        src = textwrap.dedent("""\
            class Outer:
                class Inner:
                    pass
        """)
        files = self._make_py_files(tmp_path, [src])
        result = run_preflight(tmp_path, files, _make_caps())
        assert result.class_count == 2
