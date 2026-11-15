[Deutsch](INSTALLATION.md) · **English**

# Installing the project and repeating the measurements

This page explains how to get the project running on a fresh machine and how
to repeat the measurements from folder 2. You do not need any of this just to
read and understand the project; the [main README](README.en.md) and the
documents it links to are enough for that.

You type all the commands below into a terminal (PowerShell on Windows). Lines
starting with `#` are comments and are not run. There are two ways to go:

- Docker: Docker is a program that delivers a ready-made environment as a
  package (an image). Python, the JDK and all the tools are already inside, so
  you do not have to install them one by one. This is the easiest route, and on
  Windows it is the only one on which folder 2 runs without further setup.
- Installing directly: worth it if you want to work on the code. Folders 1 and
  3 are written for Linux and Windows, but have not been tried on Windows (see
  below). The measurement scripts in folder 2 enforce their
  time limits with POSIX signals, a feature of Unix systems, so they only run
  on Linux, macOS or WSL (a Linux that runs inside Windows).

Both routes have been tested on Ubuntu. On Windows, Docker is the safe choice;
the direct installation has not been tried there.

## What is not in the repository

- The datasets: the source code of the 30 Lindholmen projects (a script
  downloads it) and the Zhang/Hebig replication package (about 330 MB, which
  you download by hand).
- Built third-party tools such as PlantUML and java2plantuml. Docker builds
  them itself; for the direct installation the steps are below.
- The results of earlier runs (`1-…/runs/`, `2-…/ergebnisse/`). Their numbers
  are in the READMEs and in `2-…/doku/`.

What the repository does contain is our own metadata (information about the
data) that you need to repeat the measurements: the fixed selection of
projects with checksums (`daten/lindholmen/manifest.json`), the reference
graphs, the transcription of the Zhang/Hebig diagrams
(`daten/zhang-hebig/reference.json`) and the details of the IntelliJ diagrams
(`daten/intellij/`).


## Route 1: Docker

### Setting up

On Windows and macOS you need Docker Desktop. On Windows it runs on top of
WSL2, which the installer sets up for you. On Linux, Docker and the Compose
plugin are enough; on Ubuntu, for example:

```bash
sudo apt install docker.io docker-compose-v2
sudo usermod -aG docker $USER     # then log out and back in once
```

Then fetch the repository and build the image:

```bash
git clone https://github.com/jg512/abstrakte-klassendiagramme-mit-llms.git
cd abstrakte-klassendiagramme-mit-llms
docker compose build
```

The first build takes a few minutes. It downloads the JDK image, Python 3.13
and the Python packages in the same versions that were used for the
measurements, plus PlantUML, and it builds java2plantuml.

A running image is called a container. From then on every command looks like
this:

```bash
docker compose run --rm app <command> [arguments]
```

`docker compose run --rm app` on its own lists the shortcut commands, and with
`bash` you get a terminal (a shell) inside the container.

Anything the container writes or downloads ends up on your machine in the
`docker-daten/` folder:

| Folder | Contents |
| :--- | :--- |
| `docker-daten/ausgabe/` | diagrams from `javauml` |
| `docker-daten/repos/` | your own Java repos that you want to analyse; copy them in here |
| `docker-daten/runs/` | runs of the LLM pipeline |
| `docker-daten/lindholmen-corpus/` | the downloaded Lindholmen projects |
| `docker-daten/zhang-hebig/` | the Zhang/Hebig package, unpacked by hand |
| `docker-daten/ergebnisse/` | measurement results and rendered diagrams from folder 2 |

On Linux these files belong to the administrator (root), because the container
runs as root. `sudo chown -R $USER docker-daten` gives them back to you.

Run the tests first (small checking programs that confirm everything behaves
as expected); then you know the image is fine:

```bash
docker compose run --rm app tests
```

### Folder 3: a class diagram from a Java repo

```bash
docker compose run --rm app javauml https://github.com/jainebri/Super-Simple-Stocks -f json,puml,svg
```

The result then sits in
`docker-daten/ausgabe/uml-ausgabe/Super-Simple-Stocks/`. To use a repo that is
already on your machine, copy it into `docker-daten/repos/` and pass it as
`/repos/<name>`. The options are described in the
[folder 3 README](3-java-parser-klassendiagramme/README.en.md).

### Folder 1: the LLM pipeline

A dry run without an LLM costs nothing and shows whether the parser, the
driver and the output fit together:

```bash
docker compose run --rm app pipeline https://github.com/dbader/schedule --method all --dry-run --no-cleanup
```

For a real run the API key has to be set on your machine. That is the access
password you get from the model provider (DeepSeek here). Such runs cost real
money, a few cents for `schedule`. Compose passes the key on to the container.

```bash
# Linux / macOS
export DEEPSEEK_API_KEY=...
# Windows (PowerShell)
$env:DEEPSEEK_API_KEY = "..."

docker compose run --rm app pipeline https://github.com/dbader/schedule --config configs/deepseek_exp.yaml --method all --target-nodes open
```

Without `--config` the pipeline uses Gemini and then needs `GEMINI_API_KEY`. A
local model runs for free on your own machine. For that, Ollama has to run on
the machine itself, not inside the container (`ollama pull qwen2.5:14b`). You
call it with `--config configs/ollama_docker.yaml`. What the options mean is
explained in the [folder 1
README](1-llm-pipeline-abstrakte-klassendiagramme/README.en.md).

### Folder 2: repeating the measurements

1. Download the Lindholmen projects. The script fetches the archives of the
fixed commits from GitHub and checks every file against its checksum (a kind
of fingerprint that shows the file has not changed):

```bash
docker compose run --rm app restore
```

2. Get the Zhang/Hebig package. This can only be done by hand, via
<https://osf.io/p4jdr/?view_only=34b153d3b7704f4a84befd661dc9c6a1>. You need
two folders from the package:

- `Version(s) of Source Code Used/` goes to
  `docker-daten/zhang-hebig/Version(s) of Source Code Used/`
- the models go to `docker-daten/zhang-hebig/models/`, with the IntelliJ
  diagrams from `reverse-models.zip` unpacked into
  `docker-daten/zhang-hebig/models/reverse/`

The Lindholmen measurement does not need this step.

3. Measure:

```bash
docker compose run --rm app lindholmen --label rerun --limit 30
docker compose run --rm app hebig --label curated-rerun
docker compose run --rm app intellij --render
docker compose run --rm app report
```

The results then sit in `docker-daten/ergebnisse/messungen/<label>/`. To
compare, use the tables in
[`ergebnisse-lindholmen.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-lindholmen.en.md),
[`ergebnisse-zhang-hebig.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/ergebnisse-zhang-hebig.en.md)
and
[`intellij-nachbildung.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/intellij-nachbildung.en.md).

The measurement with all seven tools (`curated_tools_benchmark.py`) is not set
up in the image. It needs Maven (a tool for building Java projects) and four
more tools that you build yourself following
[`werkzeuge.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/werkzeuge.en.md).


## Route 2: installing directly

### Once per machine

Linux (Ubuntu):

```bash
sudo apt update
sudo apt install -y git curl openjdk-25-jdk
curl -LsSf https://astral.sh/uv/install.sh | sh      # then open a new terminal
```

Windows (PowerShell):

```powershell
winget install Git.Git Microsoft.OpenJDK.25 astral-sh.uv
```

This installs `git` (downloads repos), `curl` (downloads files), the JDK (Java)
and `uv` (sets up Python environments). The measurements were made with version
25 of OpenJDK. A JDK 21 should do as well but has not been checked. You do not
need to install Python yourself; `uv` fetches Python 3.13 automatically.

Then fetch the repository:

```bash
git clone https://github.com/jg512/abstrakte-klassendiagramme-mit-llms.git
cd abstrakte-klassendiagramme-mit-llms
```

For PNG and SVG output you also need the PlantUML JAR, for example in
`~/werkzeuge/`:

```bash
mkdir -p ~/werkzeuge
curl -fL -o ~/werkzeuge/plantuml-1.2025.4.jar \
  https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml/1.2025.4/plantuml-1.2025.4.jar
```

Each folder below gets its own Python environment `.venv`, a subfolder that
holds the Python packages it needs without touching the rest of the machine.
On Windows, every command below uses `.venv\Scripts\` instead of `.venv/bin/`,
and you set environment variables with `$env:NAME = "value"` instead of
`export`.

### Folder 3: javauml

```bash
cd 3-java-parser-klassendiagramme
uv venv --python 3.13
uv pip install -e '.[dev]'
.venv/bin/python -m pytest

export PLANTUML_JAR=~/werkzeuge/plantuml-1.2025.4.jar
.venv/bin/javauml https://github.com/jainebri/Super-Simple-Stocks -f json,puml,svg
```

### Folder 1: the LLM pipeline

```bash
cd 1-llm-pipeline-abstrakte-klassendiagramme
uv venv --python 3.13
uv pip install -e '.[java,dev]'
.venv/bin/python -m pytest -q -m 'not network'

# dry run without an LLM
.venv/bin/python -m src https://github.com/dbader/schedule --method all --dry-run --no-cleanup

# real run
export DEEPSEEK_API_KEY=...
.venv/bin/python -m src https://github.com/dbader/schedule --config configs/deepseek_exp.yaml --method all --target-nodes open
```

With a local Ollama the configuration is `configs/ollama.yaml`.

### Folder 2: measurements (Linux, macOS or WSL)

The environment includes folder 1 as well, exactly as in the original
measurements:

```bash
cd 2-java-extraktoren-benchmark-forschungsdaten
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r werkzeuge/requirements.lock.txt
uv pip install --python .venv/bin/python --no-deps -e ../1-llm-pipeline-abstrakte-klassendiagramme
.venv/bin/python -m pytest -q skripte/test_benchmark.py skripte/test_curated_hebig.py
```

The measurement with three extractors also needs java2plantuml (the tool being
compared) and PlantUML (for drawing the pictures):

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

Data: `restore.py` downloads the Lindholmen projects. Unpack the Zhang/Hebig
package as described above, only into `daten/zhang-hebig/` instead of
`docker-daten/zhang-hebig/`.

```bash
.venv/bin/python skripte/restore.py
.venv/bin/python skripte/benchmark.py --label rerun --limit 30
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun
PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/intellij_abgleich.py --render
.venv/bin/python skripte/report.py
```

More detail, including the measurement with seven tools, is in
[`reproduzieren.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/reproduzieren.en.md)
and
[`werkzeuge.en.md`](2-java-extraktoren-benchmark-forschungsdaten/doku/werkzeuge.en.md).

Do not rerun the project selection itself (`discover.py`, `acquire.py`,
`benchmark.py --prepare`). The repos have changed since the selection was made,
so you would end up with a different set. For repeating the measurements,
`manifest.json` together with `restore.py` is what you want.


## When something goes wrong

- If `restore.py` reports `Modified local input`, a file in the corpus has been
  changed. Delete that project's folder under `corpus/` and run `restore.py`
  again.
- If PNG or SVG files are missing, `javauml` could not find PlantUML. Set
  `PLANTUML_JAR` or pass `--plantuml <jar>`. Java has to be on the `PATH`.
- If `hebig` or `intellij` find no files, the folder names from the
  Zhang/Hebig package are usually off. `Version(s) of Source Code Used` must be
  named exactly like that, brackets and spaces included.
- If the container stops on Windows with `bad interpreter` or `start: not
  found`, the repository was checked out with Windows line endings. Cloning it
  again helps; `.gitattributes` then takes care of the right line endings.
