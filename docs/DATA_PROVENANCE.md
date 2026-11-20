# Data provenance and scope

This project contains an exploratory analysis of user-supplied microscopy images. It is a software and tracing-quality prototype. Its saved results are not expert-validated measurements of complete collagen fibers and do not establish a CD-versus-DMSO biological effect.

## Original input

The input was supplied as:

- Archive: `Fiber Straightness Training Data-20261120T042849Z-1-001.zip`
- Archive size: 91,416,213 bytes
- SHA-256: `f17bff430ea6365a956b2fbbc1d05c69f181890ba14e0bbfedf9fd55306f0b04`
- Contents: 79 files, totaling 97,381,558 uncompressed bytes: 68 TIFF images, 8 CZI images, and 3 `Thumbs.db` files.

Only the 68 TIFF images were analyzed. They are single-frame, 8-bit grayscale exports in seven image-series folders. The analysis treated each TIFF as one 2D slice; it did not reconstruct a 3D volume or combine slices into a maximum-intensity projection.

| Filename series | Slices | TIFF dimensions, pixels | Filename sample ID |
| --- | ---: | ---: | --- |
| `E16dm_CD_s5_img1` | 8 | 2048 × 2048 | `s5` |
| `E16dm_CD_s5_img2` | 11 | 2048 × 2048 | `s5` |
| `E16dm_CD_s6_img1` | 11 | 2048 × 2048 | `s6` |
| `E16dm_CD_s6_img2` | 13 | 2048 × 2048 | `s6` |
| `E16dm_DMSO_s1_img1` | 7 | 2032 × 2024 | `s1` |
| `E16dm_DMSO_s1_img2v2` | 10 | 2006 × 2040 | `s1` |
| `E16dm_DMSO_s2_img2` | 8 | 2025 × 2042 | `s2` |

The labels `CD`, `DMSO`, `E16dm`, and sample/field identifiers are taken from filenames. The project has no independent experimental sample key confirming their biological interpretation, coverslip conditions, specimen identities, or independence. Adjacent slices and fields sharing a filename sample ID must not be counted as independent biological replicates.

The eight CZI files have separate `Control`/`Ski` filenames. They were not assigned to the TIFF conditions, analyzed, or used to calibrate the TIFFs. No CA-labeled dataset was included in this analysis.

## Calibration

The TIFF metadata inspected for this project did not provide verified microscopy pixel sizes or Z spacing. Their 300 dpi export tags are not used as tissue calibration. All reported lengths use image pixels and assume equal X and Y spacing. Physical length thresholds, comparability of physical scales across fields, and 3D waviness remain unverified. Calibration from a differently named CZI image must not be transferred to the TIFF series.

## Included analysis artifacts

The saved English analysis snapshot includes:

- Per-image and per-path numerical tables, parameter settings, source TIFF hashes, technical summaries, and display coordinates.
- 68 contrast-enhanced JPEG previews derived from the source TIFFs, 68 tracing overlays, and 68 binary masks.
- An offline HTML reviewer with seven embedded central-slice previews, one from each image field. These are a subset of the 68 analyzed slices.
- Summary figures, numerical/synthetic test records, and a consistency audit.

These artifacts include laboratory image content and derived data even though the original TIFFs are absent. The previews are downscaled and contrast-adjusted for display; they are not replacement raw inputs for reproducing the numerical analysis. Display trace coordinates are subsampled and do not reproduce the exact full smoothed contour-length calculation.

The snapshot records 100,960 candidate graph paths: 1,592 pass automatic geometric filters, 11,362 require review, and 88,006 are excluded. These are repeated 2D observations, not counts of unique biological fibers. Passing the filters is not expert confirmation. No independent manual reference traces or biological ground-truth dataset were supplied with the archive.

Manual decisions or polylines subsequently created in the reviewer are separate annotations. They do not automatically become expert ground truth or alter the original automatic summaries. Export them explicitly if they need to be shared or retained.

## Not packaged

The default project does not package the original training ZIP, original TIFF/CZI files, email screenshots, personal correspondence, the thesis or journal-paper PDFs, temporary working directories, or installed Python dependencies. The archive's `Thumbs.db` files are also omitted.

Literature is referenced for method context. The prototype is not a replication of the thesis's projection-based, semi-manual experiment or of the separate intestinal-looping simulation project.

## Reproduction and access

Recomputing the microscopy results requires the original TIFF inputs from the archive above, obtained separately through the appropriate data holder. A repository clone and the JPEG previews alone are insufficient. Extract the original input locally, verify the archive and TIFF hashes, and write new analysis outputs to a separate directory so the saved snapshot remains available for comparison. Numerical and synthetic tests do not require the original microscopy images.

The pinned numerical dependencies require Python 3.12 or newer; this analysis was run with Python 3.12.14. Use the repository's current command instructions for selecting input, output, and snapshot directories.

The archive basename and SHA-256 identify the source without requiring a workstation-specific absolute path. Filename identifiers have been retained so outputs can be reconciled with the original input.

## Sharing and licensing scope

Original laboratory data and their derivatives retain their existing ownership and reuse terms. This repository does not assign a new data or software license. Raw microscopy inputs, correspondence, screenshots, and thesis files are not redistributed.

## Git repository storage

The public Git repository contains code, documentation, compact summary tables, validation records, all 68 image-derived preview/overlay/mask sets, and a compact standalone reviewer. The full candidate CSV and coordinate JSON are stored as lossless `.gz` files. Run `python unpack_snapshot.py` to restore their exact original bytes and verify SHA-256 values. The complete repository can be downloaded using Code → Download ZIP. A smaller quick-review ZIP is available under downloads/. Original raw microscopy, correspondence, screenshots, and thesis files are excluded.
