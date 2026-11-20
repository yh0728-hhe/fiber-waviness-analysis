#!/usr/bin/env python3
"""Exercise all five pipeline stages on disposable synthetic TIFFs.

Run after installing requirements: python tests/smoke_pipeline.py
No microscopy data, supplied results, or public service is used or modified.
Temporary inputs/results are removed after a successful check.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="fiber_pipeline_smoke_") as directory:
        base = Path(directory)
        raw, output = base / "original_tiffs", base / "run"
        raw.mkdir()
        for z in [1, 2]:
            image = Image.new("I", (512, 512), 1000)
            draw = ImageDraw.Draw(image)
            points = [(int(x), int(100 + 18*np.sin(x/45))) for x in range(55, 455)]
            draw.line(points, fill=45000, width=5)
            draw.line([(90, 230), (143, 230)], fill=45000, width=5)
            draw.line([(220, 330), (242, 330)], fill=45000, width=5)
            draw.line([(300, 360), (410, 360)], fill=45000, width=5)
            draw.line([(355, 305), (355, 415)], fill=45000, width=5)
            image = Image.fromarray(np.asarray(image).astype(np.uint16))
            image.save(raw / f"E16dm_CD_s1_img1_z{z:02d}_ORG.tif")
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob("*.tif")}
        process = subprocess.run([sys.executable, str(ROOT / "run_pipeline.py"),
                                  "--input-dir", str(raw), "--output-dir", str(output)], check=False)
        if process.returncode:
            raise SystemExit(f"Full pipeline smoke failed with return code {process.returncode}")
        manifest = json.loads((output / "pipeline_run.json").read_text())
        data = json.loads((output / "report_data.json").read_text())
        validation = json.loads((output / "validation/validation_results.json").read_text())
        audit = json.loads((output / "validation/audit_results.json").read_text())
        assert manifest["status"] == "complete"
        assert len(manifest["steps"]) == 5
        assert len(data["images"]) == 2
        assert validation["all_checks_passed"]
        assert audit["internal_consistency_passed"]
        assert (output / "review.html").stat().st_size > 1000
        assert (output / "overview.png").stat().st_size > 1000
        assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob("*.tif")}
        text = (output / "READ_ME_RESULTS_AND_METHODS.txt").read_text()
        assert "2 single-slice TIFFs from 1 image field" in text
        assert "68 slices" not in text and "43 CD and 25 DMSO" not in text
        print(json.dumps({"full_pipeline_smoke": "passed", "images": 2,
                          "synthetic_checks": validation["check_count"],
                          "audit_consistent": True, "original_tiffs_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
