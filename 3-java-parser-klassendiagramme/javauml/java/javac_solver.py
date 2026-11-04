"""Optionale Anreicherung der Beziehungen über den JDK-Compiler.

Maßgeblich bleibt der tree-sitter-Durchlauf, der ohne Build auskommt. Nur auf
Wunsch nutzt dieses Modul die öffentlichen APIs ``javax.tools`` und
``com.sun.source``, um Feld- und Obertyp-Symbole mit javac aufzulösen. Fehlende
Abhängigkeiten werden als Diagnose gemeldet. Interne Symbole, die javac trotzdem
zuordnen konnte, ergänzen den Graphen.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from javauml.model import ClassInfo
from javauml.schema.graph import Diagnostic, Edge, EdgeEvidence


_HELPER = r'''
import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.nio.file.*;
import java.util.*;
import javax.lang.model.element.*;
import javax.lang.model.type.*;
import javax.lang.model.util.*;
import javax.tools.*;

public class AbstractUmlJavacEdges {
  static void emit(String source, String kind, String target, String member,
                   long line, String declared) {
    if (source == null || target == null || source.equals(target)) return;
    System.out.println(String.join("\t", source, kind, target,
      member == null ? "" : member, Long.toString(line),
      declared == null ? "" : declared.replace('\t', ' ')));
  }

  static class Scan extends TreePathScanner<Void, String> {
    final Trees trees;
    final CompilationUnitTree unit;
    final SourcePositions positions;
    Scan(Trees trees, CompilationUnitTree unit) {
      this.trees = trees; this.unit = unit; this.positions = trees.getSourcePositions();
    }
    long line(Tree tree) {
      long pos = positions.getStartPosition(unit, tree);
      return pos < 0 ? 0 : unit.getLineMap().getLineNumber(pos);
    }
    String qualified(Tree tree) {
      if (tree == null) return null;
      Element e = trees.getElement(new TreePath(getCurrentPath(), tree));
      return e instanceof TypeElement ? ((TypeElement)e).getQualifiedName().toString() : null;
    }
    void typeTargets(String owner, String kind, Tree tree, String member, long line) {
      if (tree == null) return;
      TypeMirror mirror = trees.getTypeMirror(new TreePath(getCurrentPath(), tree));
      if (mirror == null) return;
      new SimpleTypeVisitor14<Void, Void>() {
        @Override public Void visitDeclared(DeclaredType t, Void x) {
          Element e = t.asElement();
          if (e instanceof TypeElement)
            emit(owner, kind, ((TypeElement)e).getQualifiedName().toString(), member, line, tree.toString());
          for (TypeMirror arg : t.getTypeArguments()) walk(arg);
          return null;
        }
        @Override public Void visitArray(ArrayType t, Void x) { walk(t.getComponentType()); return null; }
        @Override public Void visitWildcard(WildcardType t, Void x) {
          if (t.getExtendsBound() != null) walk(t.getExtendsBound());
          if (t.getSuperBound() != null) walk(t.getSuperBound());
          return null;
        }
        void walk(TypeMirror t) { if (t != null) t.accept(this, null); }
      }.walk(mirror);
    }
    @Override public Void visitClass(ClassTree node, String ignored) {
      Element e = trees.getElement(getCurrentPath());
      String owner = e instanceof TypeElement ? ((TypeElement)e).getQualifiedName().toString() : null;
      if (owner != null) {
        typeTargets(owner, "inheritance", node.getExtendsClause(), "", line(node));
        for (Tree t : node.getImplementsClause())
          typeTargets(owner,
            (e.getKind() == ElementKind.INTERFACE || e.getKind() == ElementKind.ANNOTATION_TYPE)
              ? "inheritance" : "realization",
            t, "", line(t));
      }
      return super.visitClass(node, owner);
    }
    @Override public Void visitVariable(VariableTree node, String owner) {
      Tree parent = getCurrentPath().getParentPath() == null ? null : getCurrentPath().getParentPath().getLeaf();
      if (owner != null && parent instanceof ClassTree)
        typeTargets(owner, "field", node.getType(), node.getName().toString(), line(node));
      return super.visitVariable(node, owner);
    }
  }

  public static void main(String[] args) throws Exception {
    Path fileList = null; String classpath = "";
    for (int i=0; i<args.length; i++) {
      if (args[i].equals("--files")) fileList = Paths.get(args[++i]);
      else if (args[i].equals("--classpath")) classpath = args[++i];
    }
    if (fileList == null) throw new IllegalArgumentException("--files is required");
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    if (compiler == null) throw new IllegalStateException("JDK compiler unavailable");
    DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
    try (StandardJavaFileManager fm = compiler.getStandardFileManager(diagnostics, null, null)) {
      List<String> names = Files.readAllLines(fileList);
      Iterable<? extends JavaFileObject> units = fm.getJavaFileObjectsFromStrings(names);
      List<String> options = new ArrayList<>(Arrays.asList("-proc:none", "-Xlint:none"));
      if (!classpath.isEmpty()) { options.add("-classpath"); options.add(classpath); }
      JavacTask task = (JavacTask)compiler.getTask(null, fm, diagnostics, options, null, units);
      Iterable<? extends CompilationUnitTree> parsed = task.parse();
      try { task.analyze(); } catch (Throwable ignored) {}
      Trees trees = Trees.instance(task);
      for (CompilationUnitTree unit : parsed) new Scan(trees, unit).scan(unit, null);
      long errors = diagnostics.getDiagnostics().stream()
        .filter(d -> d.getKind() == javax.tools.Diagnostic.Kind.ERROR).count();
      System.err.println("ABSTRACT_UML_JAVAC_ERRORS=" + errors);
    }
  }
}
'''


def _many(declared: str) -> bool:
    compact = declared.replace(" ", "")
    return compact.endswith("[]") or any(
        compact.startswith(name + "<")
        for name in ("List", "Set", "Collection", "Queue", "Deque", "Map", "Iterable", "Stream")
    )


def resolve_with_javac(
    files: list[Path],
    root: Path,
    classes: list[ClassInfo],
    classpath: tuple[str, ...] = (),
) -> tuple[list[Edge], list[Diagnostic]]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        return [], [Diagnostic(
            code="javac-unavailable",
            message="java.symbol_solver=javac requested but a JDK was not found",
            severity="error",
        )]

    by_source: dict[tuple[str, str], list[ClassInfo]] = defaultdict(list)
    file_module: dict[Path, str] = {}
    for cls in classes:
        by_source[(cls.build_module, cls.source_qualified_name or cls.qualified_name)].append(cls)
        file_module[cls.file] = cls.build_module
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        groups[file_module.get(path, "")].append(path)

    edges: list[Edge] = []
    diagnostics: list[Diagnostic] = []
    with tempfile.TemporaryDirectory(prefix="abstract-uml-javac-") as td:
        work = Path(td)
        source = work / "AbstractUmlJavacEdges.java"
        source.write_text(_HELPER, encoding="utf-8")
        compiled = subprocess.run(
            [javac, "-d", str(work), str(source)], capture_output=True, text=True
        )
        if compiled.returncode:
            return [], [Diagnostic(
                code="javac-helper-failed",
                message=compiled.stderr.strip()[-1000:], severity="error",
            )]

        import os
        cp = os.pathsep.join(classpath)
        for index, (module, module_files) in enumerate(sorted(groups.items())):
            manifest = work / f"files-{index}.txt"
            manifest.write_text("\n".join(str(p) for p in module_files) + "\n", encoding="utf-8")
            command = [java, "-cp", str(work), "AbstractUmlJavacEdges", "--files", str(manifest)]
            if cp:
                command += ["--classpath", cp]
            try:
                result = subprocess.run(
                    command, cwd=root, capture_output=True, text=True, timeout=120
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                diagnostics.append(Diagnostic(
                    code="javac-resolution-failed", message=str(exc),
                    source=module or ".", severity="error",
                ))
                continue
            error_count = 0
            for line in result.stderr.splitlines():
                if line.startswith("ABSTRACT_UML_JAVAC_ERRORS="):
                    error_count = int(line.partition("=")[2] or 0)
            if result.returncode:
                diagnostics.append(Diagnostic(
                    code="javac-resolution-failed",
                    message=result.stderr.strip()[-1000:] or f"java exited {result.returncode}",
                    source=module or ".", severity="error",
                ))
                continue
            if error_count:
                diagnostics.append(Diagnostic(
                    code="javac-partial-resolution",
                    message=f"javac reported {error_count} attribution errors; resolved internal facts were retained",
                    source=module or ".",
                ))
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) != 6:
                    continue
                source_q, kind, target_q, member, line_no, declared = parts
                source_matches = by_source.get((module, source_q), [])
                target_matches = by_source.get((module, target_q), [])
                if len(source_matches) != 1 or len(target_matches) != 1:
                    continue
                relation = kind
                target_card = None
                if kind == "field":
                    relation = "aggregation" if _many(declared) else "association"
                    target_card = "0..*" if relation == "aggregation" else None
                    if declared.replace(" ", "").startswith("Optional<"):
                        target_card = "0..1"
                cls = source_matches[0]
                edges.append(Edge(
                    source=cls.qualified_name,
                    target=target_matches[0].qualified_name,
                    type=relation,
                    target_card=target_card,
                    label=member or None,
                    evidence=[EdgeEvidence(
                        kind=kind, member=member or None,
                        declared_type=declared or target_q,
                        file=cls.source_file or str(cls.file),
                        line=int(line_no) if line_no.isdigit() else None,
                        resolver="javac",
                    )],
                ))
    return edges, diagnostics
