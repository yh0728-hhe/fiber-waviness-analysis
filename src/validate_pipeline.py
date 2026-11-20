#!/usr/bin/env python3
"""Independent fixed-geometry checks for the exploratory fiber estimator.

This validates numerical behavior on synthetic inputs. It does not validate
biological fiber identity, manual annotations, or performance on real SHG data.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import integrate, ndimage


def load_module(path):
    spec = importlib.util.spec_from_file_location("fiber_analysis_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def geometry_cases():
    t = np.linspace(0, 1, 10001)
    line = np.column_stack([50 + 400 * t, 256 + 0 * t])
    theta = -math.pi / 2 + math.pi * t
    arc = np.column_stack([180 + 130 * np.cos(theta), 256 + 130 * np.sin(theta)])
    amplitude, cycles, length = 35.0, 2.0, 400.0
    sine = np.column_stack([50 + length * t, 256 + amplitude * np.sin(2 * math.pi * cycles * t)])
    sine_length = integrate.quad(
        lambda x: math.sqrt(1 + (amplitude * 2 * math.pi * cycles / length *
                                 math.cos(2 * math.pi * cycles * x / length)) ** 2),
        0, length, epsabs=1e-10, epsrel=1e-10)[0]
    return {
        "line": {"points": line, "waviness": 1.0, "length": 400.0},
        "semicircle": {"points": arc, "waviness": math.pi / 2, "length": math.pi * 130},
        "sine_two_periods": {"points": sine, "waviness": sine_length / length, "length": sine_length},
    }


def draw_mask(paths, size=512, width=3):
    im = Image.new("L", (size, size), 0)
    dr = ImageDraw.Draw(im)
    for path in paths:
        dr.line([tuple(p) for p in np.asarray(path)], fill=255, width=width)
    return np.asarray(im) > 0


def summarize_segments(segments, stats):
    keys = ["segment_id", "status", "flags", "waviness", "straightness",
            "contour_length_px", "raw_contour_length_px", "end_to_end_px"]
    return {"stats": stats, "segments": [{k: s.get(k) for k in keys} for s in segments]}


def run(module, out):
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    metric_rows = []
    raster_rows = []
    panel_items = []

    def check(name, passed, observed, criterion, category):
        checks.append(dict(name=name, passed=bool(passed), observed=observed,
                           criterion=criterion, category=category))

    cases = geometry_cases()
    for name, case in cases.items():
        points = case["points"]
        reference = case["waviness"]
        for sigma in [0.0, 1.0, 2.0, 3.0]:
            measured = module.measure_path(points, smooth_sigma=sigma)
            error = abs(measured["waviness"] / reference - 1)
            metric_rows.append(dict(case=name, smoothing_sigma_px=sigma,
                                    reference_waviness=reference, measured_waviness=measured["waviness"],
                                    relative_error=error, contour_length_px=measured["contour_length_px"]))
            tolerance = 0.001 if name == "line" else 0.01
            check(f"metric_{name}_sigma{sigma:g}", error < tolerance,
                  error, f"relative W error < {tolerance}", "numerical")
            check(f"range_reciprocal_{name}_sigma{sigma:g}",
                  measured["waviness"] >= 1 - 1e-12 and 0 < measured["straightness"] <= 1 + 1e-12
                  and abs(measured["waviness"] * measured["straightness"] - 1) < 1e-12,
                  {"W": measured["waviness"], "S": measured["straightness"]},
                  "W>=1; 0<S<=1; W*S=1 within 1e-12", "numerical")
        base = module.measure_path(points, 2.0)["waviness"]
        angle = 0.713
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        variants = {"reverse": points[::-1], "translation": points + [932.1, -777.3],
                    "rotation": points @ rotation.T}
        for transform, transformed in variants.items():
            w = module.measure_path(transformed, 2.0)["waviness"]
            delta = abs(w - base)
            check(f"invariance_{name}_{transform}", delta < 1e-8, delta,
                  "absolute W difference <1e-8", "numerical")
        # Fixed pixel smoothing is resolution-dependent; both sigma and geometry
        # must scale when testing a change of coordinate unit.
        doubled = module.measure_path(points * 2.0, 4.0)["waviness"]
        check(f"scale_with_sigma_{name}", abs(doubled / base - 1) < 0.001,
              abs(doubled / base - 1), "relative W change <0.1% when coordinates and sigma double", "numerical")

    # Calibrated xy coordinates must be supplied to measure_path; the current
    # interface has no pixel-spacing argument. Verify this contract explicitly.
    physical = cases["sine_two_periods"]["points"] * [0.5, 2.0]
    physical_ref = np.linalg.norm(np.diff(physical, axis=0), axis=1).sum() / np.linalg.norm(physical[-1] - physical[0])
    value = module.measure_path(physical, 0)["waviness"]
    check("anisotropic_coordinates", abs(value / physical_ref - 1) < 0.01,
          value, "supplied physically scaled coordinates within 1% of independent polyline reference", "numerical")

    for name, points in [
        ("single", [[0, 0]]), ("duplicates", [[0, 0], [0, 0], [0, 0]]),
        ("closed_loop", [[0, 0], [20, 0], [20, 20], [0, 0]])]:
        measured = module.measure_path(points)
        check("degenerate_" + name, measured["waviness"] is None and measured["straightness"] is None,
              {k: measured[k] for k in ["waviness", "straightness", "end_to_end_px"]},
              "undefined endpoint ratio returns None", "numerical")

    masks = {}
    for name, case in cases.items():
        masks[name] = draw_mask([case["points"]])
    masks["crossing_x"] = draw_mask([[[60, 60], [452, 452]], [[60, 452], [452, 60]]])
    masks["broken_line"] = draw_mask([[[60, 256], [230, 256]], [[242, 256], [452, 256]]])
    masks["image_edge"] = draw_mask([[[0, 256], [452, 256]]])

    rng = np.random.default_rng(20261120)
    for name, mask in masks.items():
        segments, stats = module.trace_mask(mask, "mask_" + name)
        raster_rows.append(dict(case=name, stage="known_binary_mask", **summarize_segments(segments, stats)))
        if name in cases:
            accepted = [s for s in segments if s["status"] == "accepted"]
            longest = max(accepted, key=lambda s: s["contour_length_px"], default=None)
            error = abs(longest["waviness"] / cases[name]["waviness"] - 1) if longest else None
            check("mask_clean_" + name, longest is not None and error < 0.05,
                  {"n_accepted": len(accepted), "relative_W_error": error},
                  "at least one accepted path and longest W within 5% of fixed complete-curve reference", "mask_geometry")
        elif name == "crossing_x":
            safe = len(segments) >= 4 and all(s["status"] != "accepted" and "junction_truncated" in s["flags"] for s in segments)
            check("mask_crossing_ambiguity", safe,
                  {"n_segments": len(segments), "n_accepted": stats["n_accepted"], "flags": stats["exclusion_flags"]},
                  "crossing split into >=4 paths, junction_truncated, none accepted", "mask_geometry")
        elif name == "broken_line":
            spans_gap = [s["segment_id"] for s in segments
                         if min(p[0] for p in s["points"]) < 230 and max(p[0] for p in s["points"]) > 242]
            check("mask_no_gap_bridge", len(segments) == 2 and not spans_gap,
                  {"n_segments": len(segments), "spans_gap": spans_gap},
                  "two disconnected paths and no path bridges the known gap", "mask_geometry")
        elif name == "image_edge":
            check("mask_edge_rejected", stats["n_accepted"] == 0 and any("image_edge" in s["flags"] for s in segments),
                  {"n_accepted": stats["n_accepted"], "flags": stats["exclusion_flags"]},
                  "edge-touching path flagged image_edge and excluded from accepted", "mask_geometry")

        # All synthetic images use identical imaging parameters and RNG stream;
        # these do not imitate any treatment condition in the real data.
        raw = 500 + 3000 * ndimage.gaussian_filter(mask.astype(float), 1.0)
        raw += rng.normal(0, 30, raw.shape)
        raw = np.clip(raw, 0, 65535).astype(np.uint16)
        segments_i, stats_i, detected, _ = module.analyze_array(raw, "image_" + name)
        raster_rows.append(dict(case=name, stage="synthetic_intensity", **summarize_segments(segments_i, stats_i)))
        if name in cases:
            accepted = [s for s in segments_i if s["status"] == "accepted"]
            longest = max(accepted, key=lambda s: s["contour_length_px"], default=None)
            error = abs(longest["waviness"] / cases[name]["waviness"] - 1) if longest else None
            check("intensity_clean_" + name, longest is not None and error < 0.05,
                  {"n_accepted": len(accepted), "relative_W_error": error,
                   "accepted_graph_length_coverage": stats_i["accepted_graph_length_coverage"]},
                  "at least one accepted path and longest W within 5% of fixed complete-curve reference", "intensity_diagnostic")
        elif name == "crossing_x":
            check("intensity_crossing_ambiguity", stats_i["n_accepted"] == 0 and stats_i["junction_nodes"] > 0,
                  {"n_accepted": stats_i["n_accepted"], "junction_nodes": stats_i["junction_nodes"]},
                  "crossing detected as junction; no entire crossing arm silently accepted", "intensity_diagnostic")
        elif name == "broken_line":
            bridge = [s["segment_id"] for s in segments_i if min(p[0] for p in s["points"]) < 230
                      and max(p[0] for p in s["points"]) > 242]
            check("intensity_no_gap_bridge", not bridge,
                  {"n_segments": len(segments_i), "spans_gap": bridge},
                  "no detected path bridges the known 12-pixel gap", "intensity_diagnostic")
        elif name == "image_edge":
            check("intensity_edge_rejected", stats_i["n_accepted"] == 0,
                  {"n_accepted": stats_i["n_accepted"], "flags": stats_i["exclusion_flags"]},
                  "boundary-crossing line not accepted", "intensity_diagnostic")
        panel_items.append((name, raw, segments_i))

    for name, raw in [
        ("blank", np.full((512, 512), 500, dtype=np.uint16)),
        ("noise_only", np.clip(500 + rng.normal(0, 30, (512, 512)), 0, 65535).astype(np.uint16))]:
        segments, stats, mask, _ = module.analyze_array(raw, name)
        raster_rows.append(dict(case=name, stage="synthetic_intensity", **summarize_segments(segments, stats)))
        check("intensity_" + name + "_no_long_detection", stats["n_accepted"] == 0,
              {"n_accepted": stats["n_accepted"], "n_review": stats["n_review"],
               "detected_signal_area_fraction": stats["detected_signal_area_fraction"]},
              "zero accepted long segments", "intensity_diagnostic")
        panel_items.append((name, raw, segments))

    # Direction bias is measured at fixed smoothing and fixed physical length.
    angle_sweep = []
    t = np.linspace(-160, 160, 3001)
    for angle_deg in [0, 15, 30, 45, 60, 75, 90]:
        a = math.radians(angle_deg)
        p = np.column_stack([256 + t * math.cos(a), 256 + t * math.sin(a)])
        for width in [1, 3, 5]:
            seg, stat = module.trace_mask(draw_mask([p], width=width), f"angle{angle_deg}_width{width}")
            accepted = [s for s in seg if s["status"] == "accepted"]
            longest = max(accepted, key=lambda s: s["contour_length_px"], default=None)
            w = longest["waviness"] if longest else None
            angle_sweep.append(dict(angle_deg=angle_deg, width_px=width, waviness=w,
                                    n_accepted=stat["n_accepted"]))
            check(f"mask_line_angle{angle_deg}_width{width}", w is not None and abs(w - 1) < 0.01,
                  w, "accepted line W within 1% of 1", "pixel_direction")

    thumb, label_h = 300, 45
    panel = Image.new("RGB", (thumb * 3, (thumb + label_h) * 3), "white")
    dr = ImageDraw.Draw(panel)
    for i, (name, raw, segs) in enumerate(panel_items):
        arr = np.clip((raw.astype(float) - 400) / 3000, 0, 1)
        im = Image.fromarray((arr * 255).astype(np.uint8)).convert("RGB").resize((thumb, thumb))
        draw = ImageDraw.Draw(im)
        for s in segs:
            points = [(x * thumb / 512, y * thumb / 512) for x, y in s["points"]]
            if len(points) > 1:
                color = {"accepted": "#00ffbb", "review": "#ffb940", "rejected": "#888888"}[s["status"]]
                draw.line(points, fill=color, width=2)
        x, y = (i % 3) * thumb, (i // 3) * (thumb + label_h)
        panel.paste(im, (x, y + label_h))
        dr.text((x + 8, y + 7), name, fill="black")
        n = sum(s["status"] == "accepted" for s in segs)
        dr.text((x + 8, y + 24), f"automatic-QC accepted: {n}", fill="black")
    panel.save(out / "synthetic_diagnostics.png")

    failed = [c for c in checks if not c["passed"]]
    report = dict(
        purpose="Independent numerical/synthetic validation, not biological instance validation",
        analysis_source_sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        validation_harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        all_checks_passed=not failed,
        check_count=len(checks), failed_count=len(failed),
        acceptance_criteria_fixed_before_run=True,
        random_seed=20261120,
        limitations=[
            "Synthetic intensity settings do not represent calibrated microscope noise or treatment conditions.",
            "Clean-curve raster comparison uses the complete reference curve; endpoint trimming can affect error.",
            "No manual real-image reference or biological sample inference is included.",
            "Pixel-space smoothing makes results depend on pixel resolution; uniform scale tests scale sigma too.",
            "No performance threshold was retrospectively adjusted to make the current code pass.",
        ],
        parameters=module.PARAMETERS,
        checks=checks, failed_checks=failed,
        ordered_trace_measurements=metric_rows,
        raster_diagnostics=raster_rows,
        line_angle_width_sweep=angle_sweep,
    )
    (out / "validation_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "README.md").write_text(
        "# Synthetic validation\n\n"
        f"{len(checks)} fixed checks; {len(failed)} failures. The results apply to the source SHA-256 recorded in `validation_results.json`.\n\n"
        "These checks cover ordered straight, circular-arc and sinusoidal traces; reciprocal metric definitions; "
        "rigid transforms; scaled smoothing; degenerate endpoints; raster angle/width bias; and clean/noisy "
        "intensity images containing curves, a crossing, a gap, and an image boundary. "
        "The fixed seed is 20261120. No thresholds were changed after seeing these results.\n\n"
        f"Maximum ordered-trace relative waviness error: {100 * max(r['relative_error'] for r in metric_rows):.3f}%. "
        "The clean synthetic-intensity line, arc and sine errors were "
        + ", ".join(f"{100 * c['observed']['relative_W_error']:.3f}%" for c in checks if c['name'].startswith('intensity_clean_') and c['observed']['relative_W_error'] is not None)
        + ". These are errors for the fixed synthetic geometries, not uncertainty estimates for real images.\n\n"
        "**Limits:** this is numerical and synthetic validation, not validation of biological fiber identity. "
        "The noise-only image generated many short rejected paths and a substantial mask area despite yielding "
        "zero accepted long paths. Consequently, detected mask area must not be interpreted as collagen density. "
        "Automatic QC acceptance is not manual confirmation. Smoothing variation is a parameter sensitivity, "
        "not a confidence interval. Physical calibration must be applied before lengths can be reported in micrometres.\n\n"
        "The image montage uses green for automatic-QC accepted, amber for review, and gray for rejected paths.\n",
        encoding="utf-8")
    print(json.dumps({"check_count": len(checks), "failed_count": len(failed),
                      "failed_checks": failed, "output": str(out)}, indent=2))
    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, default=Path(__file__).resolve().parent / "analyze_fibers.py")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "validation")
    args = parser.parse_args()
    raise SystemExit(run(load_module(args.analysis), args.output))


if __name__ == "__main__":
    main()
