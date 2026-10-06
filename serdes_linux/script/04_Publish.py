#!/usr/bin/env python3
"""Maintainer-only native release builder. Never edits or deletes the source tree.

Build dependencies: Cython 3.1.6, setuptools 80.9.0, GCC, matching Python headers.
Run under the target Ketupa CPython ABI. Artifacts are Linux-only, not Windows PYD.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compile_extensions(units, build, destination, jobs):
    from setuptools import Distribution, Extension
    from Cython.Build import cythonize
    from Cython.Compiler import Options
    Options.docstrings = False
    header = Path(sysconfig.get_path("include"))
    if not (header / "Python.h").is_file():
        header = Path("/usr/include/python{0}.{1}".format(*sys.version_info[:2]))
    if not (header / "Python.h").is_file():
        raise RuntimeError("Install matching CPython development headers before compiling")
    extensions = []
    staged = build / "staged"
    for name, source, target in units:
        extensions.append(Extension(name, [source.relative_to(staged).as_posix()],
            include_dirs=[str(header)],
            extra_compile_args=["-O2", "-g0", "-fvisibility=hidden"],
            extra_link_args=["-Wl,--strip-all"]))
    previous = Path.cwd()
    try:
        os.chdir(staged)
        compiled = cythonize(extensions, nthreads=jobs, build_dir=str(build / "c"),
            compiler_directives=dict(language_level=3, annotation_typing=False,
                                     binding=True, embedsignature=False, emit_code_comments=False),
            quiet=True)
        distribution = Distribution(dict(name="ketupa-native", ext_modules=compiled))
        command = distribution.get_command_obj("build_ext")
        command.build_lib = str(build / "extensions")
        command.build_temp = str(build / "objects")
        command.parallel = jobs
        command.ensure_finalized()
        command.run()
    finally:
        os.chdir(previous)
    for name, source, target in units:
        artifact = Path(command.get_ext_fullpath(name))
        output = destination / target
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact, output)
        subprocess.run(["strip", "--strip-unneeded", str(output)], check=True)


def source_facts(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), str(path))
    functions = sorted({n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))})
    imports, methods, paths = set(), set(), set()
    calls = defaultdict(list)
    invalid = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == "resource" or node.value.startswith("resource/"):
                paths.add(node.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            methods.add(method)
            try:
                if node.keywords:
                    raise ValueError("Keyword arguments")
                calls[method].append(tuple(ast.literal_eval(arg) for arg in node.args))
            except (ValueError, TypeError):
                invalid.add(method)
    recordings = {name: values for name, values in calls.items() if name not in invalid}
    facts = dict(functions=functions, imports=sorted(imports), methods=sorted(methods),
                 resource_paths=sorted(paths), invalid_recordings=sorted(invalid))
    return tree, facts, recordings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True,
                        help="New private build directory outside the product")
    parser.add_argument("--jobs", type=int, default=2)
    options = parser.parse_args(argv)
    if sys.platform != "linux" or sys.version_info[:2] != (3, 12):
        parser.error("This release targets Linux CPython 3.12 only")
    if not 1 <= options.jobs <= 4:
        parser.error("--jobs must be 1..4")
    destination = options.destination.resolve()
    if destination.is_relative_to(ROOT) or destination.exists():
        parser.error("Destination must be NEW and outside the source project")
    destination.mkdir(parents=True, mode=0o700)
    build = destination / "private-build"
    build.mkdir(mode=0o700)
    product = destination / "ketupa_serdes_linux_cp312"
    product.mkdir()
    from lib.unified_runner import audit_contracts
    from lib.core.config_audit import audit_config
    from lib.catalog import load_catalog
    from lib.core.workflow_geometry_contract import workflow_geometry_declaration
    from lib.core.workflow_package_contract import audit_package_workflow
    passed, messages = audit_contracts()
    config = audit_config(ROOT)
    if not passed or not config["valid"]:
        raise RuntimeError("Source audit failed: " + repr((messages, config)))
    (destination / "source-audit.json").write_text(json.dumps(
        dict(contracts=messages, config=config), ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "main.py", product / "main.py")
    shutil.copy2(ROOT / "README.md", product / "README.md")
    shutil.copytree(ROOT / "input", product / "input")
    shutil.copytree(ROOT / "script", product / "script", ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.pyo", "*.md", "*.docx", "docs", "03_Verify.py", "04_Publish.py"))
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    raw_map = json.loads((ROOT / "lib/_variant_map.json").read_text())
    mapping = {k: {w: p for w, p in v.items() if w.startswith("serdes-")}
               for k, v in raw_map["modules"].items()}
    mapping = {k: v for k, v in mapping.items() if v}
    profiles = {p for v in mapping.values() for p in v.values()}
    asset_paths = [ROOT / "resource/workflows.json", *sorted((ROOT / "config").rglob("*.json"))]
    assets = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8-sig") for p in asset_paths}
    assets["lib/_variant_map.json"] = json.dumps(dict(schema_version=1, modules=mapping))
    facts, recordings, variants, units = {}, {}, {}, []
    source_hashes = {}
    for area in ("lib", "resource", "modules"):
        for path in sorted((ROOT / area).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            if "profiles" in path.parts and path.relative_to(ROOT / "lib").as_posix() not in profiles:
                continue
            tree, fact, recorded = source_facts(path)
            facts[relative], recordings[relative] = fact, recorded
            source_hashes[relative] = digest(path)
            # Recorded AEDT argument trees are DATA, never executed as modules.
            if "vbsmodule" in path.parts and not fact["functions"] and fact["methods"]:
                continue
            if relative in {"resource/aedt_report_executor.py", "resource/__init__.py"}:
                continue
            parts = list(path.relative_to(ROOT).with_suffix("").parts)
            source = build / "staged" / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, source)
            if "profiles" in parts:
                alias = "_v_" + hashlib.sha256(relative.encode()).hexdigest()[:20]
                source = build / "staged" / "lib" / (alias + ".py")
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, source)
                name = "lib." + alias
                target = "lib/" + alias + suffix
                variants[path.relative_to(ROOT / "lib").as_posix()] = name
            elif path.name == "__init__.py":
                name = ".".join(parts[:-1])
                target = path.relative_to(ROOT).with_name("__init__" + suffix).as_posix()
            else:
                if parts[0] == "resource":
                    parts[:1] = ["lib", "core"]
                name = ".".join(parts)
                target = path.relative_to(ROOT).with_name(path.stem + suffix).as_posix()
            units.append((name, source, target))
    for spec in load_catalog():
        fact = facts[spec.entrypoint.relative_to(ROOT).as_posix()]
        fact["geometry"] = workflow_geometry_declaration(spec.entrypoint, spec.topology)
        fact["package_errors"] = audit_package_workflow(ROOT, spec.entrypoint, spec.workflow_id, spec.topology)
        if fact["package_errors"]:
            raise RuntimeError(repr(fact["package_errors"]))
    # Data is embedded in native code; NO general read_source or source-loader API.
    data_path = build / "staged/lib/_native_data.py"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    host_adapter = (ROOT / "resource/aedt_report_executor.py").read_text(encoding="utf-8")
    data_path.write_text("from copy import deepcopy\n" +
        "_FACTS = " + repr(facts) + "\n_RECORDINGS = " + repr(recordings) +
        "\n_ASSETS = " + repr(assets) + "\n_VARIANTS = " + repr(variants) +
        "\ndef fact(key): return deepcopy(_FACTS.get(key))\n" +
        "def has_asset(key): return key in _ASSETS\n" +
        "def asset(key): return _ASSETS[key]\n" +
        "def asset_keys(): return tuple(_ASSETS)\n" +
        "def variants(): return dict(_VARIANTS)\n" +
        "def recorded(key, method):\n" +
        "    if method in _FACTS[key]['invalid_recordings']: raise ValueError('Not a literal AEDT recording')\n" +
        "    return deepcopy(_RECORDINGS[key].get(method, []))\n" +
        "def report_host_adapter():\n    return " + repr(host_adapter) + "\n", encoding="utf-8")
    units.append(("lib._native_data", data_path, "lib/_native_data" + suffix))
    os.environ["CC"] = "gcc"
    compile_extensions(units, build, product, options.jobs)
    expected = {p.relative_to(product).as_posix(): digest(p) for p in sorted(product.rglob("*.so"))}
    seal_path = build / "staged/lib/_native_seal.py"
    seal_path.write_text("import hashlib\nfrom pathlib import Path\n_EXPECTED = " + repr(expected) + textwrap.dedent('''

        def verify(root):
            root = Path(root)
            for relative, expected in _EXPECTED.items():
                path = root / relative
                with path.open('rb') as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                if actual != expected:
                    raise RuntimeError('Native release integrity failure: ' + relative)
            for area in ('lib', 'modules', 'resource'):
                for path in (root / area).rglob('*'):
                    if path.is_file() and path.suffix in {'.py', '.pyc', '.pyo', '.pyx', '.c'}:
                        raise RuntimeError('Unexpected core source override: ' + str(path))
            return True
        '''), encoding="utf-8")
    compile_extensions([("lib._native_seal", seal_path, "lib/_native_seal" + suffix)], build, product, 1)
    # A compilable archive is not yet a usable product. Exercise the actual
    # extension-only package in clean child interpreters before archiving it.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith("KETUPA_") and k != "PYTHONPATH"}
    for label, arguments in (("audit", ["audit"]),
                             ("dry-run", ["run-all", "--dry-run"])):
        with (destination / ("native-" + label + ".log")).open("w") as stream:
            subprocess.run([sys.executable, "-B", "main.py", *arguments],
                           cwd=product, env=environment, stdout=stream,
                           stderr=subprocess.STDOUT, timeout=180, check=True)
    # Preserve test evidence privately, but never ship it as customer inputs.
    for name in ("output", ".cache", "__pycache__"):
        path = product / name
        if path.exists():
            shutil.move(str(path), str(build / ("validation-" + name)))
    for path in list(product.rglob("__pycache__")):
        token = hashlib.sha256(str(path.relative_to(product)).encode()).hexdigest()[:16]
        shutil.move(str(path), str(build / ("validation-cache-" + token)))
    for area in ("resource", "lib", "modules"):
        assert not list((product / area).rglob("*.py"))
    assert [p.relative_to(product).as_posix() for p in product.rglob("*.md")] == ["README.md"]
    manifest = dict(python=sys.version, platform=sys.platform,
                    files={p.relative_to(product).as_posix(): digest(p)
                           for p in sorted(product.rglob("*")) if p.is_file()},
                    source_sha256=source_hashes,
                    physical_aedt_validation="NOT_RUN_BY_BUILDER",
                    native_audit="PASS", native_three_case_dry_run="PASS",
                    protection="Native compilation, NOT impossible-to-reverse encryption")
    (destination / "build-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = destination / (product.name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(product, arcname=product.name)
    (destination / "SHA256SUMS").write_text(digest(archive) + "  " + archive.name + "\n", encoding="ascii")
    print("Native candidate:", product, flush=True)
    print("Validate before publication:", archive, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
