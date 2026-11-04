#!/usr/bin/env bash
# Kurzbefehle für den Container. Alles, was kein Kurzbefehl ist, wird direkt
# ausgeführt (z. B. "bash" oder "python ...").
set -euo pipefail

P1=/app/1-llm-pipeline-abstrakte-klassendiagramme
P2=/app/2-java-extraktoren-benchmark-forschungsdaten
P3=/app/3-java-parser-klassendiagramme

cmd="${1:-hilfe}"
[ $# -gt 0 ] && shift

case "$cmd" in
  javauml)
    # Ausgabe landet im eingehängten Ordner /ausgabe
    cd /ausgabe
    exec javauml "$@"
    ;;
  pipeline)
    cd "$P1"
    exec python -m src "$@"
    ;;
  tests)
    echo "== Ordner 3: javauml"
    (cd "$P3" && python -m pytest -q)
    echo "== Ordner 1: Pipeline (ohne Netz)"
    (cd "$P1" && python -m pytest -q -m 'not network')
    echo "== Ordner 2: Benchmark-Skripte"
    (cd "$P2" && python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py)
    ;;
  restore)
    cd "$P2"
    exec python skripte/restore.py "$@"
    ;;
  lindholmen)
    cd "$P2"
    exec env PYTHONPATH="$P1" python skripte/benchmark.py "$@"
    ;;
  hebig)
    cd "$P2"
    exec env PYTHONPATH="$P1" python skripte/curated_hebig_benchmark.py "$@"
    ;;
  intellij)
    cd "$P2"
    exec env PYTHONPATH="$P1" python skripte/intellij_abgleich.py "$@"
    ;;
  report)
    cd "$P2"
    exec python skripte/report.py "$@"
    ;;
  hilfe|help|-h|--help)
    cat <<'EOF'
Kurzbefehle:
  javauml <repo> [optionen]   Klassendiagramm aus einem Java-Repo (Ordner 3), Ausgabe in /ausgabe
  pipeline <repo> [optionen]  LLM-Pipeline (Ordner 1), Läufe in runs/
  tests                       alle Tests der drei Ordner
  restore                     die 30 Lindholmen-Projekte herunterladen und prüfen
  lindholmen [optionen]       Messung auf Lindholmen (skripte/benchmark.py)
  hebig [optionen]            Messung auf Zhang/Hebig (skripte/curated_hebig_benchmark.py)
  intellij [--render]         Abgleich mit den IntelliJ-Diagrammen
  report                      Tabellen aus den gespeicherten Messungen neu erzeugen
  bash                        Shell im Container
EOF
    ;;
  *)
    exec "$cmd" "$@"
    ;;
esac
