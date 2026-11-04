"""Gesamttabellen und normalisierte Referenzdateien aus den gespeicherten Läufen neu erzeugen."""
from collections import Counter
import csv
import json
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parent.parent
# Alle Pfade in den JSON-Dateien der Lindholmen-Auswahl sind relativ zu diesem Ordner.
DATA=ROOT/'daten'/'lindholmen'
RESULTS=ROOT/'ergebnisse'/'messungen'

def aggregate(rows):
    counts={k:sum(r['edges'][k] for r in rows) for k in ('tp','fp','fn')}
    tp,fp,fn=(counts[k] for k in ('tp','fp','fn'))
    return dict(**counts,precision=tp/(tp+fp),recall=tp/(tp+fn),f1=2*tp/(2*tp+fp+fn),
                macro_f1=mean(r['edges']['f1'] for r in rows),seconds=sum(r['seconds'] for r in rows),
                node_recall=sum(r['nodes']['tp'] for r in rows)/sum(r['nodes']['tp']+r['nodes']['fn'] for r in rows),
                statuses=dict(Counter(r['status'] for r in rows)))

def main():
    before=json.loads((RESULTS/'before/results.json').read_text())
    after=json.loads((RESULTS/'final/results.json').read_text())
    curated=json.loads((RESULTS/'curated-final/aggregate.json').read_text())
    manifest=json.loads((DATA/'manifest.json').read_text())
    comparison=[r for r in after if r['tool']=='ours']+[r for r in before if r['tool']!='ours']
    (RESULTS/'comparison.json').write_text(json.dumps(comparison,indent=2))
    groups={'Own extractor — before':[r for r in before if r['tool']=='ours'],
            'Own extractor — fixed':[r for r in after if r['tool']=='ours'],'javalang + adapter':[r for r in before if r['tool']=='javalang'],
            'Java2PlantUML / JavaParser':[r for r in before if r['tool']=='java2plantuml']}
    totals={name:aggregate(rows) for name,rows in groups.items()}
    (RESULTS/'aggregate.json').write_text(json.dumps(totals,indent=2))
    refdir=DATA/'reference-graphs';refdir.mkdir(exist_ok=True)
    for r in manifest:
        obj={'repo':r['repo'],'commit':r['commit'],'model_path':r['path'],
             'scope':'unambiguously mapped model classifiers only',
             'nodes':r['reference_nodes'],'edges':r['reference_edges'],
             'mapping':r['mapping'],'unmapped_model_nodes':r['unmapped_model_nodes']}
        name=r['repo'].replace('/','__');(refdir/(name+'.json')).write_text(json.dumps(obj,indent=2))
        ids={q:f'n{i}' for i,q in enumerate(r['reference_nodes'])}
        lines=['@startuml',"' Normalized mapped reference scope; associations are undirected."]
        lines += [f'class "{q}" as {alias}' for q,alias in ids.items()]
        arrows={'association':'--','inheritance':'--|>','realization':'..|>'}
        lines += [f'{ids[s]} {arrows[k]} {ids[t]}' for s,t,k in r['reference_edges']]
        (refdir/(name+'.puml')).write_text('\n'.join(lines+['@enduml','']))
    lines=['# Java UML extractor benchmark — 2026-09-20','',
      'A reproducible **30-project subset of Lindholmen** is downloaded and paired with its original UML/XMI models. '
      'The subset contains **4,040 Java source files**. Each source/model pair is pinned to the same Git commit. '
      'Three extraction approaches were run on exactly the same inputs.','',
      '**These are diagram-agreement scores, not exhaustive source-correctness scores.** '
      'Repository diagrams can be partial, abstract, generated, or out of date. '
      'The benchmark deliberately records that limitation rather than presenting the diagrams as independently validated gold truth.','',
      '## Curated Zhang–Hebig companion suite','',
      'The replication package for Zhang, Zhang, Strüber and Hebig’s 2025 manual-abstraction study is also downloaded and benchmarked. '
      'It contributes nine exact Java revisions, 79 modeled classifiers, 82 author-counted diagram relationships, original diagrams, '
      'manual annotations, reverse-engineered diagrams and per-project comparison workbooks. Three diagrams contain repeated directed '
      'associations between the same classifier pair; the shared undirected-association metric contains 79 distinct relationships. '
      '`daten/zhang-hebig/reference.json` is a reviewable manual transcription; the original images, PDFs and workbooks are preserved beside it.','',
      '| Extractor | Completed | Node recall | Edge precision | Edge recall | Micro F1 | Adapter time |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
      f"| Own extractor — fixed | {curated['ours']['completed']}/9 | {curated['ours']['nodes']['recall']:.3f} | {curated['ours']['edges']['precision']:.3f} | {curated['ours']['edges']['recall']:.3f} | {curated['ours']['edges']['f1']:.3f} | {curated['ours']['seconds']:.2f} s |",
      f"| javalang + adapter | {curated['javalang']['completed']}/9 | {curated['javalang']['nodes']['recall']:.3f} | {curated['javalang']['edges']['precision']:.3f} | {curated['javalang']['edges']['recall']:.3f} | {curated['javalang']['edges']['f1']:.3f} | {curated['javalang']['seconds']:.2f} s |",
      f"| Java2PlantUML / JavaParser | {curated['java2plantuml']['completed']}/9 | {curated['java2plantuml']['nodes']['recall']:.3f} | {curated['java2plantuml']['edges']['precision']:.3f} | {curated['java2plantuml']['edges']['recall']:.3f} | {curated['java2plantuml']['edges']['f1']:.3f} | {curated['java2plantuml']['seconds']:.2f} s |",'',
      'All three tools recover the same 73 of 79 modeled classifiers. The six missing classifiers are documented model/code differences: '
      'five RaiseMeUp concepts absent or summarized differently in source and the model-only `Link` class in myblog. The own extractor and '
      'javalang tie on normalized relationship agreement. Java2PlantUML is more precise but omits more diagram relationships.','',
      '## Results','',
      '| Extractor | Completed | Edge precision | Edge recall | Micro F1 | Macro F1 | Adapter time |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,a in totals.items():
        lines.append(f"| {name} | {a['statuses'].get('ok',0)}/30 | {a['precision']:.3f} | {a['recall']:.3f} | {a['f1']:.3f} | {a['macro_f1']:.3f} | {a['seconds']:.2f} s |")
    n=sum(len(r['reference_nodes']) for r in manifest);e=sum(len(r['reference_edges']) for r in manifest)
    totaln=sum(r['model_total_nodes'] for r in manifest);totale=sum(r['model_total_edges'] for r in manifest)
    lines += ['',f'The scored scope contains **{n} mapped classifiers and {e} relations**, drawn from models containing '
      f'{totaln} named classifiers and {totale} resolved class relations before source mapping. '
      'Full model identities, unmapped names, ambiguous matches and unsupported references are retained in `daten/lindholmen/manifest.json`.','',
      'All tools recover all mapped nodes in this sample (node recall 1.0). Because correspondence preparation uses a '
      'javalang source inventory, this is a feasibility/coverage observation, not an unbiased node-accuracy result. '
      'Unmapped model classes are excluded transparently; other source classes outside the diagram scope are not counted as false positives.','',
      'The fixed extractor recovers five more reference relationships (224 → 229 of 399). It also emits fourteen additional '
      'source relationships absent from the reference diagrams (diagram-extra edges 67 → 81). '
      'Consequently micro F1 changes from 0.649 to 0.646. **This is not evidence that the fixes made extraction less correct, '
      'nor is it a meaningful victory over javalang.** It demonstrates the difference between literal extraction and architectural abstraction.','',
      'Times are single-run adapter wall times on this machine, including parsing and graph construction; Java2PlantUML includes '
      'JVM startup and UTF-8 staging. They exclude corpus download and reference preparation. No statistical runtime claim is made.','',
      '## What was fixed in abstract-uml','',
      '- Restored a working project `.venv`; preserved the broken environment in `original-venv/`.',
      '- Anchored `/runs/` in `.gitignore`, exposing the required `src/runs/` modules to Git.',
      '- Preserved original Java qualified identities and package/import context. Explicit imports no longer bind to unrelated project classes.',
      '- Added conservative wildcard and inherited nested-type resolution; ambiguous matches warn and are omitted.',
      '- Used the same resolver for the Java class graph, dependency graph and inheritance graph, avoiding contradictory clustering inputs.',
      '- Extracted enum body fields/methods, interface constants, and array dimensions after variable names.',
      '- Preserved project types nested in custom generic wrappers such as `NeurophArrayList<Neuron>`.',
      '- Kept legitimate self-associations and prevented named/default-package identity collisions.',
      '- Versioned the parser cache to avoid reusing obsolete graph objects; updated README toolbox and Java behavior descriptions.','',
      'Thirteen new regression tests cover these cases and cyclic invalid inheritance. Seven of the first eight tests failed before '
      'the changes; the remaining inherited-type case happened to pass through the old guessing behavior, so its fixture was tightened. '
      'Final project verification: **385 passed, 1 network test deselected**. Benchmark normalization and curated-reference validation: **10 passed**. '
      'A separate syntax audit finds zero tree-sitter syntax-error files in the 4,040 selected inputs.','',
      'The Java pipeline was also run through **all eight variants with `--dry-run --no-cleanup`**. '
      'All eight wrote diagrams and summaries. This validates plumbing, not live LLM diagram quality. '
      'The generic stub adds dummy nodes to prune seeds, producing documented node-cap warnings; no paid LLM calls were made.','',
      '## Examples checked against code','',
      '- `hodiqual/projet2015`: reference matches improve 31 → 33; the `TypePoint` enum contains a `Map<String, TypePoint>` field. '
      'Enum fields and self-references are real source facts.',
      '- `jainebri/Super-Simple-Stocks`: matches improve 10 → 11. The `SimpleStockServicesFactory` interface declares its own singleton `INSTANCE`.',
      '- `Neseek77/gwt-ent`: matches improve 2 → 3. The corpus exposes self-relations in a reflection API.',
      '- `shadeven/cerebrumehr`: every tool matches 0 of 96 projected diagram edges. Source relationships commonly involve generated `*Base` '
      'classes while the diagram models the domain classes. This is a scope/abstraction mismatch, not proof that every tool fails to parse the project.',
      '- Most new diagram-extra edges are self-associations (including enum value tables and singleton holders). The curated Neuroph case '
      'also exposed a missed generic-wrapper relationship, which is now preserved. Source declarations are retained for review.','',
      '## Reproduce','',
      'From `~/Desktop/java-uml-benchmark/`, using the installed environment:',
      '```bash',
      '.venv/bin/python skripte/restore.py  # verifies existing inputs; downloads missing pinned snapshots',
      '.venv/bin/python -m pytest -q skripte/test_benchmark.py',
      '.venv/bin/python skripte/benchmark.py --label rerun --limit 30',
      'PYTHONPATH=../1-llm-pipeline-abstrakte-klassendiagramme .venv/bin/python skripte/curated_hebig_benchmark.py --label curated-rerun',
      '```','',
      'To recreate the environment and competitor build from scratch, see `REPRODUCE.md`. '
      '`requirements.lock.txt`, `TOOLS.json`, archive SHA-256s and per-source SHA-256s capture versions and inputs. '
      'The before state is preserved in `project-before.tar.gz`; extract it to a separate directory and run the harness with that checkout '
      'first on `PYTHONPATH` to reproduce the original extractor. Never overwrite the active working tree to replay a baseline.','',
      'To regenerate this report from the saved measurements: `.venv/bin/python skripte/report.py`. '
      'The frozen manifest is authoritative; `discover.py` and `acquire.py` document selection but may observe different live availability later.','',
      '## Artifacts and limits','',
      '- `RESEARCH.md`: papers, rejected alternatives, licenses and evaluation contract.',
      '- `daten/lindholmen/manifest.json`: the 30 frozen project/commit/model/source mappings.',
      '- `daten/lindholmen/reference-graphs/`: normalized scoped references in JSON and PlantUML; originals remain under `daten/lindholmen/corpus/`.',
      '- `ergebnisse/messungen/before/`, `ergebnisse/messungen/final/`, `ergebnisse/messungen/comparison.json`, `ergebnisse/messungen/aggregate.json`: raw outputs and results.',
      '- `daten/zhang-hebig/` and `ergebnisse/messungen/curated-final/`: the nine-project package, manual graph transcription, hashes and extractor results.',
      '- `daten/lindholmen/discovery.json`, `daten/lindholmen/acquisition.json`, `daten/lindholmen/preparation-exclusions.json`: screening and failures; no silent exclusions.',
      '- `project-before.patch`, `project-before.tar.gz`, `changes-this-session.diff`: preservation and review.',
      '- `tests-final.log`, `benchmark-tests.log`, `daten/lindholmen/syntax-audit.json`, `ergebnisse/pipeline-trockenlauf/`: verification evidence.','',
      'This is a newly screened subset of a published research dataset, not an independently human-validated 30-project gold standard. '
      'Selection favors small, available, Java-8-parseable projects with XML models. Only one indexed model is considered per repository. '
      'Associations are compared without direction, multiplicity or ownership; inheritance and realization retain direction and type. '
      'The javalang comparator is a custom adapter with simpler type resolution, not a standalone UML extractor. '
      'All three runs completed; process timeouts are 120 seconds per adapter and 90 seconds for Java2PlantUML. '
      'Live LLM synthesis, annotation semantics, dependency classpath resolution and exhaustive semantic correctness remain outside this benchmark.','',
      'Final reproduction check: all 90 broad-suite runs (30 projects × 3 tools) and all 27 curated-suite runs (9 projects × 3 tools) '
      'reproduced identical statuses, node/edge metrics and discrepancy sets. See `reproduction-verification.json`.','',
      'No commits, pushes, or publication were performed. Existing work was preserved.','',
      '## Per-project diagram agreement','',
      '| Project | Java files | Mapped nodes | Reference edges | Own F1 before | Own F1 fixed | javalang F1 | Java2PlantUML F1 |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for m in manifest:
        repo=m['repo'];old=next(r for r in before if r['repo']==repo and r['tool']=='ours');new=next(r for r in after if r['repo']==repo and r['tool']=='ours')
        jl=next(r for r in before if r['repo']==repo and r['tool']=='javalang');jp=next(r for r in before if r['repo']==repo and r['tool']=='java2plantuml')
        lines.append(f"| [{repo}](https://github.com/{repo}/tree/{m['commit']}) | {len(m['files'])} | {len(m['reference_nodes'])} | {len(m['reference_edges'])} | {old['edges']['f1']:.3f} | {new['edges']['f1']:.3f} | {jl['edges']['f1']:.3f} | {jp['edges']['f1']:.3f} |")
    (RESULTS/'REPORT.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
