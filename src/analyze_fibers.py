#!/usr/bin/env python3
"""Exploratory 2D SHG candidate-segment tracing, not validated fiber instances.

Run with Python >=3.12 and requirements.txt. Original TIFFs are read-only.
No crossing linking, gap bridging, or condition-specific parameter tuning.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy import ndimage as ndi
import skimage
from skimage import filters, morphology
from PIL import Image, ImageDraw

PARAMETERS = dict(background_sigma_px=8.0, denoise_sigma_px=1.2,
                  ridge_sigmas_px=[1.5, 2.5, 3.5], normalization_percentile=99.8,
                  hysteresis_low_ratio=0.5, threshold_factor=1.0,
                  min_normalized_signal=0.06, min_mask_component_pixels=25,
                  minimum_qc_contour_px=80.0, minimum_review_contour_px=40.0,
                  edge_margin_px=10, smoothing_sigma_px=2.0,
                  minimum_endpoint_distance_px=10.0)


def measure_path(points, smooth_sigma=2.0):
    """Ordered xy pixels -> endpoint-preserving, arc-length-resampled metrics.

    smooth_sigma is in pixel arc-length units. Raw polyline length is retained.
    Invalid coincident endpoints return None scores. Coordinates remain pixels.
    """
    xy = np.asarray(points, dtype=float)
    if len(xy) < 2:
        return dict(contour_length_px=0.0, raw_contour_length_px=0.0,
                    end_to_end_px=0.0, waviness=None, straightness=None,
                    raw_waviness=None, points=xy.tolist())
    ds = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    keep = np.r_[True, ds > 1e-10]
    xy = xy[keep]
    if len(xy) < 2:
        return measure_path(xy, smooth_sigma)
    arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    raw_length = float(arc[-1])
    grid = np.linspace(0, raw_length, max(2, int(math.ceil(raw_length)) + 1))
    sampled = np.column_stack([np.interp(grid, arc, xy[:, k]) for k in [0, 1]])
    if smooth_sigma > 0:
        sampled = ndi.gaussian_filter1d(sampled, smooth_sigma, axis=0, mode='nearest')
        sampled[0], sampled[-1] = xy[0], xy[-1]
    length = float(np.linalg.norm(np.diff(sampled, axis=0), axis=1).sum())
    distance = float(np.linalg.norm(xy[-1] - xy[0]))
    valid = distance > 1e-8
    return dict(contour_length_px=length, raw_contour_length_px=raw_length,
                end_to_end_px=distance, waviness=length / distance if valid else None,
                straightness=distance / length if valid and length else None,
                raw_waviness=raw_length / distance if valid else None,
                points=sampled.tolist())


def ridge_image(raw):
    a = np.asarray(raw, dtype=np.float32)
    residual = ndi.gaussian_filter(a, PARAMETERS['denoise_sigma_px']) - ndi.gaussian_filter(a, PARAMETERS['background_sigma_px'])
    residual = np.maximum(residual, 0)
    scale = float(np.percentile(residual, PARAMETERS['normalization_percentile']))
    norm = np.clip(residual / max(scale, 1e-6), 0, 1)
    ridge = filters.sato(norm, sigmas=PARAMETERS['ridge_sigmas_px'], black_ridges=False).astype(np.float32)
    threshold = float(filters.threshold_otsu(ridge)) if np.ptp(ridge) > 1e-12 else 1.0
    return norm, ridge, threshold, scale


def mask_from_ridge(norm, ridge, threshold, factor=1.0):
    high = threshold * factor
    mask = filters.apply_hysteresis_threshold(ridge, high * PARAMETERS['hysteresis_low_ratio'], high)
    mask &= norm >= PARAMETERS['min_normalized_signal']
    labels, count = ndi.label(mask, structure=np.ones((3, 3)))
    sizes = np.bincount(labels.ravel())
    good = sizes >= PARAMETERS['min_mask_component_pixels']
    good[0] = False
    return good[labels]


def skeleton_graph(skeleton):
    """8-neighbor graph, suppress diagonals redundant with an orthogonal edge."""
    ys, xs = np.nonzero(skeleton)
    width = skeleton.shape[1]
    nodes = {int(y * width + x) for y, x in zip(ys, xs)}
    graph = {}
    for v in nodes:
        y, x = divmod(v, width)
        neighbors = []
        for dy, dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            yy, xx = y + dy, x + dx
            if not (0 <= yy < skeleton.shape[0] and 0 <= xx < width):
                continue
            n = yy * width + xx
            if n not in nodes:
                continue
            if dy and dx and (y * width + xx in nodes or yy * width + x in nodes):
                continue
            neighbors.append(n)
        graph[v] = neighbors
    return graph


def trace_mask(mask, image_id='test'):
    """Split skeleton at all junctions; return segments and algorithm diagnostics."""
    skeleton = morphology.skeletonize(mask)
    height, width = mask.shape
    graph = skeleton_graph(skeleton)
    junctions = {v for v, ns in graph.items() if len(ns) >= 3}
    blocked = junctions | {n for v in junctions for n in graph[v]}
    available = set(graph) - blocked
    total_length = sum(math.hypot((v % width)-(n % width), (v//width)-(n//width))
                       for v, ns in graph.items() for n in ns) / 2
    segments, tiny_count = [], 0
    while available:
        root = min(available)
        stack, component = [root], set()
        available.remove(root)
        while stack:
            v = stack.pop()
            component.add(v)
            for n in graph[v]:
                if n in available:
                    available.remove(n)
                    stack.append(n)
        if len(component) < 5:
            tiny_count += 1
            continue
        ends = sorted(v for v in component if sum(n in component for n in graph[v]) <= 1)
        closed = len(ends) != 2
        first = ends[0] if ends else min(component)
        ordered, visited, current = [], set(), first
        while current not in visited:
            ordered.append(current)
            visited.add(current)
            ns = [n for n in graph[current] if n in component and n not in visited]
            if not ns:
                break
            current = min(ns)
        if closed and len(ordered) > 2 and first in graph[ordered[-1]]:
            ordered.append(first)
        xy = np.array([(v % width, v // width) for v in ordered], dtype=float)
        metrics = measure_path(xy, PARAMETERS['smoothing_sigma_px'])
        flags = []
        if closed:
            flags.append('closed_or_non_path')
        if any(n in blocked for v in component for n in graph[v]):
            flags.append('junction_truncated')
        margin = PARAMETERS['edge_margin_px']
        if ((xy[:, 0] < margin) | (xy[:, 0] >= width-margin) |
            (xy[:, 1] < margin) | (xy[:, 1] >= height-margin)).any():
            flags.append('image_edge')
        if metrics['end_to_end_px'] < PARAMETERS['minimum_endpoint_distance_px']:
            flags.append('short_endpoint_distance')
        if metrics['contour_length_px'] < PARAMETERS['minimum_qc_contour_px']:
            flags.append('short_contour')
        if len(visited) != len(component):
            flags.append('incomplete_graph_path')
        if metrics['waviness'] is None:
            flags.append('undefined_ratio')
        fatal = {'closed_or_non_path', 'image_edge', 'short_endpoint_distance', 'incomplete_graph_path', 'undefined_ratio'}
        if fatal.intersection(flags) or metrics['contour_length_px'] < PARAMETERS['minimum_review_contour_px']:
            status = 'rejected'
        elif flags:
            status = 'review'
        else:
            status = 'accepted'
        # Retain smoothing sensitivity of this identical path; not a confidence interval.
        alt1, alt3 = measure_path(xy, 1.0), measure_path(xy, 3.0)
        metrics['waviness_sigma1'] = alt1['waviness']
        metrics['waviness_sigma3'] = alt3['waviness']
        points = metrics.pop('points')
        metrics['points'] = [[round(x, 2), round(y, 2)] for x, y in points[::3]]
        if metrics['points'][-1] != [round(points[-1][0], 2), round(points[-1][1], 2)]:
            metrics['points'].append([round(points[-1][0], 2), round(points[-1][1], 2)])
        segments.append(dict(segment_id=f'{image_id}_p{len(segments)+1:04d}',
                             status=status, flags=flags, **metrics))
    counts = Counter(s['status'] for s in segments)
    accepted = [s for s in segments if s['status'] == 'accepted']
    waves = [s['waviness'] for s in accepted]
    accepted_length = sum(s['raw_contour_length_px'] for s in accepted)
    stats = dict(n_segments=len(segments), n_accepted=counts['accepted'], n_review=counts['review'],
                 n_rejected=counts['rejected'], n_tiny_components=tiny_count,
                 skeleton_pixels=int(skeleton.sum()), junction_nodes=len(junctions),
                 detected_graph_length_px=total_length,
                 accepted_raw_length_px=accepted_length,
                 accepted_graph_length_coverage=accepted_length / total_length if total_length else 0,
                 median_waviness=float(np.median(waves)) if waves else None,
                 mean_waviness=float(np.mean(waves)) if waves else None,
                 median_contour_px=float(np.median([s['contour_length_px'] for s in accepted])) if accepted else None,
                 exclusion_flags=dict(Counter(f for s in segments for f in s['flags'])))
    return segments, stats


def analyze_array(raw, image_id='test', threshold_factor=1.0):
    norm, ridge, threshold, scale = ridge_image(raw)
    mask = mask_from_ridge(norm, ridge, threshold, threshold_factor)
    segments, stats = trace_mask(mask, image_id)
    stats.update(otsu_ridge_threshold=threshold, normalization_residual_scale=scale,
                 detected_signal_area_fraction=float(mask.mean()), raw_mean=float(np.mean(raw)),
                 raw_p99=float(np.percentile(raw, 99)))
    return segments, stats, mask, (norm, ridge, threshold)


def preview_array(raw):
    # Display only; no effect on measurement. Percentile/gamma adjusted for dim SHG.
    lo, hi = np.percentile(raw, [20, 99.8])
    a = np.clip((np.asarray(raw, float)-lo)/max(hi-lo, 1), 0, 1)**0.65
    return (a*255).astype(np.uint8)


def save_images(raw, segments, out, image_id):
    size = raw.shape[1], raw.shape[0]
    im = Image.fromarray(preview_array(raw)).convert('RGB')
    im.thumbnail((1100, 1100))
    preview = out / 'images' / f'{image_id}.jpg'
    im.save(preview, quality=90)
    overlay = im.copy()
    draw = ImageDraw.Draw(overlay)
    sx, sy = im.width/size[0], im.height/size[1]
    for status, color in [('rejected', '#8a8a8a'), ('review', '#f4b942'), ('accepted', '#32e6bf')]:
        for s in segments:
            if s['status'] != status or s['contour_length_px'] < 40:
                continue
            p = [(x*sx, y*sy) for x,y in s['points']]
            if len(p) > 1:
                draw.line(p, fill=color, width=2 if status=='accepted' else 1)
    op = out / 'images' / f'{image_id}_overlay.jpg'
    overlay.save(op, quality=92)
    return preview.relative_to(out).as_posix(), op.relative_to(out).as_posix()


def write_csv(path, rows):
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ';'.join(v) if isinstance(v,list) else json.dumps(v) if isinstance(v,dict) else v for k,v in row.items()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--representative-only', action='store_true')
    args = parser.parse_args()
    out = args.output_dir
    (out/'images').mkdir(parents=True, exist_ok=True)
    files = sorted(args.input_dir.rglob('*.tif'))
    grouped = defaultdict(list)
    for file in files:
        m = re.match(r'(E\d+dm_(CD|DMSO)_(s\d+)_img\d+(?:v\d+)?)', file.name)
        if not m:
            continue
        z = int(re.search(r'_z(\d+)', file.name).group(1))
        grouped[m[1]].append((z,file,m[2],m[3]))
    representatives = {series: sorted(items)[len(items)//2][0] for series, items in grouped.items()}
    image_rows, segment_rows, sensitivity_rows, images, representative_ids = [], [], [], [], []
    for series, items in sorted(grouped.items()):
        for z, file, condition, sample in sorted(items):
            if args.representative_only and z != representatives[series]:
                continue
            if args.limit and len(images) >= args.limit:
                break
            start = time.time()
            image_id = f'{series}_z{z:02d}'
            raw = np.array(Image.open(file))
            segments, stats, mask, cached = analyze_array(raw, image_id)
            pp, op = save_images(raw, segments, out, image_id)
            mask_path = out/'images'/f'{image_id}_mask.png'
            Image.fromarray((mask*255).astype(np.uint8)).save(mask_path)
            row = dict(image_id=image_id, condition=condition, sample_id=sample, series_id=series,
                       z_index=z, width=raw.shape[1], height=raw.shape[0],
                       source_file=str(file.relative_to(args.input_dir)),
                       sha256=hashlib.sha256(file.read_bytes()).hexdigest(), **stats)
            image_rows.append(row)
            for s in segments:
                segment_rows.append({**{k:row[k] for k in ['image_id','condition','sample_id','series_id','z_index']},
                                     **{k:v for k,v in s.items() if k!='points'}})
            images.append({**{k:row[k] for k in ['image_id','condition','sample_id','series_id','z_index','width','height']},
                           'preview_path':pp,'overlay_path':op,'statistics':stats,'segments':segments})
            if z == representatives[series]:
                representative_ids.append(image_id)
                norm, ridge, threshold = cached
                for factor in [0.8, 1.0, 1.2]:
                    if factor == 1:
                        ss = stats
                    else:
                        _, ss = trace_mask(mask_from_ridge(norm,ridge,threshold,factor), image_id)
                    sensitivity_rows.append(dict(image_id=image_id,condition=condition,sample_id=sample,
                                                 series_id=series,threshold_factor=factor,
                                                 **{k:ss[k] for k in ['n_segments','n_accepted','median_waviness','accepted_graph_length_coverage']}))
            print(f'{image_id}: autoQC={stats["n_accepted"]}, review={stats["n_review"]}, medianW={stats["median_waviness"]}, {time.time()-start:.1f}s', flush=True)
    series_rows = []
    for series in sorted(grouped):
        rs = [r for r in image_rows if r['series_id']==series]
        if not rs:
            continue
        medians = [r['median_waviness'] for r in rs if r['median_waviness'] is not None]
        series_rows.append(dict(series_id=series,condition=rs[0]['condition'],sample_id=rs[0]['sample_id'],
                                n_slices=len(rs),n_slices_with_qc_segments=len(medians),
                                n_auto_qc_segments_across_slices=sum(r['n_accepted'] for r in rs),
                                median_of_slice_median_waviness=float(np.median(medians)) if medians else None,
                                min_slice_median_waviness=min(medians) if medians else None,
                                max_slice_median_waviness=max(medians) if medians else None,
                                median_algorithmic_length_coverage=float(np.median([r['accepted_graph_length_coverage'] for r in rs]))))
    sample_rows=[]
    for condition,sample in sorted({(r['condition'],r['sample_id']) for r in series_rows}):
        rs=[r for r in series_rows if r['condition']==condition and r['sample_id']==sample]
        ms=[r['median_of_slice_median_waviness'] for r in rs if r['median_of_slice_median_waviness'] is not None]
        sample_rows.append(dict(condition=condition,filename_sample_id=sample,n_fields=len(rs),
                                median_of_field_summaries=float(np.median(ms)) if ms else None,
                                biological_identity_confirmed=False))
    analysis_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    identity = json.dumps(dict(source_hashes=[r['sha256'] for r in image_rows],
                               parameters=PARAMETERS,analysis_source_sha256=analysis_source_sha256),sort_keys=True)
    analysis_id = 'fiber_waviness_' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]
    meta = dict(title='Fiber-segment waviness: exploratory analysis', analysis_id=analysis_id,
                metric='W=smoothed 2D centerline contour length / endpoint distance; S=1/W',
                parameters=PARAMETERS,review_image_ids=representative_ids,
                versions=dict(python=sys.version.split()[0],numpy=np.__version__,scipy=scipy.__version__,skimage=skimage.__version__),
                source_input_kind='Extracted TIFF directory supplied through --input-dir; relative source filenames and SHA-256 hashes are recorded in images.csv.',
                analysis_source_sha256=analysis_source_sha256,
                processing_options=dict(limit=args.limit,representative_only=args.representative_only),
                manual_validation_completed=False,
                limitations=['Automatic QC passage is not manual validation. The measurements describe candidate 2D segments, not confirmed complete fibers.',
                             'No explicit gap bridging or junction linking is performed. Filtering can still merge nearby signals or miss a true crossing, so correct biological fiber identity is not guaranteed.',
                             'Lengths use original-image pixels and assume isotropic XY spacing. Pixel calibration, common spacing across fields, and Z spacing are unconfirmed. No 3D waviness is reported.',
                             'Adjacent Z slices and multiple fields from the same specimen are not independent biological replicates. No between-condition significance tests are performed.',
                             'Brightness, density, segmentation breaks, and segment length select which paths are measured. These outputs cannot establish a biological CD/DMSO difference.',
                             'Mask area fraction is an algorithm response, not collagen volume density or a validated biological area fraction.',
                             'CZI files and CA conditions are outside this analysis. Treatment labels, sample identities, mounting conditions, and independence require experimental records.',
                             'Fields with few or no automatically accepted paths have unstable or unavailable descriptive summaries; inspect tracing yield before interpreting a field median.',
                             'Numerical/synthetic checks are not independent validations on biological images. Expert reference traces are still required.',
                             'Accepted graph-length coverage uses the detected skeleton graph, including noise, as its denominator; it is not recall of true collagen fibers.'])
    write_csv(out/'segments.csv',segment_rows)
    write_csv(out/'images.csv',image_rows)
    write_csv(out/'series_summary.csv',series_rows)
    write_csv(out/'sample_id_summary.csv',sample_rows)
    write_csv(out/'threshold_sensitivity.csv',sensitivity_rows)
    (out/'report_data.json').write_text(json.dumps(dict(meta=meta,images=images,series_summary=series_rows,sample_summary=sample_rows),ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (out/'parameters.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'DONE {len(images)} slices; {len(segment_rows)} candidate segments; {sum(r["n_accepted"] for r in image_rows)} autoQC segments',flush=True)


if __name__ == '__main__':
    main()
