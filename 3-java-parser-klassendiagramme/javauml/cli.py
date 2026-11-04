"""Kommandozeile: ``javauml REPO [REPO ...] -o AUSGABE``."""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from javauml.api import MEMBER_PROFILES, MODES, Options, extract
from javauml.java.ts_pass import JavaParserUnavailable
from javauml.render import RenderError, find_plantuml, render
from javauml.repo import RepoError, open_repo, repo_name
from javauml.sources import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_FILES

FORMATS = ("json", "puml", "png", "svg")
BASENAME = "klassendiagramm"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="javauml",
        description="Klassendiagramme (PlantUML und JSON) aus dem Quelltext von Java-Repos. "
                    "Liest nur Quelltext, braucht keinen Build.",
    )
    p.add_argument("repos", nargs="+", metavar="REPO",
                   help="lokaler Pfad oder Git-URL, mehrere möglich")
    p.add_argument("-o", "--output", type=Path, default=Path("uml-ausgabe"),
                   help="Ausgabeordner, pro Repo ein Unterordner (Standard: uml-ausgabe)")
    p.add_argument("-f", "--format", default="json,puml",
                   help=f"kommagetrennt aus {', '.join(FORMATS)} (Standard: json,puml)")
    p.add_argument("--name", help="Name des Repos in der Ausgabe (genau ein Repo), "
                                  "sonst der Ordner- bzw. Repo-Name")
    p.add_argument("--stdout", choices=("puml", "json"),
                   help="Ergebnis nur ausgeben statt Dateien zu schreiben (genau ein Repo)")
    p.add_argument("-m", "--mode", choices=MODES, default="literal",
                   help="literal: Felder, extends, implements. intellij: wie IntelliJ IDEA, "
                        "mit Abhängigkeiten aus Methodenrümpfen (Standard: literal)")
    p.add_argument("--members", choices=MEMBER_PROFILES, default="summary",
                   help="Detailgrad von Attributen und Methoden im Modus literal (Standard: summary)")

    g = p.add_argument_group("Dateiauswahl")
    g.add_argument("--source-sets", choices=("auto", "all"), default="auto",
                   help="auto bevorzugt src/main/java bzw. die Angaben aus pom.xml/build.gradle")
    g.add_argument("--include-generated", action="store_true", help="generierte Quellen mitlesen")
    g.add_argument("--exclude-dir", action="append", default=[], metavar="MUSTER",
                   help="weiteres Verzeichnismuster ausschließen (mehrfach möglich)")
    g.add_argument("--exclude-file", action="append", default=[], metavar="MUSTER",
                   help="weiteres Dateimuster ausschließen (mehrfach möglich)")
    g.add_argument("--no-default-excludes", action="store_true",
                   help="Standardausschlüsse (test, target, *Test.java, ...) abschalten")

    g = p.add_argument_group("Modus literal")
    g.add_argument("--no-external-supertypes", action="store_true",
                   help="externe Obertypen wie JFrame nicht als Knoten zeigen")
    g.add_argument("--method-dependencies", action="store_true",
                   help="Abhängigkeiten aus Methodensignaturen")
    g.add_argument("--javac", action="store_true",
                   help="zusätzlich den JDK-Compiler zur Typauflösung fragen")
    g.add_argument("--classpath", action="append", default=[], metavar="PFAD",
                   help="JAR oder Verzeichnis für --javac (mehrfach möglich)")

    g = p.add_argument_group("Modus intellij")
    g.add_argument("--classes", type=Path, metavar="DATEI",
                   help="Klassen im Diagramm, ein voll qualifizierter Name pro Zeile "
                        "(ohne Angabe alle Klassen)")
    g.add_argument("--ide-no-jdk", action="store_true",
                   help="IntelliJ ohne eingerichtetes JDK nachbilden")
    g.add_argument("--ide-no-same-package", action="store_true",
                   help="IntelliJ mit falschem Source-Root nachbilden")

    g = p.add_argument_group("Git und Rendern")
    g.add_argument("--ref", help="Branch oder Tag beim Klonen")
    g.add_argument("--keep-clone", action="store_true",
                   help="Klon unter AUSGABE/<repo>/quelle behalten")
    g.add_argument("--plantuml", type=Path, metavar="JAR",
                   help="PlantUML-JAR für png/svg (sonst PLANTUML_JAR oder plantuml im PATH)")
    p.add_argument("-v", "--verbose", action="store_true", help="Fortschritt und Hinweise ausgeben")
    return p


def _read_classes(path: Path) -> tuple[str, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(s for line in lines if (s := line.strip()) and not s.startswith("#"))


def options_from_args(args: argparse.Namespace) -> Options:
    exclude_dirs = () if args.no_default_excludes else DEFAULT_EXCLUDE_DIRS
    exclude_files = () if args.no_default_excludes else DEFAULT_EXCLUDE_FILES
    return Options(
        mode=args.mode,
        member_profile=args.members,
        source_sets=args.source_sets,
        include_generated=args.include_generated,
        exclude_dirs=exclude_dirs + tuple(args.exclude_dir),
        exclude_files=exclude_files + tuple(args.exclude_file),
        external_supertypes=not args.no_external_supertypes,
        method_dependencies=args.method_dependencies,
        javac=args.javac,
        classpath=tuple(args.classpath),
        diagram_classes=_read_classes(args.classes) if args.classes else (),
        ide_jdk=not args.ide_no_jdk,
        ide_same_package=not args.ide_no_same_package,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        print(f"Unbekanntes Format: {', '.join(unknown)}", file=sys.stderr)
        return 2
    if (args.stdout or args.name) and len(args.repos) != 1:
        print("--stdout und --name gehen nur mit genau einem Repo", file=sys.stderr)
        return 2
    try:
        options = options_from_args(args)
        options.check()
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    plantuml = None
    if not args.stdout and {"png", "svg"} & set(formats):
        try:
            plantuml = find_plantuml(args.plantuml)
        except RenderError as exc:
            print(exc, file=sys.stderr)
            return 2

    names = [args.name] if args.name else _unique_names(args.repos)
    failed = 0
    for source, name in zip(args.repos, names):
        keep = args.output / name / "quelle" if args.keep_clone else None
        try:
            with open_repo(source, args.ref, keep) as root:
                result = extract(root, options, repo=name)
                if args.stdout:
                    sys.stdout.write(result.plantuml() if args.stdout == "puml" else result.json())
                    continue
                written = _write(result, args.output / name, formats, plantuml)
        except (RepoError, RenderError, JavaParserUnavailable, OSError,
                subprocess.TimeoutExpired) as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            failed += 1
            continue
        g = result.graph
        print(f"{name}: {len(result.files)} Dateien, {len(g.nodes)} Klassen, {len(g.edges)} Kanten, "
              f"{len(result.diagnostics)} Hinweise -> {', '.join(str(w) for w in written)}")
    return 1 if failed else 0


def _unique_names(sources: list[str]) -> list[str]:
    names: list[str] = []
    for source in sources:
        base = repo_name(source)
        name, i = base, 2
        while name in names:
            name, i = f"{base}-{i}", i + 1
        names.append(name)
    return names


def _write(result, out_dir: Path, formats: list[str], plantuml: list[str] | None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    puml = out_dir / f"{BASENAME}.puml"
    if "puml" in formats or "png" in formats or "svg" in formats:
        puml.write_text(result.plantuml(), encoding="utf-8")
        if "puml" in formats:
            written.append(puml)
    if "json" in formats:
        path = out_dir / f"{BASENAME}.json"
        path.write_text(result.json(), encoding="utf-8")
        written.append(path)
    diagnostics = out_dir / f"{BASENAME}.diagnostics.json"
    if result.diagnostics:
        diagnostics.write_text(result.diagnostics_json(), encoding="utf-8")
        written.append(diagnostics)
    elif diagnostics.exists():
        diagnostics.unlink()
    for fmt in ("png", "svg"):
        if fmt in formats:
            written.append(render(puml, fmt, plantuml))
    if "puml" not in formats and puml.exists():
        puml.unlink()
    return written


if __name__ == "__main__":
    raise SystemExit(main())
