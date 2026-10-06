"""Create a version-bound acceptance matrix without confusing mocks with AEDT evidence."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_product_runtime():
    """Run acceptance with the configured product Python, not host Python."""
    configured = os.environ.get("PYTHON_EXE", "").strip()
    if not configured:
        settings = ROOT / "script/extractors/cds_env"
        if settings.is_file():
            for line in settings.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith("PYTHON_EXE="):
                    configured = line.split("=", 1)[1].strip()
                    break
    if not configured:
        return
    runtime = Path(configured).expanduser().resolve()
    if runtime == Path(sys.executable).resolve():
        return
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise RuntimeError("Configured verification Python is not executable: {0}".format(runtime))
    environment = os.environ.copy()
    environment["PYTHON_EXE"] = str(runtime)
    environment["PYTHONUNBUFFERED"] = "1"
    os.execve(str(runtime), [str(runtime), str(Path(__file__).resolve()), *sys.argv[1:]], environment)


_bootstrap_product_runtime()
sys.path.insert(0, str(ROOT))
from lib.catalog import load_catalog
from lib.core.task_context import version_digest, write_json, new_run_id
from lib.core.regression_evidence import evaluate_matrix
from lib.core.config_audit import audit_config
from lib.unified_runner import audit_contracts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-gate", action="store_true")
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--run-id", action="append", default=[], help="Explicit task evidence; repeat for separate workflows. No history guessing.")
    parser.add_argument("--model-gate", action="store_true", help="Require twelve Mode 0 physical model reviews. Does not imply electrical acceptance.")
    parser.add_argument("--prepare-mode0", action="store_true", help="Write a twelve-workflow command plan only; never launch AEDT.")
    parser.add_argument("--import-review", type=Path, help="Import a completed human review request and hash its baseline/supporting files; does not run AEDT.")
    options = parser.parse_args(argv)
    if options.import_review:
        from lib.core.regression_evidence import import_review
        result = import_review(options.import_review, options.workspace.resolve(), version_digest(ROOT))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["mode0_build"] == "PASS" else 1
    identity = new_run_id("verify")
    folder = ROOT / "output/verification" / identity
    folder.mkdir(parents=True, exist_ok=False)
    if options.prepare_mode0:
        import main as project_main
        from lib.input_contract import inputs_for_spec
        from lib.unified_runner import _resolve_input_overrides, _resolve_project_input
        from lib.core.input_manifest import snapshot_sources, file_record
        planned = []
        for spec in load_catalog():
            entry = dict(workflow=spec.workflow_id, status="READY_FOR_PREPROCESS", actual_files=[])
            try:
                values = _resolve_input_overrides(spec, inputs_for_spec(project_main.INPUTS, spec))
                entry["actual_files"] = [file_record(value) for value in values.values() if str(value)]
                entry["status"] = "INPUT_FILES_RESOLVED_NOT_MODELED"
            except (OSError, ValueError, RuntimeError) as exc:
                entry["needs_preprocess"] = str(exc)
            planned.append(entry)
        plan = dict(schema_version=1, engine_sha256=version_digest(ROOT), execution="NOT_STARTED",
                    source_files=snapshot_sources(load_catalog(), project_main.INPUTS, _resolve_project_input),
                    input_readiness=planned,
                    first_baseline="lpddr-merge", workflows=[dict(
                        workflow=spec.workflow_id, mode=0,
                        argv=[sys.executable, "-B", str(ROOT / "main.py"), "run", spec.workflow_id,
                        "--mode", "0", "--no-signoff", "--preprocess-first", "--preprocess-entry", "py"])
                        for spec in load_catalog()],
                    instruction="Run LPDDR Merge first using main's saved inputs. Review the physical model before expanding to twelve. External workspaces require explicit --workspace and --input-map.")
        write_json(folder / "mode0-plan.json", plan)
        print(folder / "mode0-plan.json")
        return 0
    started = time.monotonic()
    environment = dict(os.environ)
    for name in ("KETUPA_WORKFLOW_ID", "KETUPA_RUN_ID", "KETUPA_WORKSPACE_ROOT"):
        environment.pop(name, None)
    contract_verified, contract_messages = audit_contracts()
    (folder / "contracts.log").write_text(
        "\n".join(contract_messages) + "\n", encoding="utf-8"
    )
    with (folder / "dependencies.log").open("w", encoding="utf-8") as log:
        dependencies = subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT,
                                      env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    config = audit_config(ROOT)
    engine_hash = version_digest(ROOT)
    matrix = evaluate_matrix(options.workspace.resolve(), options.run_id, load_catalog(), engine_hash)
    modeling_accepted = contract_verified and dependencies.returncode == 0 and config["valid"] and all(row["mode0_build"] == "PASS" for row in matrix)
    report = dict(schema_version=2, engine_sha256=engine_hash,
                  created_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                  elapsed_seconds=time.monotonic() - started,
                  contract_exit=0 if contract_verified else 1, dependency_exit=dependencies.returncode,
                  installed_packages={package.metadata["Name"]: package.version for package in importlib.metadata.distributions()},
                  production_accepted=False, modeling_accepted=modeling_accepted,
                  contract_verified=contract_verified,
                  config_audit=config, selected_run_ids=options.run_id, workflows=matrix,
                  rule="Do not promote interface or file-existence checks to physical AEDT acceptance.")
    artifacts = {}
    for name in ("launcher", "installer"):
        path = getattr(options, name)
        if path:
            path = path.resolve(strict=True)
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(4 * 1024**2):
                    digest.update(chunk)
            artifacts[name] = dict(path=str(path), sha256=digest.hexdigest(), bytes=path.stat().st_size,
                                   installation_test="NOT_VERIFIED_BY_THIS_COMMAND")
            if name == "launcher":
                tree = hashlib.sha256()
                count = 0
                for file in sorted(path.parent.rglob("*")):
                    if not file.is_file():
                        continue
                    tree.update(file.relative_to(path.parent).as_posix().encode("utf-8"))
                    with file.open("rb") as stream:
                        while chunk := stream.read(4 * 1024**2):
                            tree.update(chunk)
                    count += 1
                artifacts[name].update(directory_sha256=tree.hexdigest(), directory_files=count)
    report["artifacts"] = artifacts
    write_json(folder / "acceptance.json", report)
    from lib.core.run_logs import verification_index
    verification_index(folder.parent)
    if artifacts:
        write_json(ROOT / "release/candidates" / identity / "release-manifest.json", report)
    print(folder / "acceptance.json")
    return 1 if (options.release_gate or (options.model_gate and not modeling_accepted)
                 or not contract_verified or dependencies.returncode or not config["valid"]
                 or any(row["mode0_build"] == "FAIL" for row in matrix)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
