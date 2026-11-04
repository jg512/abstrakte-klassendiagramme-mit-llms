# Eine Umgebung für alle drei Ordner: Python 3.13, JDK 25, PlantUML und
# java2plantuml, so wie bei den Messungen (siehe
# 2-java-extraktoren-benchmark-forschungsdaten/werkzeuge/TOOLS.json).
#
# Datensätze und Ausgaben stecken nicht im Image, sie werden beim Start als
# Ordner eingehängt (siehe compose.yaml und INSTALLATION.md).

FROM eclipse-temurin:25-jdk-noble

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PLANTUML_JAR=/opt/werkzeuge/plantuml-1.2025.4.jar

# Python-Abhängigkeiten in den Versionen der Messumgebung
COPY 2-java-extraktoren-benchmark-forschungsdaten/werkzeuge/requirements.lock.txt /tmp/requirements.lock.txt
RUN uv venv /opt/venv --python 3.13 \
 && uv pip install --python /opt/venv/bin/python -r /tmp/requirements.lock.txt

# Fremdwerkzeuge: PlantUML zum Rendern, java2plantuml (mirajp1) für den
# Vergleich mit drei Werkzeugen. Der Commit und die JavaParser-Version sind
# dieselben wie in doku/reproduzieren.md.
RUN set -eux; \
    mkdir -p /opt/werkzeuge; cd /opt/werkzeuge; \
    curl -fsSL -o plantuml-1.2025.4.jar \
      https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml/1.2025.4/plantuml-1.2025.4.jar; \
    curl -fsSL -o javaparser-core-3.4.0.jar \
      https://repo1.maven.org/maven2/com/github/javaparser/javaparser-core/3.4.0/javaparser-core-3.4.0.jar; \
    echo "d75382e0e660d08d66662b3cd3093f90e2b43827423b3eec7ccd2abed3104008  javaparser-core-3.4.0.jar" | sha256sum -c -; \
    git clone --quiet https://github.com/mirajp1/java2plantuml.git java2plantuml; \
    git -C java2plantuml checkout --quiet cadd0f0a06e87825472227381a37210763ae137c; \
    mkdir -p java2plantuml/classes; \
    src=java2plantuml/src/main/java; \
    javac -nowarn -cp javaparser-core-3.4.0.jar -d java2plantuml/classes \
      $src/*.java $src/source/*.java $src/translate/*.java $src/visitors/*.java

WORKDIR /app
COPY . /app

# Die Skripte in Ordner 2 suchen die Werkzeuge unter werkzeuge/.
RUN W=/app/2-java-extraktoren-benchmark-forschungsdaten/werkzeuge \
 && ln -s /opt/werkzeuge/plantuml-1.2025.4.jar $W/plantuml-1.2025.4.jar \
 && ln -s /opt/werkzeuge/javaparser-core-3.4.0.jar $W/javaparser-core-3.4.0.jar \
 && ln -s /opt/werkzeuge/java2plantuml $W/java2plantuml \
 && uv pip install --python /opt/venv/bin/python --no-deps \
      -e /app/1-llm-pipeline-abstrakte-klassendiagramme \
      -e /app/3-java-parser-klassendiagramme \
 && install -m 755 /app/docker/start.sh /usr/local/bin/start

ENTRYPOINT ["start"]
CMD ["hilfe"]
