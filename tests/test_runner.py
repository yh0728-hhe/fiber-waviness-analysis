"""Run with: python -m unittest discover -s tests -v (stdlib only)."""

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pipeline_runner", ROOT / "run_pipeline.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_discovery_reports_ignored_names(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "E16dm_CD_s1_img1_z01_ORG.tif").touch()
            (base / "unrecognized.tif").touch()
            paths, ignored = runner.discover_inputs(base)
            self.assertEqual(len(paths), 1)
            self.assertEqual(ignored, 1)

    def test_duplicate_image_ids_are_rejected_before_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for folder in ["one", "two"]:
                (base / folder).mkdir()
                (base / folder / "E16dm_CD_s1_img1_z01_ORG.tif").touch()
            with self.assertRaisesRegex(ValueError, "Duplicate series/z"):
                runner.discover_inputs(base)

    def test_existing_results_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            original = base / "keep.txt"
            original.write_text("keep")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                runner.ensure_fresh_output(base, base.parent / "raw")
            self.assertEqual(original.read_text(), "keep")

    def test_output_is_not_created_inside_raw_input(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            with self.assertRaisesRegex(ValueError, "outside"):
                runner.ensure_fresh_output(raw / "new_results", raw)

    def test_dry_run_is_read_only_and_handles_spaces(self):
        with tempfile.TemporaryDirectory(prefix="fiber input ") as directory:
            base = Path(directory)
            raw = base / "raw data"
            raw.mkdir()
            image = raw / "E16dm_CD_s1_img1_z01_ORG.tif"
            image.write_bytes(b"not decoded during dry run")
            output = base / "new output"
            process = subprocess.run([sys.executable, str(ROOT / "run_pipeline.py"),
                                      "--input-dir", str(raw), "--output-dir", str(output), "--dry-run"],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Dry run only", process.stdout)
            self.assertFalse(output.exists())
            self.assertEqual(image.read_bytes(), b"not decoded during dry run")
            command = runner.plan_commands(raw, output)[0][1]
            self.assertEqual(command[command.index("--input-dir") + 1], str(raw))

    def test_failed_validation_stops_later_steps_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            raw, source, output = base / "raw", base / "src", base / "run"
            raw.mkdir()
            source.mkdir()
            original = raw / "E16dm_CD_s1_img1_z01_ORG.tif"
            original.write_bytes(b"unchanged original")
            for name in runner.SCRIPT_NAMES:
                script = "print('stage executed')\n"
                if name == "validate_pipeline.py":
                    script += "raise SystemExit(7)\n"
                (source / name).write_text(script)
            args = argparse.Namespace(input_dir=raw, output_dir=output, limit=0,
                                      representative_only=False, dry_run=False)
            with patch.object(runner, "ROOT", base), patch.object(runner, "installed_versions", return_value={"python": sys.version.split()[0]}):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = runner.execute(args)
            self.assertEqual(code, 7)
            manifest = json.loads((output / "pipeline_run.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["failed_step"], "validate")
            self.assertEqual([step["name"] for step in manifest["steps"]], ["analyze", "validate"])
            self.assertEqual((output / "analyze_fibers.py").read_bytes(), (source / "analyze_fibers.py").read_bytes())
            self.assertEqual(original.read_bytes(), b"unchanged original")


if __name__ == "__main__":
    unittest.main()
