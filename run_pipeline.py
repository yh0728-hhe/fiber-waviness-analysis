#!/usr/bin/env python3
"""Run the complete exploratory fiber-waviness workflow with Python 3.12+.

Example:
    python run_pipeline.py --input-dir /path/to/extracted_tiffs --output-dir runs/my_run

Original TIFFs are read only. A new run directory must be empty or absent.
Canonical src/ scripts are copied byte-for-byte into the run directory so the
legacy sibling-file layout works and validation/audit source hashes remain
traceable. This does not replace the supplied results/ and report/ snapshots.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
SCRIPT_NAMES = (
    "analyze_fibers.py", "validate_pipeline.py", "create_summary.py",
    "audit_pipeline.py", "build_review.py",
)
DEPENDENCIES = {"numpy": "numpy", "scipy": "scipy", "skimage": "scikit-image",
                "PIL": "Pillow", "matplotlib": "matplotlib"}
SERIES_PATTERN = re.compile(r"(E\d+dm_(CD|DMSO)_(s\d+)_img\d+(?:v\d+)?)")
Z_PATTERN = re.compile(r"_z(\d+)")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_inputs(input_dir: Path) -> tuple[list[Path], int]:
    """Check the analyzer's existing lowercase .tif filename contract."""
    if not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {input_dir}")
    matches, ignored, identifiers = [], 0, {}
    for path in sorted(input_dir.rglob("*.tif")):
        series = SERIES_PATTERN.match(path.name)
        if not series:
            ignored += 1
            continue
        z = Z_PATTERN.search(path.name)
        if not z:
            raise ValueError(f"Matching TIFF filename lacks a _z<number> index: {path.name}")
        identifier = (series[1], int(z[1]))
        if identifier in identifiers:
            raise ValueError(f"Duplicate series/z image ID: {path} and {identifiers[identifier]}")
        identifiers[identifier] = path
        matches.append(path)
    if not matches:
        raise ValueError("No supported TIFFs found. Expected lowercase .tif names such as "
                         "E16dm_CD_s1_img1_z01_ORG.tif (CD or DMSO). "
                         "CZI, .tiff, uppercase extensions, and other filename conventions are not processed.")
    return matches, ignored


def ensure_fresh_output(output_dir: Path, input_dir: Path) -> None:
    if output_dir == input_dir or output_dir.is_relative_to(input_dir):
        raise ValueError("Choose an output directory outside the original input directory.")
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError(f"Output must be absent or empty; refusing to overwrite: {output_dir}")


def plan_commands(input_dir: Path, output_dir: Path, *, limit: int = 0,
                  representative_only: bool = False) -> list[tuple[str, list[str]]]:
    executable = sys.executable
    analysis = [executable, str(output_dir / "analyze_fibers.py"),
                "--input-dir", str(input_dir), "--output-dir", str(output_dir)]
    if limit:
        analysis += ["--limit", str(limit)]
    if representative_only:
        analysis.append("--representative-only")
    return [
        ("analyze", analysis),
        ("validate", [executable, str(output_dir / "validate_pipeline.py"),
                      "--analysis", str(output_dir / "analyze_fibers.py"),
                      "--output", str(output_dir / "validation")]),
        ("summarize", [executable, str(output_dir / "create_summary.py"),
                       "--base", str(output_dir)]),
        ("audit", [executable, str(output_dir / "audit_pipeline.py"),
                   "--base", str(output_dir),
                   "--output", str(output_dir / "validation" / "audit_results.json")]),
        ("build_review", [executable, str(output_dir / "build_review.py"),
                          str(output_dir / "report_data.json"),
                          "--output", str(output_dir / "review.html")]),
    ]


def installed_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    missing = []
    for module, distribution in DEPENDENCIES.items():
        if importlib.util.find_spec(module) is None:
            missing.append(distribution)
            continue
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "available; distribution metadata unavailable"
    if missing:
        raise ValueError("Missing dependencies: " + ", ".join(missing) +
                         ". Install the project requirements in your active environment first.")
    return versions


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def execute(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required. Activate a Python 3.12+ environment.")
    input_dir, output_dir = args.input_dir.expanduser().resolve(), args.output_dir.expanduser().resolve()
    if args.limit < 0:
        raise ValueError("--limit must be zero (all) or a positive integer.")
    paths, ignored = discover_inputs(input_dir)
    ensure_fresh_output(output_dir, input_dir)
    source_dir = ROOT / "src"
    missing = [name for name in SCRIPT_NAMES if not (source_dir / name).is_file()]
    if missing:
        raise ValueError("Missing canonical source scripts in src/: " + ", ".join(missing))
    commands = plan_commands(input_dir, output_dir, limit=args.limit,
                             representative_only=args.representative_only)
    print(f"Supported input TIFFs: {len(paths)}; ignored lowercase .tif filenames: {ignored}")
    print(f"Fresh run directory: {output_dir}")
    if args.dry_run:
        for name, command in commands:
            print(f"[{name}] {shlex.join(command)}")
        print("Dry run only; no files were written and no analysis was executed.")
        return 0
    versions = installed_versions()
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots = {}
    for name in SCRIPT_NAMES:
        source = source_dir / name
        shutil.copyfile(source, output_dir / name)
        snapshots[name] = {"canonical_source": f"src/{name}", "sha256": sha256(source)}
    shutil.copyfile(Path(__file__).resolve(), output_dir / "run_pipeline_snapshot.py")
    manifest = {
        "status": "running", "started_at_utc": timestamp(), "finished_at_utc": None,
        "input_directory": str(input_dir), "supported_input_tiff_count": len(paths),
        "ignored_lowercase_tiff_filename_count": ignored,
        "options": {"limit": args.limit, "representative_only": args.representative_only},
        "versions": versions, "source_snapshots": snapshots,
        "runner_sha256": sha256(Path(__file__).resolve()), "steps": [],
        "interpretation": "Numerical/synthetic checks and bookkeeping audit do not establish biological fiber validation.",
    }
    manifest_path = output_dir / "pipeline_run.json"
    write_manifest(manifest_path, manifest)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["MPLCONFIGDIR"] = str(output_dir / ".matplotlib")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with (output_dir / "pipeline.log").open("w", encoding="utf-8") as log:
        for name, command in commands:
            step = {"name": name, "started_at_utc": timestamp(), "command": command}
            manifest["steps"].append(step)
            line = f"\n[{name}] {shlex.join(command)}\n"
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
            try:
                process = subprocess.Popen(command, cwd=output_dir, env=env, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
                code = process.wait()
            except (OSError, KeyboardInterrupt) as exc:
                if "process" in locals() and process.poll() is None:
                    process.terminate()
                    process.wait()
                code = 130 if isinstance(exc, KeyboardInterrupt) else 1
                step["error"] = str(exc) or "Interrupted"
            step["return_code"] = code
            step["finished_at_utc"] = timestamp()
            write_manifest(manifest_path, manifest)
            if code:
                manifest["status"] = "failed"
                manifest["failed_step"] = name
                manifest["finished_at_utc"] = timestamp()
                write_manifest(manifest_path, manifest)
                print(f"Pipeline stopped at {name}; see {output_dir / 'pipeline.log'}", file=sys.stderr)
                return code
    manifest["status"] = "complete"
    manifest["finished_at_utc"] = timestamp()
    write_manifest(manifest_path, manifest)
    print(f"\nComplete. Open {output_dir / 'review.html'} in a browser.")
    print("Automatic QC passage is not manual or biological validation.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", required=True, type=Path, help="Extracted, original TIFF directory (read only)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs" / "latest",
                        help="New empty/absent run directory (default: runs/latest in this project)")
    parser.add_argument("--limit", type=int, default=0, help="Optional processing limit; 0 analyzes all matching TIFFs")
    parser.add_argument("--representative-only", action="store_true", help="Analyze the central z slice of each matching series")
    parser.add_argument("--dry-run", action="store_true", help="Validate paths/names and print commands without writing files")
    args = parser.parse_args()
    try:
        return execute(args)
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
