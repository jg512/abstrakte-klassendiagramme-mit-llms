**Deutsch** · [English](INSTALLATION.en.md)

# Installation und Wiederholung der Messungen

Hier steht, wie man das Projekt auf einem frischen Rechner zum Laufen bringt
und die Messungen aus Ordner 2 wiederholt. Zum Lesen und Verstehen des Projekts
braucht man das nicht, das [Haupt-README](README.md) und die verlinkten
Dokumente reichen dafür.

Alle Befehle unten tippt man in ein Terminal (unter Windows PowerShell). Zeilen,
die mit `#` beginnen, sind Kommentare und werden nicht ausgeführt. Es gibt zwei
Wege:

- Docker: Docker ist ein Programm, das eine fertig eingerichtete Umgebung als
  Paket (ein Image) liefert. Python, das JDK und die Werkzeuge stecken darin,
  man muss sie nicht einzeln installieren. Das ist der einfachste Weg und unter
  Windows der einzige, auf dem auch Ordner 2 ohne weitere Einrichtung läuft.
- Direkt installieren: sinnvoll, wenn man am Code arbeiten will. Ordner 1
  und 3 sind für Linux und Windows geschrieben, unter Windows aber nicht
  ausprobiert (siehe unten). Die Messskripte in Ordner 2 setzen ihre
  Zeitlimits über POSIX-Signale, eine Funktion von Unix-Systemen, und laufen
  deshalb nur unter Linux, macOS oder in WSL (einem Linux innerhalb von
  Windows).

Beides ist unter Ubuntu getestet. Unter Windows ist Docker der sichere Weg, die
direkte Installation dort ist nicht ausprobiert.

## Was nicht im Repo liegt

- Die Datensätze: der Quelltext der 30 Lindholmen-Projekte (lädt ein Skript
  nach) und das Replikationspaket von Zhang/Hebig (etwa 330 MB, von Hand
  herunterladen).
- Gebaute Fremdwerkzeuge wie PlantUML und java2plantuml. Docker baut sie selbst,
  bei der direkten Installation steht unten, wie es geht.
- Die Ergebnisse früherer Läufe (`1-…/runs/`, `2-…/ergebnisse/`). Die Zahlen
  daraus stehen in den READMEs und in `2-…/doku/`.

Im Repo liegen dagegen die eigenen Metadaten (Angaben über die Daten), die man
zum Wiederholen braucht:
die festgelegte Projektauswahl mit Prüfsummen (`daten/lindholmen/manifest.json`),
die Referenzgraphen, die Abschrift der Zhang/Hebig-Diagramme
(`daten/zhang-hebig/reference.json`) und die Angaben zu den IntelliJ-Diagrammen
(`daten/intellij/`).


## Weg 1: Docker

### Einrichten

Unter Windows und macOS braucht man Docker Desktop. Unter Windows läuft es über
WSL2, das richtet der Installer mit ein. Unter Linux reichen Docker und das
Compose-Plugin, unter Ubuntu zum Beispiel:

```bash
sudo apt install docker.io docker-compose-v2
sudo usermod -aG docker $USER     # danach einmal ab- und wieder anmelden
```

Dann das Repo holen und das Image bauen:

```bash
git clone https://github.com/jg512/abstrakte-klassendiagramme-mit-llms.git
cd abstrakte-klassendiagramme-mit-llms
docker compose build
```

Der erste Build dauert einige Minuten. Er lädt das JDK-Image, Python 3.13 und
die Python-Pakete in denselben Versionen wie bei den Messungen, außerdem
PlantUML, und baut java2plantuml.

Ein laufendes Image heißt Container. Alle Befehle haben danach die Form

```bash
docker compose run --rm app <befehl> [argumente]
```

`docker compose run --rm app` ohne Befehl zeigt die Liste der Kurzbefehle, mit
`bash` bekommt man ein Terminal (eine Shell) im Container.

Was der Container schreibt oder herunterlädt, landet auf dem eigenen Rechner im
Ordner `docker-daten/`:

| Ordner | Inhalt |
| :--- | :--- |
| `docker-daten/ausgabe/` | Diagramme von `javauml` |
| `docker-daten/repos/` | eigene Java-Repos, die man auswerten will, hier hineinkopieren |
| `docker-daten/runs/` | Läufe der LLM-Pipeline |
| `docker-daten/lindholmen-corpus/` | die heruntergeladenen Lindholmen-Projekte |
| `docker-daten/zhang-hebig/` | das Paket von Zhang/Hebig, von Hand entpackt |
| `docker-daten/ergebnisse/` | Messergebnisse und gerenderte Diagramme aus Ordner 2 |

Unter Linux gehören diese Dateien dem Administrator (root), weil der Container
als root läuft. Mit `sudo chown -R $USER docker-daten` holt man sie sich zurück.

Zuerst die Tests (kleine Prüfprogramme, die kontrollieren, ob alles wie
erwartet arbeitet), dann weiß man, dass das Image in Ordnung ist:

```bash
docker compose run --rm app tests
```

### Ordner 3: Klassendiagramm aus einem Java-Repo

```bash
docker compose run --rm app javauml https://github.com/jainebri/Super-Simple-Stocks -f json,puml,svg
```

Das Ergebnis liegt dann unter
`docker-daten/ausgabe/uml-ausgabe/Super-Simple-Stocks/`. Ein Repo, das schon auf
dem Rechner liegt, kopiert man nach `docker-daten/repos/` und gibt es als
`/repos/<name>` an. Die Optionen stehen im
[README von Ordner 3](3-java-parser-klassendiagramme/README.md).

### Ordner 1: LLM-Pipeline

Ein Trockenlauf ohne LLM kostet nichts und zeigt, ob Parser, Driver und Ausgabe
zusammenspielen:

```bash
docker compose run --rm app pipeline https://github.com/dbader/schedule --method all --dry-run --no-cleanup
```

Für einen echten Lauf muss der API-Schlüssel auf dem Rechner gesetzt sein. Das
ist das Zugangspasswort, das man beim Anbieter des Modells bekommt (hier
DeepSeek). Die Läufe kosten dann echtes Geld, bei `schedule` wenige Cent.
Compose reicht den Schlüssel an den Container weiter.

```bash
# Linux / macOS
export DEEPSEEK_API_KEY=...
# Windows (PowerShell)
$env:DEEPSEEK_API_KEY = "..."

docker compose run --rm app pipeline https://github.com/dbader/schedule --config configs/deepseek_exp.yaml --method all --target-nodes open
```

Ohne `--config` nimmt die Pipeline Gemini und braucht dann `GEMINI_API_KEY`. Ein
lokales Modell läuft kostenlos auf dem eigenen Rechner. Dafür muss Ollama auf
dem Rechner selbst laufen, nicht im Container (`ollama pull qwen2.5:14b`).
Aufgerufen wird es mit `--config configs/ollama_docker.yaml`. Was die Optionen
bedeuten, steht im [README von Ordner
1](1-llm-pipeline-abstrakte-klassendiagramme/README.md).

### Ordner 2: Messungen wiederholen

1. Lindholmen-Projekte laden. Das Skript lädt die Archive der festgelegten
Commits von GitHub und prüft jede Datei gegen ihre Prüfsumme (eine Art
Fingerabdruck, an dem man sieht, dass die Datei unverändert ist):

```bash
docker compose run --rm app restore
```

2. Paket von Zhang/Hebig holen. Das geht nur von Hand, über
<https://osf.io/p4jdr/?view_only=34b153d3b7704f4a84befd661dc9c6a1>. Aus dem
Paket werden zwei Ordner gebraucht:

- `Version(s) of Source Code Used/` nach
  `docker-daten/zhang-hebig/Version(s) of Source Code Used/`
- die Modelle nach `docker-daten/zhang-hebig/models/`, wobei die
  IntelliJ-Diagramme aus `reverse-models.zip` nach
  `docker-daten/zhang-hebig/models/reverse/` ausgepackt werden

Für die Lindholmen-Messung ist dieser Schritt nicht nötig.

3. Messen:

```bash
docker compose run --rm app lindholmen --label rerun --limit 30
docker compose run --rm app hebig --label curated-rerun
docker compose run --rm app intellij --render
docker compose run --rm app report
```

Die Ergebnisse stehen danach in `docker-daten/ergebnisse/messungen/<label>/`.
Zum Vergleich dienen die Tabellen in
[`ergebnisse-lindholmen.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-lindholmen.md),
[`ergebnisse-zhang-hebig.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-zhang-hebig.md)
und
[`intellij-nachbildung.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.md).

Die Messung mit allen sieben Werkzeugen (`curated_tools_benchmark.py`) ist im
Image nicht vorbereitet. Dafür braucht es Maven (ein Werkzeug zum Bauen von
Java-Projekten) und vier weitere Werkzeuge, die man nach
[`werkzeuge.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/werkzeuge.md)
selbst baut.


## Weg 2: Direkt installieren

### Einmal pro Rechner

Linux (Ubuntu):

```bash
sudo apt update
sudo apt install -y git curl openjdk-25-jdk
curl -LsSf https://astral.sh/uv/install.sh | sh      # danach Terminal neu öffnen
```

Windows (PowerShell):

```powershell
winget install Git.Git Microsoft.OpenJDK.25 astral-sh.uv
```

Das installiert `git` (lädt Repos herunter), `curl` (lädt Dateien herunter),
das JDK (Java) und `uv` (richtet Python-Umgebungen ein). Gemessen wurde mit
OpenJDK 25. Ein JDK 21 sollte auch reichen, ist aber nicht geprüft. Python muss
man nicht selbst installieren, `uv` holt Python 3.13 automatisch.

Dann das Repo holen:

```bash
git clone https://github.com/jg512/abstrakte-klassendiagramme-mit-llms.git
cd abstrakte-klassendiagramme-mit-llms
```

Für PNG und SVG braucht man noch die PlantUML-JAR, zum Beispiel unter
`~/werkzeuge/`:

```bash
mkdir -p ~/werkzeuge
curl -fL -o ~/werkzeuge/plantuml-1.2025.4.jar \
  https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml/1.2025.4/plantuml-1.2025.4.jar
```

Jeder Ordner bekommt unten eine eigene Python-Umgebung `.venv`, einen
Unterordner, in dem die benötigten Python-Pakete liegen, ohne den Rest des
Rechners zu berühren. Unter Windows steht in allen Befehlen unten
`.venv\Scripts\` statt `.venv/bin/`, und Umgebungsvariablen setzt man mit
`$env:NAME = "wert"` statt mit `export`.

### Ordner 3: javauml

```bash
cd 3-java-parser-klassendiagramme
uv venv --python 3.13
uv pip install -e '.[dev]'
.venv/bin/python -m pytest

export PLANTUML_JAR=~/werkzeuge/plantuml-1.2025.4.jar
.venv/bin/javauml https://github.com/jainebri/Super-Simple-Stocks -f json,puml,svg
```

### Ordner 1: LLM-Pipeline

```bash
cd 1-llm-pipeline-abstrakte-klassendiagramme
uv venv --python 3.13
uv pip install -e '.[java,dev]'
.venv/bin/python -m pytest -q -m 'not network'

# Trockenlauf ohne LLM
.venv/bin/python -m src https://github.com/dbader/schedule --method all --dry-run --no-cleanup

# echter Lauf
export DEEPSEEK_API_KEY=...
.venv/bin/python -m src https://github.com/dbader/schedule --config configs/deepseek_exp.yaml --method all --target-nodes open
```

Mit einem lokalen Ollama heißt die Konfiguration `configs/ollama.yaml`.

### Ordner 2: Messungen (Linux, macOS oder WSL)

Die Umgebung enthält auch Ordner 1, genau wie bei den ursprünglichen Messungen:

```bash
cd 2-java-extraktoren-benchmark-forschungsdaten
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r werkzeuge/requirements.lock.txt
uv pip install --python .venv/bin/python --no-deps -e ../1-llm-pipeline-abstrakte-klassendiagramme
.venv/bin/python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py
```

Für die Messung mit drei Extraktoren braucht man zusätzlich java2plantuml (das
Werkzeug, das verglichen wird) und PlantUML (zum Zeichnen der Bilder):

```bash
cp ~/werkzeuge/plantuml-1.2025.4.jar werkzeuge/
git clone https://github.com/mirajp1/java2plantuml.git werkzeuge/java2plantuml
git -C werkzeuge/java2plantuml checkout cadd0f0a06e87825472227381a37210763ae137c
curl -fL -o werkzeuge/javaparser-core-3.4.0.jar \
  https://repo1.maven.org/maven2/com/github/javaparser/javaparser-core/3.4.0/javaparser-core-3.4.0.jar
mkdir -p werkzeuge/java2plantuml/classes
J=werkzeuge/java2plantuml/src/main/java
javac -cp werkzeuge/javaparser-core-3.4.0.jar -d werkzeuge/java2plantuml/classes \
  $J/*.java $J/source/*.java $J/translate/*.java $J/visitors/*.java
```

Daten: `restore.py` lädt die Lindholmen-Projekte. Das Paket von Zhang/Hebig
entpackt man wie oben beschrieben, nur eben nach `daten/zhang-hebig/` statt nach
`docker-daten/zhang-hebig/`.

```bash
.venv/bin/python skripte/restore.py
.venv/bin/python skripte/benchmark.py --label rerun --limit 30
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/intellij_abgleich.py --render
.venv/bin/python skripte/report.py
```

Mehr Einzelheiten, auch zur Messung mit sieben Werkzeugen, stehen in
[`reproduzieren.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/reproduzieren.md)
und
[`werkzeuge.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/werkzeuge.md).

Die Projektauswahl selbst (`discover.py`, `acquire.py`, `benchmark.py --prepare`)
sollte man nicht neu laufen lassen. Die Repos haben sich seit der Auswahl
verändert, es käme eine andere Menge heraus. Für eine Wiederholung ist
`manifest.json` mit `restore.py` gedacht.


## Wenn etwas hakt

- Meldet `restore.py` `Modified local input`, wurde eine Datei im Korpus
  verändert. Den Ordner des Projekts unter `corpus/` löschen und `restore.py`
  noch einmal starten.
- Fehlen PNG oder SVG, hat `javauml` PlantUML nicht gefunden. Dann
  `PLANTUML_JAR` setzen oder `--plantuml <jar>` angeben. Java muss im `PATH`
  sein.
- Finden `hebig` oder `intellij` keine Dateien, stimmen meist die Ordnernamen
  aus dem Zhang/Hebig-Paket nicht. `Version(s) of Source Code Used` muss genau so
  heißen, mit Klammern und Leerzeichen.
- Bricht der Container unter Windows mit `bad interpreter` oder `start: not
  found` ab, wurde das Repo mit Windows-Zeilenenden ausgecheckt. Neu klonen
  hilft, `.gitattributes` sorgt dann für die richtigen Zeilenenden.
