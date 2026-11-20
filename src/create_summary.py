#!/usr/bin/env python3
"""Create plots and a plain-text interpretation from the saved first-pass results."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw


def main(base=None):
    base = Path(base).resolve() if base is not None else Path(__file__).resolve().parent
    data = json.loads((base/'report_data.json').read_text())
    images, series = data['images'], data['series_summary']
    if not images or not series:
        raise ValueError('No analyzed images/series are available for a summary.')
    colors = {'CD':'#148a83','DMSO':'#7362aa'}
    rows = list(reversed(series))
    fig, axes = plt.subplots(1,3, figsize=(15,6.5), sharey=True, gridspec_kw={'width_ratios':[1.3,1.2,1]})
    y = np.arange(len(rows))
    for i,r in enumerate(rows):
        c=colors.get(r['condition'],'#165d86')
        v=r['median_of_slice_median_waviness']
        if v is not None and r['n_auto_qc_segments_across_slices'] >= 10:
            axes[0].plot([r['min_slice_median_waviness'],r['max_slice_median_waviness']],[i,i],color=c,lw=2)
            axes[0].scatter([v],[i],c=c,s=55,zorder=3)
        else:
            axes[0].text(1.015,i,f"Low yield: {r['n_auto_qc_segments_across_slices']} paths",va='center',fontsize=9,color='#666666')
        ims=[im for im in images if im['series_id']==r['series_id']]
        counts=[im['statistics']['n_accepted'] for im in ims]
        cover=[100*im['statistics']['accepted_graph_length_coverage'] for im in ims]
        axes[1].scatter(counts,[i]*len(counts),color=c,alpha=.55,s=25)
        axes[2].scatter(cover,[i]*len(cover),color=c,alpha=.55,s=25)
    labels=[f"{r['series_id'].replace('E16dm_','')}  ({r['n_slices_with_qc_segments']}/{r['n_slices']} slices scored)" for r in rows]
    axes[0].set_yticks(y,labels)
    axes[0].set_xlabel('Median W across slice medians\nline: range of slice medians (not CI)')
    axes[1].set_xlabel('Auto-QC segments per slice')
    axes[2].set_xlabel('Accepted / detected graph length (%)')
    axes[0].set_title('Selected-segment waviness')
    axes[1].set_title('Tracing yield')
    axes[2].set_title('Algorithmic length coverage')
    for ax in axes:
        ax.grid(axis='x',alpha=.2)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle(f'First-pass 2D candidate-segment analysis | {len(images)} TIFF slices / {len(series)} fields',fontsize=15,y=.98)
    fig.text(.5,.02,'Unvalidated automated outputs. Adjacent slices are not independent samples. No biological CD/DMSO comparison.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.07,1,.94))
    fig.savefig(base/'overview.png',dpi=180)
    plt.close(fig)

    reps=[im for im in images if im['image_id'] in data['meta']['review_image_ids']]
    sheet=Image.new('RGB',(1600,max(500,math.ceil(len(reps)/4)*460+40)),'#101923');draw=ImageDraw.Draw(sheet)
    draw.text((18,12),'AUTO-QC SEGMENTS: GREEN | REVIEW: AMBER | REJECTED: GRAY | Display contrast enhanced',fill='white')
    for k,im in enumerate(reps):
        x,y=(k%4)*400,(k//4)*460+40
        preview=Image.open(base/im['overlay_path']);preview.thumbnail((390,390))
        sheet.paste(preview,(x+5,y+44))
        st=im['statistics'];name=im['image_id'].replace('E16dm_','')
        draw.text((x+7,y),name,fill='white')
        draw.text((x+7,y+18),f"AutoQC {st['n_accepted']} | graph coverage {100*st['accepted_graph_length_coverage']:.1f}%",fill='#bdd5e4')
    sheet.save(base/'representative_overlays.jpg',quality=94)

    with (base/'segments.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames or ['image_id','segment_id','status','contour_length_px','end_to_end_px','waviness','straightness','flags']
        accepted=[r for r in reader if r['status']=='accepted']
    with (base/'auto_qc_segments.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(accepted)
    counts={status:sum(im['statistics']['n_'+status] for im in images) for status in ['accepted','review','rejected']}
    coverage=np.array([im['statistics']['accepted_graph_length_coverage'] for im in images])
    weak=[im['image_id'] for im in images if im['statistics']['n_accepted']<5 or im['statistics']['accepted_graph_length_coverage']<.03]
    val=json.loads((base/'validation'/'validation_results.json').read_text()) if (base/'validation'/'validation_results.json').exists() else {}
    conditions = Counter(im['condition'] for im in images)
    low_fields = [r for r in series if r['n_auto_qc_segments_across_slices'] < 10]
    low_yield_text = '\n'.join(
        f"{r['series_id']}: {r['n_auto_qc_segments_across_slices']} QC paths; "
        f"{r['n_slices_with_qc_segments']}/{r['n_slices']} slices scored."
        for r in low_fields) or 'No field falls below the plot presentation cutoff in this run.'
    if val:
        categories = Counter(check.get('category','unspecified') for check in val.get('checks',[]))
        validation_text = (f"Saved synthetic/numerical checks: {val.get('check_count','unknown')}; "
                           f"failures: {val.get('failed_count','unknown')}. "
                           f"Categories: {dict(categories)}.")
    else:
        validation_text = 'No synthetic/numerical validation result was present when this report was generated.'
    smooth_parts = []
    for field, label in [('waviness_sigma1','sigma 1'),('waviness','sigma 2'),('waviness_sigma3','sigma 3')]:
        values = [float(r[field]) for r in accepted if r.get(field)]
        smooth_parts.append(f"{label}: {np.median(values):.5f}" if values else f"{label}: unavailable")
    report = REPORT_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        analysis_id=data['meta'].get('analysis_id','not provided'),
        n_images=len(images), n_series=len(series),
        image_plural="" if len(images)==1 else "s",series_plural="" if len(series)==1 else "s",
        condition_counts='; '.join(f'{label}: {count}' for label,count in sorted(conditions.items())),
        n_candidates=sum(counts.values()), n_accepted=counts['accepted'],
        n_review=counts['review'], n_rejected=counts['rejected'],
        coverage_median=100*np.median(coverage),coverage_min=100*coverage.min(),coverage_max=100*coverage.max(),
        low_yield_text=low_yield_text,parameters=json.dumps(data['meta'].get('parameters',{}),indent=2),
        n_representatives=len(reps),processing_options=json.dumps(data['meta'].get('processing_options',{})),
        validation_text=validation_text,smoothing_text='; '.join(smooth_parts))
    (base/'READ_ME_RESULTS_AND_METHODS.txt').write_text(report,encoding='utf-8')
    (base/'run_summary.json').write_text(json.dumps(dict(n_images=len(images),n_fields=len(series),counts=counts,
        median_algorithmic_length_coverage=float(np.median(coverage)),min_coverage=float(coverage.min()),max_coverage=float(coverage.max()),
        low_yield_images=weak),indent=2),encoding='utf-8')
    print(json.dumps(dict(n_images=len(images),n_fields=len(series),counts=counts,median_coverage=float(np.median(coverage))),indent=2))


REPORT_TEMPLATE = """FIBER-SEGMENT WAVINESS: EXPLORATORY ANALYSIS
Generated {generated_at} UTC
Analysis ID: {analysis_id}

ASSESSMENT
These are unvalidated automated candidate-segment measurements. Numerical and
synthetic checks do not establish real-image fiber identity, completeness,
recall, or agreement with expert traces. This is a technical feasibility/QC
prototype, not a validated biological measurement method or treatment result.

SCOPE AND COUNTS
{n_images} single-slice TIFF{image_plural} from {n_series} image field{series_plural}.
Observed filename conditions: {condition_counts}.
{n_candidates:,} candidate graph paths; {n_accepted:,} automatic-QC passes;
{n_review:,} paths for review; {n_rejected:,} automatically excluded paths.
These are repeated 2D observations, not counts of unique biological fibers.
The pipeline accepts its documented TIFF filename convention. CZI and other
filename conditions are not processed. Confirm labels against experimental records.

The median per-image accepted fraction of detected graph length is
{coverage_median:.2f}% (range {coverage_min:.2f}-{coverage_max:.2f}%).
The denominator includes the detected graph before junction removal, including
noise and small structures. This is NOT recall of true collagen fibers.

LOW TRACING YIELD
{low_yield_text}
Field medians based on fewer than 10 automatic-QC paths are retained in CSV/JSON
but withheld from the overview waviness plot as a presentation rule. This rule
is not a validated minimum sample size. Low yield does not establish absent
collagen or low waviness. Untraced fibers and truncated paths can occur in any field.

METRIC AND METHOD
Waviness W = centerline contour length L / endpoint distance D, with W >= 1.
Straightness S = D/L = 1/W. An ideal straight line has W=S=1.
L follows the centerline, not a segmented-blob boundary perimeter.
Reciprocals apply to each segment; 1/mean(S) is not mean(W).
Lengths use original-image pixels and assume isotropic XY spacing. Physical
calibration, common spacing across fields, and Z spacing remain unconfirmed.
Pixel cutoffs are not verified common physical lengths. No 3D waviness is calculated.

The pipeline performs Gaussian denoising and background subtraction, percentile
normalization, multiscale Sato ridge filtering, Otsu/hysteresis thresholding,
small-component filtering, skeletonization, and graph-path extraction.
A skeleton graph suppresses diagonals redundant with orthogonal connections.
Detected junctions and their first neighbors are removed before extracting paths.
There is no explicit gap bridging or junction linking. Filtering can still merge
adjacent signal or miss a crossing; biological continuity is not guaranteed.
Components with fewer than five skeleton points are counted separately.

Paths are resampled at approximately 1-pixel arc spacing and Gaussian-smoothed,
retaining their original endpoints. Raw contour length/raw W and sigma-1/sigma-3
W values are exported. Display coordinates are downsampled, so exported display
points do not reconstruct the exact full-resolution metric computation.

Automatic QC uses the recorded contour, endpoint-distance, boundary-distance,
and graph-path checks. Review candidates retain nonfatal flags. Passing these
rules is not manual confirmation or evidence of a complete fiber.
Recorded parameters, shared across conditions:
{parameters}

{n_representatives} central-slice representatives are embedded in review.html.
Threshold sensitivity uses 0.8/1.0/1.2 times the Otsu threshold where a central
slice was analyzed. These are parameter sensitivities, not confidence intervals.
Processing options: {processing_options}

CHECKS AND AUDIT
{validation_text}
Numerical/synthetic assertions are not independent biological validations.
See validation/validation_results.json for check-level outcomes and source hashes.
The separate bookkeeping audit checks saved metric arithmetic, counts, IDs,
summary medians, accepted-subset membership, and source-hash correspondence.
Inspect validation/audit_results.json for its recorded outcome and diagnostics;
this interpretation file does not independently establish that an audit passed.
Clean examples and extra analytic stress tests are not a general accuracy bound.

Pooled medians on the same automatically accepted paths: {smoothing_text}.
This is smoothing sensitivity, not a confidence interval or treatment effect.
Mask occupancy and detected-graph coverage are algorithm responses; they must
not be interpreted as collagen density, calibrated signal area, or biological recall.

INTERPRETATION LIMITS
Brightness, density, segmentation breaks, endpoints, and length/QC filters select
which paths are included. Shorter fragments may appear straighter. No independent
expert reference traces are included. Biological condition comparisons, biological
confidence intervals, and between-condition p-values are not justified.
Adjacent z slices and fields sharing a specimen are not independent replicates.
Filename IDs, treatment labels, mounting conditions, and independence require records.
This prototype is not a replication of a semi-manual tracing study on
maximum-intensity projections, and its individual-slice values are not directly comparable.

FILES AND REVIEW
review.html is a self-contained offline reviewer with {n_representatives} embedded
representatives. It supports zoom, trace selection, separate manual accept/reject
notes, and CSV export; these annotations do not change automatic summaries.
The independent manual drawing tool exports original XY points and raw clicked-
polyline L/D without smoothing or resampling. Match endpoints and use a common
estimator before comparing manual and automatic measurements. Saving or accepting
a trace does not establish an expert-validated reference set.

images/ contains preview, overlay, and mask files for the {n_images} analyzed slices.
Display contrast is enhanced; numerical measurements use original image dimensions.
auto_qc_segments.csv: filtered subset, not expert-validated fibers.
segments.csv: all candidate paths and flags; images.csv: per-image descriptors.
series_summary.csv: medians of slice medians, not biological estimates.
sample_id_summary.csv: unconfirmed filename-ID groups, not confirmed replicates.
threshold_sensitivity.csv: central-slice threshold sensitivity.
report_data.json/parameters.json: display coordinates, settings, and caveats.
validation/: synthetic checks, separate audit, and diagnostic figures.
The runner also records pipeline_run.json, pipeline.log, and exact source snapshots.

NEXT VALIDATION STEP
Use a prespecified, blinded subset spanning clear fibers, weak signal, crossings,
and boundaries. Knowledgeable annotators should trace matched segments/endpoints.
Measure missed and false paths, splits, merges, W error, review time, and coverage.
Keep every field/slice from one specimen together across development/validation splits.

REPRODUCING A NEW RUN
Use Python 3.12 or newer and install the project's requirements.txt.
From the project root:
python run_pipeline.py --input-dir /path/to/extracted_tiffs --output-dir runs/new_analysis
The output must be absent or empty. The runner reads original TIFFs without
modifying them and stages exact source copies in the new run directory.
The supplied results/ and report/ directories remain fixed snapshots.
"""


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=Path(__file__).resolve().parent,help='Directory containing report_data.json and CSV results')
    main(parser.parse_args().base)
