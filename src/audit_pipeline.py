#!/usr/bin/env python3
"""Read-only arithmetic audit plus independent analytic smoothing diagnostics.

Run from any directory with: python /path/to/package/audit_pipeline.py
Only validation/audit_results.json is written. No analysis data are changed.
The analytic stress tests report bias without imposing new pass/fail thresholds.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.special import ellipe


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(base, output, source_dir=None):
    source_dir = Path(source_dir).resolve() if source_dir is not None else base
    segments = read_csv(base / "segments.csv")
    images = read_csv(base / "images.csv")
    accepted = read_csv(base / "auto_qc_segments.csv")
    series = read_csv(base / "series_summary.csv")
    samples = read_csv(base / "sample_id_summary.csv")
    validation = json.loads((base / "validation" / "validation_results.json").read_text())
    summary = json.loads((base / "run_summary.json").read_text())
    failures = []

    def require(condition, label, detail=None):
        if not condition:
            failures.append({"check": label, "detail": detail})

    hashes = {}
    for filename, field in [("analyze_fibers.py", "analysis_source_sha256"),
                            ("validate_pipeline.py", "validation_harness_sha256")]:
        observed = sha256(source_dir / filename)
        hashes[filename] = {"recorded_in_validation": validation[field],
                            "current": observed, "matches": validation[field] == observed}
        require(hashes[filename]["matches"], "validation_source_hash", filename)
    require(validation["check_count"] == len(validation["checks"]), "validation_check_count")
    require(validation["failed_count"] == sum(not check["passed"] for check in validation["checks"]),
            "validation_failed_count")

    counts = collections.Counter(row["status"] for row in segments)
    require({status: counts[status] for status in ["accepted", "review", "rejected"]} == summary["counts"], "summary_status_counts")
    require(len(segments) == sum(int(row["n_segments"]) for row in images), "total_candidate_count")
    require(len(images) == summary["n_images"], "summary_image_count")
    require(len(series) == summary["n_fields"], "summary_field_count")
    require(len({row["segment_id"] for row in segments}) == len(segments), "unique_segment_ids")
    require(len({row["image_id"] for row in images}) == len(images), "unique_image_ids")
    require(accepted == [row for row in segments if row["status"] == "accepted"], "exact_accepted_subset")

    maximum_errors = {"W_from_L_over_D": 0.0, "S_from_D_over_L": 0.0,
                      "W_times_S_minus_1": 0.0, "raw_W_from_raw_L_over_D": 0.0}
    by_image = collections.defaultdict(list)
    undefined_count = 0
    for row in segments:
        by_image[row["image_id"]].append(row)
        length, distance, raw_length = [float(row[key]) for key in
                                       ["contour_length_px", "end_to_end_px", "raw_contour_length_px"]]
        if row["waviness"]:
            w, s, raw_w = [float(row[key]) for key in ["waviness", "straightness", "raw_waviness"]]
            errors = {"W_from_L_over_D": abs(w - length / distance),
                      "S_from_D_over_L": abs(s - distance / length),
                      "W_times_S_minus_1": abs(w * s - 1),
                      "raw_W_from_raw_L_over_D": abs(raw_w - raw_length / distance)}
            for key, error in errors.items():
                maximum_errors[key] = max(maximum_errors[key], error)
            require(all(math.isfinite(value) for value in [length, distance, raw_length, w, s, raw_w]),
                    "finite_metrics", row["segment_id"])
            require(w >= 1 - 1e-12 and 0 < s <= 1 + 1e-12, "metric_ranges", row["segment_id"])
            require(max(errors.values()) < 1e-12, "metric_arithmetic", row["segment_id"])
        else:
            undefined_count += 1
            require(distance <= 1e-8 and row["status"] != "accepted", "undefined_ratio_exclusion", row["segment_id"])
        if row["status"] == "accepted":
            require(length >= 80 and distance >= 10 and not row["flags"], "accepted_QC_rules", row["segment_id"])

    require(set(by_image) <= {row["image_id"] for row in images}, "segment_parent_images")
    for image in images:
        rows = by_image[image["image_id"]]
        counts_i = collections.Counter(row["status"] for row in rows)
        require(len(rows) == int(image["n_segments"]), "image_candidate_count", image["image_id"])
        for status in ["accepted", "review", "rejected"]:
            require(counts_i[status] == int(image["n_" + status]), "image_status_count", [image["image_id"], status])
        selected = [row for row in rows if row["status"] == "accepted"]
        if selected:
            values = [float(row["waviness"]) for row in selected]
            expected = {"median_waviness": float(np.median(values)), "mean_waviness": float(np.mean(values)),
                        "median_contour_px": float(np.median([float(row["contour_length_px"]) for row in selected]))}
            for field, value in expected.items():
                require(abs(float(image[field]) - value) < 1e-12, "image_summary", [image["image_id"], field])
            coverage = sum(float(row["raw_contour_length_px"]) for row in selected) / float(image["detected_graph_length_px"])
            require(abs(float(image["accepted_graph_length_coverage"]) - coverage) < 1e-12,
                    "image_length_coverage", image["image_id"])
        else:
            require(not image["median_waviness"] and not image["mean_waviness"], "empty_image_summary", image["image_id"])

    for row in series:
        image_group = [image for image in images if image["series_id"] == row["series_id"]]
        medians = [float(image["median_waviness"]) for image in image_group if image["median_waviness"]]
        require(len(image_group) == int(row["n_slices"]), "field_slice_count", row["series_id"])
        require(sum(int(image["n_accepted"]) for image in image_group) == int(row["n_auto_qc_segments_across_slices"]),
                "field_accepted_count", row["series_id"])
        if medians:
            require(abs(float(np.median(medians)) - float(row["median_of_slice_median_waviness"])) < 1e-12,
                    "field_summary_median", row["series_id"])
    for row in samples:
        medians = [float(field["median_of_slice_median_waviness"]) for field in series
                   if field["condition"] == row["condition"] and field["sample_id"] == row["filename_sample_id"]
                   and field["median_of_slice_median_waviness"]]
        if medians:
            require(abs(float(np.median(medians)) - float(row["median_of_field_summaries"])) < 1e-12,
                    "filename_sample_summary", [row["condition"], row["filename_sample_id"]])

    spec = importlib.util.spec_from_file_location("fiber_module_for_independent_audit", source_dir / "analyze_fibers.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    diagnostics = []
    for radius in [20.0, 40.0, 100.0]:
        for angle in [math.pi / 2, math.pi, 3 * math.pi / 2]:
            theta = np.linspace(0, angle, 16001)
            points = np.column_stack([radius * np.cos(theta), radius * np.sin(theta)])
            reference = angle / (2 * math.sin(angle / 2))
            measured = module.measure_path(points, smooth_sigma=2.0)["waviness"]
            diagnostics.append(dict(shape="circular_arc", radius_px=radius, angle_rad=angle,
                                    smoothing_sigma_px=2.0, reference_waviness=reference,
                                    measured_waviness=measured, signed_relative_error=measured / reference - 1))

    # Every domain contains an integer number of periods. The closed-form mean
    # arc length uses the complete elliptic integral of the second kind E(m):
    # W=(2/pi)*sqrt(1+b^2)*E(b^2/(1+b^2)), b=2*pi*A/T.
    # A dense independent trapezoidal derivative integral cross-checks this.
    for period in [100.0, 40.0, 10.0]:
        amplitude, domain = 8.0, 200.0
        x = np.linspace(0, domain, 200001)
        y = amplitude * np.sin(2 * math.pi * x / period)
        slope_amplitude = 2 * math.pi * amplitude / period
        reference = 2 / math.pi * math.sqrt(1 + slope_amplitude**2) * ellipe(slope_amplitude**2 / (1 + slope_amplitude**2))
        dense_reference = np.trapezoid(np.sqrt(1 + (slope_amplitude * np.cos(2 * math.pi * x / period))**2), x) / domain
        for sigma in [0.0, 1.0, 2.0, 3.0]:
            measured = module.measure_path(np.column_stack([x, y]), smooth_sigma=sigma)["waviness"]
            diagnostics.append(dict(shape="sinusoid", amplitude_px=amplitude, period_px=period,
                                    x_domain_px=[0.0, domain], full_period_count=domain / period,
                                    smoothing_sigma_px=sigma, reference_waviness=float(reference),
                                    dense_integral_reference_waviness=float(dense_reference),
                                    reference_method_disagreement=float(dense_reference - reference),
                                    measured_waviness=measured, signed_relative_error=measured / reference - 1))

    coverage = float(np.median([float(image["accepted_graph_length_coverage"]) for image in images]))
    require(abs(coverage - summary["median_algorithmic_length_coverage"]) < 1e-12, "coverage_summary")
    report = dict(
        purpose="Independent arithmetic/accounting audit plus analytic smoothing stress tests; no biological validation",
        internal_consistency_passed=not failures, internal_consistency_failures=failures,
        biological_validation_completed=False,
        audit_script_sha256=sha256(Path(__file__).resolve()), validation_source_hashes=hashes,
        saved_validation_check_count=validation["check_count"],
        saved_validation_failed_count=validation["failed_count"],
        saved_validation_categories=dict(collections.Counter(check["category"] for check in validation["checks"])),
        n_candidate_paths=len(segments), n_images=len(images), n_fields=len(series), status_counts=dict(counts),
        n_undefined_ratios=undefined_count, metric_maximum_absolute_errors=maximum_errors,
        median_algorithmic_graph_length_coverage=coverage,
        audited_file_sha256={name: sha256(base / name) for name in ["segments.csv", "auto_qc_segments.csv", "images.csv", "series_summary.csv", "sample_id_summary.csv"]},
        metric_definitions={"W": "Gaussian-smoothed, approximately 1-pixel-resampled 2D centerline arc length / original endpoint distance",
                            "S": "endpoint distance / smoothed arc length = 1/W",
                            "raw_W": "unsmoothed polyline arc length / endpoint distance"},
        analytic_stress_test_definitions={
            "arcs": "R in {20,40,100} pixels; angle in {pi/2,pi,3pi/2}; W=angle/[2*sin(angle/2)]; 16001 ordered points; sigma=2 pixels",
            "sines": "y(x)=8*sin(2*pi*x/T) pixels, x from 0 to 200 pixels; T in {100,40,10} pixels; 200001 ordered points; sigma in {0,1,2,3} pixels",
            "sine_reference": "Closed-form complete-elliptic-integral arc length, cross-checked with dense trapezoidal integration of sqrt(1+(dy/dx)^2)",
            "signed_relative_error": "measured_W/reference_W-1; negative values mean underestimation",
            "decision_rule": "Diagnostic values only. No new pass/fail threshold is applied to these extra analytic stress tests."},
        additional_analytic_stress_tests=diagnostics,
        limitations=[
            "The 75 saved checks are repeated numerical/synthetic assertions, not independent biological validations.",
            "No independent manual ground truth or complete-fiber identity validation is included.",
            "The stress tests demonstrate that subpercent errors on a few clean examples do not generalize to all curvature scales.",
            "A 10-pixel-period, 8-pixel-amplitude sinusoid is a deliberately tight geometric stress test, not a claim about real fibers.",
            "CSV arithmetic checks do not reconstruct contours from raw microscopy images.",
            "The saved display paths are downsampled; they do not reproduce the exact full-resolution arc-length computation.",
            "Automatic-QC accepted paths cover a selected portion of detected skeleton length; this is not biological recall.",
        ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tight = [row for row in diagnostics if row["shape"] == "sinusoid" and row["period_px"] == 10 and row["smoothing_sigma_px"] == 2][0]
    print(json.dumps({"output": str(output), "internal_consistency_passed": not failures,
                      "n_failures": len(failures), "source_hashes_match": all(row["matches"] for row in hashes.values()),
                      "tight_sine_signed_relative_error": tight["signed_relative_error"]}, indent=2))
    return 0 if not failures else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--source-dir", type=Path, help="Canonical code directory; defaults to --base for staged runs")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = args.base.resolve()
    raise SystemExit(run(base, args.output or base / "validation" / "audit_results.json", args.source_dir))


if __name__ == "__main__":
    main()
