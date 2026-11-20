# Professor overview

This project is an **exploratory prototype for measuring collagen waviness in SHG images**. It produces inspectable candidate paths and consistent numerical measurements. The paths have not been independently confirmed as complete collagen fibers, and the current results do not establish a biological difference between CD and DMSO.

## Research question and measurement

The immediate goal is to automate a measurement that otherwise requires tracing individual fibers:

\[
W = \frac{L_{\mathrm{contour}}}{D_{\mathrm{endpoints}}},
\qquad
S = \frac{D_{\mathrm{endpoints}}}{L_{\mathrm{contour}}} = \frac{1}{W}.
\]

Here, **waviness** is `W >= 1`; **straightness** is `0 < S <= 1`. A straight path has both values equal to 1. The reciprocal relationship applies to each path; the reciprocal of mean straightness is not mean waviness.

This version measures smoothed **2D path segments in individual TIFF slices**, in pixel coordinates. A broken or shortened path can have a different waviness from the complete fiber, even when both calculations are numerically correct.

## What has been completed

- Processed **68 TIFF slices from 7 imaging fields**: 43 slices labeled CD and 25 labeled DMSO in the filenames. CZI files and CA images are outside this analysis.
- Detected 100,960 candidate graph paths: **1,592 passed automatic QC**, 11,362 require review, and 88,006 were rejected.
- Saved per-path measurements, per-image diagnostics, overlays, and an offline review interface.
- Completed 75 software checks and an independent arithmetic audit. Neither provides biological validation.

“Automatic QC” means the path satisfies declared length, endpoint-distance, boundary, and graph-topology rules. It does **not** mean an expert has accepted the path as a real fiber.

Fragmentation remains substantial. The median accepted length divided by detected skeleton-graph length is **8.96% across slices**. This is an algorithmic coverage diagnostic, not true-fiber recall. One weak field, `DMSO_s1_img1`, yielded only **3 accepted segments across 7 slices**, with only 3 slices contributing a waviness summary. Low yield does not imply low collagen abundance or low waviness.

## Five-minute review

1. **One minute:** inspect the [overview figure](../results/overview.png). Read tracing yield and graph coverage alongside the selected-segment waviness summaries. The plotted slice ranges are not confidence intervals.
2. **Two minutes:** download and open the [offline review interface](https://github.com/yh0728-hhe/fiber-waviness-analysis/releases/download/v0.1.0/review.html) locally. Inspect several green, amber, and gray paths against the underlying image. Green means automatic QC passed; amber means review; gray means rejected. Check whether a path follows one fiber, whether it stops early, and whether an apparent crossing makes its identity ambiguous.
3. **One minute:** examine the [accepted-path table](../results/auto_qc_segments.csv) and [per-image diagnostics](../results/images.csv). These contain candidate-segment measurements rather than a count of independent fibers or specimens.
4. **One minute:** read [what validation establishes](VALIDATION.md), especially smoothing dependence and the absence of an independent manual reference.

The [main README](../README.md) describes setup, repository contents, and reproduction.

## The next decision

The next milestone is a **small, blinded manual-reference study**, before interpreting condition differences or training a more complex model. It should use a predefined selection spanning both conditions, weak and strong signals, crossings, and image boundaries. For each selected path, agree on fiber identity, endpoints, inclusion rules, and the measurement convention before comparing numerical waviness. Record missed fibers and incorrect paths as well as errors on correctly matched paths.

Manual and automatic traces must use a consistent length estimator. The review interface's hand-drawn `L/D` is an unsmoothed polyline measurement; the automatic output uses smoothing. Their difference is not solely segmentation error.

The experimental metadata needed next are specimen identities and independence, treatment records, coverslip/mounting conditions, XY pixel calibration, Z spacing, and acquisition/preprocessing details. Adjacent slices can show the same fiber; fields and slices from the same specimen must remain grouped in any validation or training split. The current summaries cannot support specimen-level statistical inference.
