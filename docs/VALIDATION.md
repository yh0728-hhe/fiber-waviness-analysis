# Validation and limits of certainty

The current evidence supports the **defined numerical calculation and the internal consistency of the saved results**. It does not establish that the automated paths identify complete collagen fibers or represent the tissue without selection bias. Independent manual validation is still outstanding.

## What the 75 checks mean

The [validation results](../results/validation/validation_results.json) contain 75 predefined software assertions:

| Category | Count | What is checked |
|---|---:|---|
| Numerical | 40 | Known ordered curves, reciprocal metrics, transformations, scaled smoothing, and degenerate endpoints |
| Binary geometry | 6 | Clean paths, crossing ambiguity, a disconnected gap, and boundary exclusion |
| Synthetic intensity | 8 | Curve detection, crossing/gap/boundary behavior, blank images, and a fixed noise realization |
| Pixel direction and width | 21 | Straight raster lines at seven angles and three widths |

All 75 passed for the recorded code and parameter versions. They are repeated assertions on a limited set of constructed cases, **not 75 independent biological validations**. The [synthetic image montage](../results/validation/synthetic_diagnostics.png) makes the tested situations visible. The checks are reproducible with [validate_pipeline.py](../src/validate_pipeline.py).

On the original clean synthetic intensity examples, waviness errors were approximately **0.072% for a straight line, 0.223% for a circular arc, and 0.787% for a sinusoid**. These values describe those examples and must not be presented as accuracy estimates for real SHG images.

The crossing was split into paths requiring review, the disconnected gap was not bridged, and the boundary-crossing path was excluded. The fixed noise-only image yielded no accepted long paths, but it still produced many rejected paths and **36.9% detected mask area**. Therefore, detected mask area is an algorithm response and cannot be interpreted as collagen density.

## Independent accounting and analytic audit

The [audit results](../results/validation/audit_results.json) and [audit script](../src/audit_pipeline.py) provide a separate check of the saved outputs:

- All 100,960 candidate-path rows satisfy the recorded length/endpoint-ratio arithmetic, where defined. The maximum numerical discrepancy in `W*S` from 1 was `2.22e-16`.
- Four undefined endpoint ratios are excluded from automatic acceptance.
- Image and segment identifiers, status counts, the 1,592-row accepted subset, and image/field/filename-sample summaries reconcile.
- Recorded source hashes identify the versions to which the checks apply.

These checks use saved measurements. They do not independently reconstruct the paths from raw microscopy data. The saved display coordinates are downsampled and are not an exact substitute for the full-resolution contour used for length calculation.

## Smoothing changes the measurement

The [analysis implementation](../src/analyze_fibers.py) resamples ordered paths at approximately one-pixel arc-length spacing, smooths with a default Gaussian sigma of 2 pixels, and preserves the original endpoints. This reduces pixel-scale jaggedness but can also remove real short-scale curvature.

The expanded audit uses the explicitly defined curve

\[
y(x)=8\sin(2\pi x/T),\qquad 0\leq x\leq200,
\]

with coordinates in pixels, periods `T = 100, 40, 10` pixels, and smoothing sigma `0, 1, 2, 3` pixels. Reference arc length is calculated using a complete elliptic integral and cross-checked by dense integration of `sqrt(1 + (dy/dx)^2)`.

At the default sigma of 2 pixels, the estimated waviness is **1.57% below the reference for a 40-pixel period** and **13.4% below it for a 10-pixel period**. The latter is a deliberately tight geometric stress test, not a claim about the curvature of the supplied fibers. These additional tests report bias without introducing a new pass/fail threshold. They show why subpercent errors on a few clean examples cannot be generalized to every curvature scale.

The saved sigma-1 and sigma-3 estimates are parameter-sensitivity diagnostics, not confidence intervals. Pixel-space smoothing also makes physical calibration relevant when comparing images acquired at different resolutions.

## What remains to be validated

The current pipeline deliberately avoids reconnecting paths across detected junctions or gaps. That conservatism limits incorrect connections but also fragments real fibers and changes endpoints. Low graph coverage, brightness differences, network density, and the minimum-length rule can change which paths enter a summary. The accepted subset is therefore not established as a representative sample of the collagen network.

A useful next validation should:

1. Define whether the target is a complete visible fiber or a segment with explicitly chosen endpoints, including rules for crossings, gaps, and boundaries.
2. Select reference regions across conditions and image qualities using a predefined, blinded protocol; retain specimen, field, and slice identifiers.
3. Obtain independent manual traces and reconcile ambiguous identities. Keep manual-reference selection separate from algorithm tuning.
4. Measure detection/identity errors separately from waviness error on correctly matched paths. Apply the same declared smoothing and endpoint convention to the traces being compared.
5. Establish acceptable error and coverage requirements before using results for condition comparisons. Split training and evaluation by confirmed specimen, with its fields and adjacent slices kept together.

No biological CD/DMSO conclusion or specimen-level significance test is supported by the present software checks. Start with the [professor overview](PROFESSOR_OVERVIEW.md) for a short review path and the metadata needed to make the next study interpretable.
