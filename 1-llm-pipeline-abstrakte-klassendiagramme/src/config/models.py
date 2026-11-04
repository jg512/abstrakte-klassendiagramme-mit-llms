from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FiltersConfig:
    exclude_dirs: tuple[str, ...]
    exclude_files: tuple[str, ...]


@dataclass(frozen=True)
class SizeCapsConfig:
    max_loc: int
    max_classes: int


@dataclass(frozen=True)
class DriverConfig:
    """Budget des Drivers. Es ist für alle Varianten gleich, damit sie vergleichbar bleiben."""
    max_tool_calls: int
    max_tokens: int
    read_file_max_lines: int
    compress_every_n_turns: int  # 0 = aus; sonst den Verlauf alle N Tool-Calls zusammenfassen


@dataclass(frozen=True)
class ClusteringConfig:
    """Nur für cluster und cluster-peek (Zerlegung pro Cluster)."""
    max_cluster_size: int
    min_cluster_size: int
    synthesis_share: float  # Anteil des Driver-Budgets, der für die Synthese zurückgehalten wird


@dataclass(frozen=True)
class OutputConfig:
    dir: str
    write_pyreverse: bool
    trace_jsonl: bool
    trace_messages: bool  # bei true volle Nachrichten und Tools im Trace speichern (für replay)


@dataclass(frozen=True)
class DevConfig:
    cache_dir: str
    verbose: bool


@dataclass(frozen=True)
class JavaConfig:
    """Einstellungen für die Extraktion des Java-Quellgraphen.

    Standard bleibt der schnelle Weg ohne Build. Die Auflösung über ``javac`` muss
    man ausdrücklich einschalten, weil beliebige Repos oft einen unvollständigen
    Classpath haben. Eingeschaltet ergänzt sie die Quelltext-Auflösung, ersetzt
    aber keine Kanten, die schon aufgelöst sind.
    """

    source_sets: str = "auto"          # auto | all
    include_generated: bool = False
    member_profile: str = "summary"    # structure | summary | public-api | full
    include_external_supertypes: bool = True
    include_method_dependencies: bool = False
    symbol_solver: str = "source"      # source | javac
    classpath: tuple[str, ...] = ()
    # literal: Felder, extends, implements (Standard). intellij: Klassendiagramm
    # nach den Regeln von IntelliJ, mit Abhängigkeiten aus den Methodenrümpfen.
    relation_style: str = "literal"
    ide_jdk: bool = True               # nur intellij: JDK eingerichtet?
    ide_same_package: bool = True      # nur intellij: Klassen aus demselben Paket gefunden?
    diagram_classes: tuple[str, ...] = ()   # nur intellij: Klassen im Diagramm, leer = alle


@dataclass(frozen=True)
class Config:
    language: str                 # "python" | "java", wählt den Parser
    backend: str
    model: str
    base_url: str
    api_key_env: str
    temperature: float
    num_ctx: int
    seed: int
    request_timeout: int          # Sekunden; 0 = Standard von litellm (600)
    target_nodes: int | None      # None = offen: das Modell wählt die Größe
    max_nodes: int                # harte Obergrenze; zur Laufzeit auf die Klassenzahl des Repos gekappt
    node_tolerance: float
    cleanup: bool
    auto_target_nodes: bool
    context_budget: int
    driver: DriverConfig
    clustering: ClusteringConfig
    filters: FiltersConfig
    size_caps: SizeCapsConfig
    output: OutputConfig
    dev: DevConfig
    java: JavaConfig = field(default_factory=JavaConfig)
