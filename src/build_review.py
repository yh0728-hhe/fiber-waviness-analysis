#!/usr/bin/env python3
"""Build a self-contained, offline image/trace QC report using only the stdlib.

Usage: python build_review.py [report_data.json] [--output review.html]
Library: generate_report(json_path, output_path=None) -> pathlib.Path

Coordinates in segments[].points must be [x, y] in the original full-field
image coordinate system. Preview images must cover that same field of view.
meta.review_image_ids may limit which images and traces are embedded; summary
tables and limitations are retained for the complete analysis.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
from pathlib import Path


def _image_uri(path: str, base: Path, cache: dict[str, str]) -> str:
    if path in cache:
        return cache[path]
    if path.startswith("data:image/"):
        return path
    source = (base / path).resolve()
    if not source.is_relative_to(base.resolve()):
        raise ValueError(f"Image must be inside the report directory: {path}")
    if not source.is_file():
        return ""
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    if not mime.startswith("image/"):
        raise ValueError(f"Unsupported preview image: {path}")
    uri = f"data:{mime};base64," + base64.b64encode(source.read_bytes()).decode("ascii")
    cache[path] = uri
    return uri


def generate_report(json_path: str | Path, output_path: str | Path | None = None, compact: bool = False) -> Path:
    """Read a JSON analysis and write an offline review HTML next to it."""
    source = Path(json_path).resolve()
    raw = source.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise ValueError("Expected an object containing an images array")
    meta = data.setdefault("meta", {})
    meta.setdefault("title", "Fiber-segment waviness: exploratory analysis")
    meta.setdefault("analysis_id", "fiber-waviness-" + hashlib.sha256(raw).hexdigest()[:16])
    all_images = data["images"]
    selection = meta.get("review_image_ids")
    if selection is not None:
        wanted = {str(item) for item in selection}
        images = [im for im in all_images if str(im.get("image_id")) in wanted]
    else:
        images = list(all_images)
    payload = dict(data)
    payload["meta"] = dict(meta)
    payload["meta"]["analysis_image_count"] = len(all_images)
    payload["meta"]["embedded_image_count"] = len(images)
    if compact:
        payload["meta"]["compact_review"] = True
        payload["meta"]["limitations"] = list(meta.get("limitations", [])) + [
            "This compact viewer embeds automatic-QC and needs-review paths only. Automatically excluded paths remain in the complete compressed CSV/JSON snapshot; the recorded numerical summaries are unchanged."
        ]
    payload["images"] = []
    cache: dict[str, str] = {}
    for original in images:
        im = dict(original)
        if compact:
            im["segments"] = [segment for segment in original.get("segments", []) if segment.get("status") != "rejected"]
        im["preview_data_uri"] = _image_uri(str(im.get("preview_path") or ""), source.parent, cache) if im.get("preview_path") else ""
        payload["images"].append(im)
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    destination = Path(output_path).resolve() if output_path else source.with_name("review.html")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(HTML.replace("__REPORT_JSON__", encoded), encoding="utf-8")
    return destination


build_review = generate_report


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fiber-segment waviness: exploratory analysis</title>
<style>
:root{color-scheme:light;--ink:#182b3b;--muted:#607283;--line:#dce5eb;--bg:#f3f6f8;--panel:#fff;--blue:#165d86;--green:#16846d;--amber:#be7600;--red:#9d2945;--gray:#8a949f;--pink:#c12597}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:#17364a;color:white;padding:28px max(24px,calc((100vw - 1540px)/2));border-bottom:5px solid #48baa9}header .eyebrow{font-size:12px;letter-spacing:.12em;color:#aedddc;margin:0 0 6px}h1{font-size:27px;line-height:1.35;margin:0 0 10px;font-weight:650}header p{margin:6px 0;color:#dce8ef;max-width:1080px}main{max-width:1588px;margin:auto;padding:22px 24px 36px}.notice{background:#fff8e9;border:1px solid #ead3a1;border-left:4px solid #bc790a;padding:13px 17px;border-radius:8px;margin-bottom:18px}.notice p{margin:2px 0}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px}.card{padding:13px 18px}.card .value{font-size:25px;line-height:1.25;font-weight:650;color:var(--blue)}.card .label{color:var(--muted);font-size:12px;margin-top:5px}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px}.panel h2{font-size:16px;margin:0 0 12px}.padded{padding:18px}.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.controls label{display:flex;gap:5px;align-items:center}select,button,textarea,input[type=text]{font:inherit;color:inherit}select,button,input[type=text]{border:1px solid #c6d4de;background:white;border-radius:6px;min-height:36px;padding:5px 10px}select{max-width:100%}button{cursor:pointer}button:hover{border-color:var(--blue);background:#edf5fa}button:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #63b8e5;outline-offset:2px}button:disabled{opacity:.45;cursor:default}.primary{background:var(--blue);color:white;border-color:var(--blue)}.primary:hover{background:#104869;color:white}.danger{color:var(--red)}.small{font-size:12px;color:var(--muted)}.image-select{width:100%;margin:6px 0 12px}.toolbar{padding:10px 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:#f7fafb}.viewer{position:relative;height:570px;background:#0a1119;overflow:hidden;border-radius:0 0 9px 9px;touch-action:none}.viewer canvas{display:block;width:100%;height:100%;cursor:crosshair}.viewer-note{position:absolute;bottom:10px;left:12px;right:12px;font-size:11px;color:#d5e2ed;background:#101b28c9;padding:5px 8px;border-radius:4px;pointer-events:none}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;margin-top:9px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 14px}.metric{background:#f2f6f8;border-radius:6px;padding:8px 10px}.metric b{display:block;font-size:18px;line-height:1.3;font-weight:600}.metric span{font-size:11px;color:var(--muted)}.badge{display:inline-block;border-radius:5px;padding:3px 7px;background:#eaf2f7;color:#28506d;font-size:12px;overflow-wrap:anywhere}.badge.review{background:#fff2d8;color:#986000}.badge.accepted{background:#e2f3ed;color:#126c59}.badge.rejected{background:#edf0f3;color:#697683}.status-line{margin:6px 0 10px}.divider{border:0;border-top:1px solid var(--line);margin:17px 0}textarea{display:block;width:100%;height:70px;resize:vertical;border:1px solid #c6d4de;border-radius:6px;padding:8px;background:white}.review-buttons{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.review-buttons button{font-size:13px}.export-box{padding:13px;background:#f2f7fa;border-radius:7px}.export-box button{width:100%;margin-top:7px}.empty{color:var(--muted);padding:20px 0}.table-panel{margin-top:16px;padding:18px}.table-scroll{overflow:auto;max-height:370px;border:1px solid var(--line);border-radius:7px;margin-top:10px}table{border-collapse:collapse;width:100%;font-size:12px;text-align:left;white-space:nowrap}th{background:#edf3f7;color:#405c70;position:sticky;top:0;z-index:1;font-weight:600}td,th{padding:8px 10px;border-bottom:1px solid var(--line)}tbody tr:last-child td{border-bottom:0}#traceRows tr{cursor:pointer}#traceRows tr:hover{background:#f0f7fb}#traceRows tr.selected{background:#fdebf8}td.num{text-align:right;font-variant-numeric:tabular-nums}details{margin-top:18px;background:white;border:1px solid var(--line);border-radius:8px;padding:12px 16px}summary{cursor:pointer;font-weight:600}details p{color:var(--muted)}#limits li{margin-bottom:6px}#imageFacts{overflow-wrap:anywhere}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}.section-heading h2{margin-bottom:0}.summary-note{max-width:1050px}#manualState{font-weight:600}.foot{margin-top:18px;color:var(--muted);font-size:12px}a{color:var(--blue)}
@media(max-width:1000px){.workspace{grid-template-columns:1fr}.sidebar{display:grid;grid-template-columns:1fr 1fr;gap:18px}.sidebar .divider{display:none}.viewer{height:490px}.sidebar .export-box{grid-column:1/-1}.cards{grid-template-columns:1fr 1fr}}
@media(max-width:600px){main{padding:14px 10px}header{padding:22px 16px}h1{font-size:22px}.workspace{gap:10px}.sidebar{display:block}.sidebar .divider{display:block}.viewer{height:370px}.padded,.table-panel{padding:13px}.card{padding:11px}.cards{gap:8px}.controls{gap:7px}.toolbar button{padding:4px 8px}.metric b{font-size:17px}}
</style>
</head>
<body>
<header><p class="eyebrow">EXPLORATORY FIBER WAVINESS · OFFLINE REVIEW</p><h1 id="title">Fiber-segment waviness: exploratory analysis</h1><p>Review automatically extracted fiber segments in their original fields of view and record decisions for individual traces. These are exploratory image measurements; passing automatic QC does not establish manual or expert validation.</p></header>
<main>
<div class="notice"><p><strong>Unvalidated first-pass analysis.</strong>Crossings, fragmentation, noise, and defocus can change the traces. Measurements describe traceable image segments; they do not directly represent complete fibers or material properties.</p><p class="small">Manual annotations are stored only in this browser. Download a CSV to retain them. Exporting annotations does not modify the analysis or original images.</p></div>
<div class="cards"><div class="card"><div class="value" id="cardImages">—</div><div class="label">Embedded review images / analyzed images</div></div><div class="card"><div class="value" id="cardSegments">—</div><div class="label">Candidate segments embedded in this report</div></div><div class="card"><div class="value" id="cardReviewed">0</div><div class="label">Segments manually accepted or rejected</div></div><div class="card"><div class="value" id="cardPending">—</div><div class="label">Segments without a manual decision</div></div></div>
<div class="workspace">
<section class="panel" aria-label="Image and trace viewer">
<div class="padded"><h2>Images and candidate traces</h2><label for="imageSelect" class="small">Select an image (original labels retained)</label><select id="imageSelect" class="image-select"></select><div id="imageFacts" class="small"></div><div class="legend"><span><i class="dot" style="background:var(--green)"></i>Automatic QC passed (not manually validated)</span><span><i class="dot" style="background:var(--amber)"></i>Needs review</span><span><i class="dot" style="background:var(--gray)"></i>Automatically excluded</span><span><i class="dot" style="background:var(--pink)"></i>Selected</span></div></div>
<div class="toolbar controls"><label><input type="checkbox" id="showTraces" checked>Automatic traces</label><label><input type="checkbox" id="showAccepted" checked>QC passed</label><label><input type="checkbox" id="showReview" checked>Needs review</label><label><input type="checkbox" id="showRejected">Excluded</label><label><input type="checkbox" id="showManual" checked>Manual polylines</label><button id="zoomOut" title="Zoom out">−</button><button id="zoomIn" title="Zoom in">＋</button><button id="fit">Fit image</button><span id="zoomLabel" class="small">100%</span></div>
<div class="viewer" id="viewer"><canvas id="canvas" role="img" aria-label="Image preview with selectable fiber traces"></canvas><div class="viewer-note" id="viewerHint">Select a trace on the image or in the table · Drag to pan · Scroll to zoom · Dashed lines indicate manual rejection</div></div>
</section>
<aside class="panel padded sidebar"><div><h2>Selected segment</h2><div id="selectedEmpty" class="empty">Select a trace on the image or in the segment table.</div><div id="selectedDetail" hidden><div id="selectedId" class="badge"></div><div class="status-line"><span id="autoStatus" class="badge"></span></div><div class="detail-grid"><div class="metric"><b id="waviness">—</b><span>Waviness L/D</span></div><div class="metric"><b id="straightness">—</b><span>Straightness D/L</span></div><div class="metric"><b id="contour">—</b><span>Contour length L (px)</span></div><div class="metric"><b id="chord">—</b><span>Endpoint distance D (px)</span></div></div><div id="flags" class="small"></div></div></div>
<hr class="divider"><div><h2>Manual decision</h2><p id="manualState">No manual decision yet</p><label for="note" class="small">Notes (optional)</label><textarea id="note" disabled placeholder="For example: wrong branch at a crossing, fragmented trace, or background noise"></textarea><div class="review-buttons"><button id="accept" disabled>Accept segment</button><button id="reject" class="danger" disabled>Reject segment</button><button id="unreview" disabled>Clear decision</button></div><p class="small">Your accept/reject decisions are recorded separately from the original automatic QC status. Notes are saved locally as you type.</p></div>
<div class="export-box"><strong>Keep your review records</strong><div id="storageInfo" class="small">Loading local annotations…</div><button id="export" class="primary">Download manual-review CSV</button><button id="clearAll" class="danger">Clear local review annotations</button><div class="small">The CSV contains every embedded candidate, its original QC status, and your manual decision. Unreviewed decision fields remain blank.</div></div></aside>
</div>
<section class="panel table-panel"><div class="section-heading"><h2>Segments in the current image</h2><div class="controls"><label for="manualFilter" class="small">Manual status</label><select id="manualFilter"><option value="all">All</option><option value="unreviewed">Unreviewed</option><option value="accepted">Accepted manually</option><option value="rejected">Rejected manually</option></select><button id="prevPage">Previous page</button><button id="nextPage">Next page</button><span id="rowCount" class="small"></span></div></div><p class="small">The table and traces share the QC filters. Select a row to inspect a segment; select a numeric column heading to sort. The table displays up to 200 segments per page; the canvas shows all traces that match the filters. Manual decisions do not recalculate group summaries.</p><div class="table-scroll"><table><thead><tr><th>Segment</th><th>Original automatic QC</th><th>Manual decision</th><th data-sort="waviness" tabindex="0" role="button" title="Sort by waviness">Waviness L/D ↕</th><th data-sort="straightness" tabindex="0" role="button">Straightness D/L ↕</th><th data-sort="contour_length_px" tabindex="0" role="button">Contour length (px)↕</th><th data-sort="end_to_end_px" tabindex="0" role="button">Endpoint distance (px)↕</th><th>Flags</th></tr></thead><tbody id="traceRows"></tbody></table></div></section>
<section class="panel table-panel"><div class="section-heading"><h2>Independent manual-polyline measurements</h2><span class="badge">Cyan traces · excluded from automatic summaries</span></div><p>Choose the start and end of one identifiable, continuous fiber. Click sequentially along its centerline from the chosen start to the chosen end. Stop before ambiguous crossings, signal gaps, or image boundaries; do not bridge gaps. You can still drag to pan and scroll to zoom.</p><p class="small"><strong>Manual estimator: </strong>Length is the sum of straight-line distances between successive clicks, with no smoothing, curve fitting, or arc-length resampling. Click density and endpoint choice affect the result. This differs from the smoothed-centerline estimator used for automatic traces, so the numbers cannot directly establish its measurement error. Export the original points to apply a consistent estimator separately.</p><div class="controls"><button id="startManual">Start drawing</button><button id="undoManual" disabled>Undo last point</button><button id="saveManual" disabled>Save polyline</button><button id="cancelManual" disabled>Cancel drawing</button><span id="manualMetrics" class="small">No drawing in progress</span></div><label for="manualNote" class="small">Notes for this manual polyline (optional)</label><input type="text" id="manualNote" style="width:100%;margin-top:5px" placeholder="For example: one continuous fiber between two identifiable landmarks" disabled><div class="controls" style="margin-top:12px"><button id="exportManual" class="primary">Download manual points and raw-polyline CSV</button><button id="clearManual" class="danger">Clear all manual polylines for this analysis</button></div><div class="table-scroll"><table><thead><tr><th>Manual polyline in the current image</th><th>Points</th><th>Raw-polyline waviness L/D</th><th>Raw-polyline straightness D/L</th><th>Contour length (px)</th><th>Endpoint distance (px)</th><th>Notes</th><th>Action</th></tr></thead><tbody id="manualRows"></tbody></table></div></section>
<details open><summary>Measurement definitions and limits</summary><p>Waviness is contour length L divided by the straight-line distance D between endpoints. An ideal straight segment has waviness 1; larger values describe a more curved traced segment. Straightness is D/L. Lengths are reported in pixels unless a reliable physical calibration is supplied. Individual segments, fields from the same sample, and adjacent z sections are not independent biological replicates.</p><ul id="limits"></ul><p id="scopeNote" class="small"></p></details>
<details><summary>Original group summaries (unaffected by manual annotations)</summary><p class="small summary-note">These series and sample summaries are reproduced from the analysis, with original field names and values retained. They have not been validated against manual traces and do not update when you accept or reject segments here.</p><div id="seriesSummary"></div><div id="sampleSummary"></div></details>
<p class="foot">This file works offline, has no backend, and does not transmit images or annotations. Display contrast may have been normalized; check the original files to assess the signal.<span id="runId"></span></p>
</main>
<script id="reportData" type="application/json">__REPORT_JSON__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('reportData').textContent);
const $=id=>document.getElementById(id), images=DATA.images||[], meta=DATA.meta||{};
const title=String(meta.title||'Fiber-segment waviness: exploratory analysis'); document.title=title; $('title').textContent=title;
const AUTO={accepted:'Automatic QC passed (not manually validated)',review:'Needs review',rejected:'Automatically excluded'};
const SHORT={accepted:'Automatic QC passed (not manually validated)',review:'Needs review',rejected:'Automatically excluded'};
const COLORS={accepted:'#22b99a',review:'#f0af3c',rejected:'#9ca6b4'};
const runId=String(meta.analysis_id||'fiber-waviness-review');
const storageKey='fiber-waviness-manual-v1:'+runId;
let decisions=Object.create(null), storageAvailable=true, activeIndex=0, selected=null, rows=[], sortKey='', sortDesc=true, tablePage=0;
const PAGE_SIZE=200;
let manualTraces=[], manualDrawing=false, manualDraft=[];
const manualStorageKey=storageKey+':drawn-polylines';
try{const saved=JSON.parse(localStorage.getItem(manualStorageKey)||'[]');if(Array.isArray(saved))manualTraces=saved.filter(t=>t&&Array.isArray(t.points)&&t.points.length>1);}catch(_){storageAvailable=false;}
let currentImage=null, imageLoading=false, imageError=false, camera={zoom:1,panX:0,panY:0}, fitScale=1;
let viewport={w:1,h:1}, pointer=null, drawPending=false;
const canvas=$('canvas'), ctx=canvas.getContext('2d');
const autoStatus=s=>Object.hasOwn(AUTO,s.status)?s.status:'review';
const key=(im,s)=>JSON.stringify([String(im.image_id),String(s.segment_id)]);
const finite=v=>v!==null && v!==undefined && v!=='' && Number.isFinite(Number(v));
const fmt=(v,d=3)=>finite(v)?Number(v).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d}):'—';
const str=v=>v===null||v===undefined?'—':String(v);
const im=()=>images[activeIndex]||null;
const pointList=s=>Array.isArray(s.points)?s.points:[];
const hasPoints=s=>pointList(s).length>1;
const flags=s=>Array.isArray(s.flags)?s.flags.map(str).join('; '):(s.flags?str(s.flags):'');
try{const parsed=JSON.parse(localStorage.getItem(storageKey)||'{}');if(parsed&&typeof parsed==='object'&&!Array.isArray(parsed))decisions=Object.assign(Object.create(null),parsed);}catch(_){storageAvailable=false;}
function persist(){try{localStorage.setItem(storageKey,JSON.stringify(decisions));}catch(_){storageAvailable=false;}updateCards();$('storageInfo').textContent=storageAvailable?'Local storage is enabled. Moving this file or changing browsers may make stored annotations unavailable; download a CSV backup.':'Local storage is unavailable. Annotations currently exist only in this open page; download a CSV before closing it.';}
function updateCards(){let n=0,done=0;for(const image of images){for(const s of image.segments||[]){n++;if(['accepted','rejected'].includes(decisions[key(image,s)]?.decision))done++;}}$('cardImages').textContent=images.length.toLocaleString()+' / '+Number(meta.analysis_image_count||images.length).toLocaleString();$('cardSegments').textContent=n.toLocaleString();$('cardReviewed').textContent=done.toLocaleString();$('cardPending').textContent=(n-done).toLocaleString();}
function allowed(s){if(!$('show'+({accepted:'Accepted',review:'Review',rejected:'Rejected'}[autoStatus(s)])).checked)return false;const f=$('manualFilter').value,d=decisions[key(im(),s)]?.decision;if(f==='unreviewed')return !['accepted','rejected'].includes(d);return f==='all'||f===d;}
function orderedRows(){let a=(im()?.segments||[]).filter(allowed);if(sortKey)a=a.slice().sort((a,b)=>{const av=finite(a[sortKey])?Number(a[sortKey]):-Infinity,bv=finite(b[sortKey])?Number(b[sortKey]):-Infinity;return sortDesc?bv-av:av-bv;});return a;}
function cell(tr,text,cls){const td=document.createElement('td');td.textContent=text;if(cls)td.className=cls;tr.append(td);return td;}
function renderRows(){rows=orderedRows();const tbody=$('traceRows');tbody.replaceChildren();const fragment=document.createDocumentFragment();tablePage=Math.min(tablePage,Math.max(0,Math.ceil(rows.length/PAGE_SIZE)-1));for(const s of rows.slice(tablePage*PAGE_SIZE,(tablePage+1)*PAGE_SIZE)){const tr=document.createElement('tr');tr.tabIndex=0;tr.setAttribute('aria-label','Selected segment '+str(s.segment_id));if(s===selected)tr.className='selected';cell(tr,str(s.segment_id));const td=cell(tr,'');const badge=document.createElement('span');badge.className='badge '+autoStatus(s);badge.textContent=SHORT[autoStatus(s)];td.append(badge);const decision=decisions[key(im(),s)]?.decision;cell(tr,decision==='accepted'?'Accepted manually':decision==='rejected'?'Rejected manually':'Unreviewed');for(const field of ['waviness','straightness','contour_length_px','end_to_end_px'])cell(tr,fmt(s[field],field.endsWith('_px')?1:3),'num');cell(tr,flags(s)||'—');tr.addEventListener('click',()=>selectSegment(s));tr.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectSegment(s);}});fragment.append(tr);}tbody.append(fragment);$('rowCount').textContent=(rows.length?(tablePage*PAGE_SIZE+1)+'–'+Math.min((tablePage+1)*PAGE_SIZE,rows.length):'0')+' / '+rows.length+' matching; embedded total '+(im()?.segments||[]).length+' segments';$('prevPage').disabled=tablePage===0;$('nextPage').disabled=(tablePage+1)*PAGE_SIZE>=rows.length;if(!rows.length){const tr=document.createElement('tr');const td=cell(tr,'No segments match the current filters.');td.colSpan=8;tbody.append(tr);}requestDraw();}
function updateDetail(){const yes=!!selected;$('selectedEmpty').hidden=yes;$('selectedDetail').hidden=!yes;for(const id of ['note','accept','reject','unreview'])$(id).disabled=!yes;if(!yes){$('manualState').textContent='No manual decision yet';$('note').value='';return;}const s=selected,d=decisions[key(im(),s)]||{};$('selectedId').textContent=str(s.segment_id);$('autoStatus').textContent=AUTO[autoStatus(s)];$('autoStatus').className='badge '+autoStatus(s);$('waviness').textContent=fmt(s.waviness);$('straightness').textContent=fmt(s.straightness);$('contour').textContent=fmt(s.contour_length_px,1);$('chord').textContent=fmt(s.end_to_end_px,1);$('flags').textContent='Flags: '+(flags(s)||'None provided');$('manualState').textContent=d.decision==='accepted'?'Accepted manually':d.decision==='rejected'?'Rejected manually':'No manual decision yet';$('note').value=d.note||'';}
function selectSegment(s){selected=s;const index=orderedRows().indexOf(s);if(index>=0)tablePage=Math.floor(index/PAGE_SIZE);updateDetail();renderRows();}
function review(decision){if(!selected)return;const k=key(im(),selected),old=decisions[k]||{};decisions[k]={...old,decision,note:$('note').value,reviewed_at:new Date().toISOString()};persist();updateDetail();renderRows();}
function loadImage(){selected=null;tablePage=0;manualDrawing=false;manualDraft=[];updateManualDraft();renderManualRows();currentImage=null;imageLoading=true;imageError=false;camera={zoom:1,panX:0,panY:0};updateDetail();const image=im();if(!image){$('imageFacts').textContent='No images are available for review.';imageLoading=false;renderRows();return;}$('imageFacts').textContent=['Condition '+str(image.condition),'Sample '+str(image.sample_id),'Series '+str(image.series_id),'z '+str(image.z_index),'Original '+str(image.width)+' × '+str(image.height)+' px'].join(' · ');renderRows();const img=new Image(),expected=activeIndex;img.onload=()=>{if(expected!==activeIndex)return;currentImage=img;imageLoading=false;requestDraw();};img.onerror=()=>{if(expected!==activeIndex)return;imageLoading=false;imageError=true;requestDraw();};if(image.preview_data_uri)img.src=image.preview_data_uri;else{imageLoading=false;imageError=true;requestDraw();}}
function dimensions(){const image=im();return {w:Number(image?.width)||currentImage?.naturalWidth||1,h:Number(image?.height)||currentImage?.naturalHeight||1};}
function transform(){const size=dimensions();fitScale=Math.min(viewport.w/size.w,viewport.h/size.h)*.94;const scale=fitScale*camera.zoom;return {scale,x:(viewport.w-size.w*scale)/2+camera.panX,y:(viewport.h-size.h*scale)/2+camera.panY};}
function requestDraw(){if(!drawPending){drawPending=true;requestAnimationFrame(()=>{drawPending=false;draw();});}}
function draw(){const r=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,3);viewport={w:Math.max(r.width,1),h:Math.max(r.height,1)};const bw=Math.round(viewport.w*dpr),bh=Math.round(viewport.h*dpr);if(canvas.width!==bw||canvas.height!==bh){canvas.width=bw;canvas.height=bh;}ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#0a1119';ctx.fillRect(0,0,viewport.w,viewport.h);const t=transform(),size=dimensions();ctx.save();ctx.translate(t.x,t.y);ctx.scale(t.scale,t.scale);if(currentImage)ctx.drawImage(currentImage,0,0,size.w,size.h);ctx.restore();if(!currentImage){ctx.font='14px system-ui';ctx.fillStyle='#b9c9d6';ctx.textAlign='center';ctx.fillText(imageLoading?'Loading image…':imageError?'Image preview unavailable; segment metrics remain available in the table.':'No image',viewport.w/2,viewport.h/2);}if($('showTraces').checked){for(const s of rows){if(s===selected)continue;drawTrace(s,t,false);}if(selected&&allowed(selected))drawTrace(selected,t,true);}if($('showManual').checked){const saved=manualTraces.filter(t=>String(t.image_id)===String(im()?.image_id));saved.forEach((trace,index)=>drawManualTrace(trace.points,t,'Manual '+(index+1),false));if(manualDraft.length)drawManualTrace(manualDraft,t,'Drawing',true);}$('zoomLabel').textContent=Math.round(camera.zoom*100)+'%';}
function drawTrace(s,t,isSelected){const p=pointList(s);if(p.length<2)return;const d=decisions[key(im(),s)]?.decision;ctx.beginPath();let begun=false;for(const a of p){if(!Array.isArray(a)||!finite(a[0])||!finite(a[1]))continue;const x=Number(a[0])*t.scale+t.x,y=Number(a[1])*t.scale+t.y;if(!begun){ctx.moveTo(x,y);begun=true;}else ctx.lineTo(x,y);}ctx.lineWidth=isSelected?3:1.5;ctx.strokeStyle=isSelected?'#ff55cb':COLORS[autoStatus(s)];ctx.globalAlpha=isSelected?1:d==='rejected'?.5:.88;ctx.setLineDash(d==='rejected'?[4,4]:[]);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;if(isSelected){ctx.fillStyle='#ffb3e7';for(const a of [p[0],p[p.length-1]]){if(!a||!finite(a[0])||!finite(a[1]))continue;ctx.beginPath();ctx.arc(a[0]*t.scale+t.x,a[1]*t.scale+t.y,4,0,2*Math.PI);ctx.fill();}}}
function zoomBy(factor,x=viewport.w/2,y=viewport.h/2){const before=transform(),next=Math.max(.5,Math.min(25,camera.zoom*factor)),ratio=next/camera.zoom;camera.zoom=next;const after=transform();camera.panX+=(x-before.x)* (1-ratio)+(before.x-after.x);camera.panY+=(y-before.y)* (1-ratio)+(before.y-after.y);requestDraw();}
function distance2(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],len=dx*dx+dy*dy;let t=len?((p[0]-a[0])*dx+(p[1]-a[1])*dy)/len:0;t=Math.max(0,Math.min(1,t));return (p[0]-a[0]-t*dx)**2+(p[1]-a[1]-t*dy)**2;}
function hitTest(x,y){if(!$('showTraces').checked)return;const t=transform(),p=[(x-t.x)/t.scale,(y-t.y)/t.scale];let best=null,bestD=(10/t.scale)**2;for(const s of rows){const points=pointList(s);for(let j=1;j<points.length;j++){const a=points[j-1],b=points[j];if(!Array.isArray(a)||!Array.isArray(b)||![...a,...b].every(finite))continue;const d=distance2(p,a,b);if(d<bestD){best=s;bestD=d;}}}if(best)selectSegment(best);}
canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;pointer={id:e.pointerId,x:e.clientX,y:e.clientY,originX:e.clientX,originY:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!pointer||e.pointerId!==pointer.id)return;const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;pointer.moved ||= Math.hypot(e.clientX-pointer.originX,e.clientY-pointer.originY)>4;camera.panX+=dx;camera.panY+=dy;pointer.x=e.clientX;pointer.y=e.clientY;requestDraw();});
canvas.addEventListener('pointerup',e=>{if(!pointer||e.pointerId!==pointer.id)return;const moved=pointer.moved;pointer=null;canvas.releasePointerCapture(e.pointerId);if(!moved){const r=canvas.getBoundingClientRect();if(manualDrawing)addManualPoint(e.clientX-r.left,e.clientY-r.top);else hitTest(e.clientX-r.left,e.clientY-r.top);}});canvas.addEventListener('pointercancel',()=>pointer=null);
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoomBy(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top);},{passive:false});
$('zoomIn').onclick=()=>zoomBy(1.25);$('zoomOut').onclick=()=>zoomBy(.8);$('fit').onclick=()=>{camera={zoom:1,panX:0,panY:0};requestDraw();};
new ResizeObserver(requestDraw).observe($('viewer'));
for(const id of ['showAccepted','showReview','showRejected','manualFilter'])$(id).addEventListener('change',()=>{tablePage=0;renderRows();});for(const id of ['showTraces','showManual'])$(id).addEventListener('change',requestDraw);$('prevPage').onclick=()=>{tablePage=Math.max(0,tablePage-1);renderRows();};$('nextPage').onclick=()=>{tablePage++;renderRows();};
$('imageSelect').addEventListener('change',()=>{if(manualDraft.length&&!confirm('This polyline has not been saved. Switch images and discard it?')){$('imageSelect').value=String(activeIndex);return;}activeIndex=Number($('imageSelect').value);loadImage();});
$('accept').onclick=()=>review('accepted');$('reject').onclick=()=>review('rejected');$('unreview').onclick=()=>{if(!selected)return;delete decisions[key(im(),selected)];persist();updateDetail();renderRows();};
$('note').addEventListener('input',()=>{if(!selected)return;const k=key(im(),selected);decisions[k]={...(decisions[k]||{}),note:$('note').value};persist();});
$('clearAll').onclick=()=>{if(!confirm('Clear every manual review decision and note for this analysis in this browser? Download a CSV backup first.'))return;decisions=Object.create(null);persist();updateDetail();renderRows();};
for(const th of document.querySelectorAll('[data-sort]')){const sort=()=>{if(sortKey===th.dataset.sort)sortDesc=!sortDesc;else{sortKey=th.dataset.sort;sortDesc=true;}tablePage=0;renderRows();};th.addEventListener('click',sort);th.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();sort();}});}
function csvValue(v){let s=v===null||v===undefined?'':String(v);if(typeof v==='string'&&/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
function polylineMetrics(points){let length=0;for(let i=1;i<points.length;i++)length+=Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]);const chord=points.length>1?Math.hypot(points.at(-1)[0]-points[0][0],points.at(-1)[1]-points[0][1]):0;return {length,chord,waviness:chord>0?length/chord:null,straightness:length>0?chord/length:null};}
function updateManualDraft(){const m=polylineMetrics(manualDraft);$('manualMetrics').textContent=manualDrawing?manualDraft.length+' points · L '+fmt(m.length,1)+' px · D '+fmt(m.chord,1)+' px · Raw-polyline waviness L/D '+fmt(m.waviness)+' · Raw-polyline straightness D/L '+fmt(m.straightness)+(m.chord>0&&m.chord<10?' · Short endpoint distance; sensitive to click placement':''):'No drawing in progress';$('undoManual').disabled=!manualDrawing||manualDraft.length===0;$('saveManual').disabled=!manualDrawing||manualDraft.length<2||m.chord<=0;$('cancelManual').disabled=!manualDrawing;$('startManual').disabled=manualDrawing||!im();$('manualNote').disabled=!manualDrawing;$('viewerHint').textContent=manualDrawing?'Drawing: click sequentially along one continuous fiber, ending at its endpoint · Drag to pan · Select Save polyline when finished':'Select a trace on the image or in the table · Drag to pan · Scroll to zoom · Dashed lines indicate manual rejection';requestDraw();}
function addManualPoint(x,y){const t=transform(),size=dimensions(),p=[(x-t.x)/t.scale,(y-t.y)/t.scale];if(p[0]<0||p[1]<0||p[0]>=size.w||p[1]>=size.h)return;const rounded=p.map(v=>Math.round(v*1e6)/1e6);if(manualDraft.length&&Math.hypot(rounded[0]-manualDraft.at(-1)[0],rounded[1]-manualDraft.at(-1)[1])<.25)return;manualDraft.push(rounded);updateManualDraft();}
function drawManualTrace(points,t,label,draft){if(!points.length)return;ctx.beginPath();points.forEach((p,i)=>{const x=p[0]*t.scale+t.x,y=p[1]*t.scale+t.y;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.strokeStyle=draft?'#c2faff':'#39d5ee';ctx.lineWidth=draft?2.5:2;ctx.setLineDash(draft?[5,3]:[]);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=draft?'#e3fcff':'#39d5ee';const dots=draft?points:[points[0],points.at(-1)];for(const p of dots){ctx.beginPath();ctx.arc(p[0]*t.scale+t.x,p[1]*t.scale+t.y,draft?3:4,0,2*Math.PI);ctx.fill();}ctx.font='11px system-ui';ctx.textAlign='left';ctx.fillText(label,points[0][0]*t.scale+t.x+6,points[0][1]*t.scale+t.y-6);}
function persistManual(){try{localStorage.setItem(manualStorageKey,JSON.stringify(manualTraces));}catch(_){storageAvailable=false;}persist();renderManualRows();requestDraw();}
function renderManualRows(){const body=$('manualRows');body.replaceChildren();const current=manualTraces.filter(t=>String(t.image_id)===String(im()?.image_id));current.forEach((trace,index)=>{const tr=document.createElement('tr'),m=polylineMetrics(trace.points);cell(tr,'Manual '+(index+1));cell(tr,String(trace.points.length),'num');cell(tr,fmt(m.waviness),'num');cell(tr,fmt(m.straightness),'num');cell(tr,fmt(m.length,1),'num');cell(tr,fmt(m.chord,1),'num');cell(tr,trace.note||'—');const td=cell(tr,''),button=document.createElement('button');button.textContent='Delete';button.className='danger';button.onclick=()=>{if(!confirm('Delete this manual polyline?'))return;manualTraces=manualTraces.filter(t=>t.trace_id!==trace.trace_id);persistManual();};td.append(button);body.append(tr);});if(!current.length){const tr=document.createElement('tr'),td=cell(tr,'No saved manual polylines for the current image.');td.colSpan=8;body.append(tr);}}
$('startManual').onclick=()=>{manualDrawing=true;manualDraft=[];$('manualNote').value='';$('showManual').checked=true;updateManualDraft();};
$('undoManual').onclick=()=>{manualDraft.pop();updateManualDraft();};
$('cancelManual').onclick=()=>{manualDrawing=false;manualDraft=[];$('manualNote').value='';updateManualDraft();};
$('saveManual').onclick=()=>{if(!im()||manualDraft.length<2||polylineMetrics(manualDraft).chord<=0)return;const image=im();manualTraces.push({trace_id:String(image.image_id)+'_manual_'+Date.now()+'_'+Math.random().toString(36).slice(2,7),image_id:image.image_id,condition:image.condition,sample_id:image.sample_id,series_id:image.series_id,z_index:image.z_index,points:manualDraft.map(p=>p.slice()),note:$('manualNote').value,created_at:new Date().toISOString()});manualDrawing=false;manualDraft=[];$('manualNote').value='';persistManual();updateManualDraft();};
$('clearManual').onclick=()=>{if(!confirm('Clear all saved manual polylines for this analysis? Download a CSV backup first.'))return;manualTraces=[];persistManual();};
$('exportManual').onclick=()=>{const fields=['analysis_id','image_id','condition','sample_id','series_id','z_index','manual_trace_id','estimator','point_count','raw_polyline_contour_length_px','end_to_end_px','raw_polyline_waviness','raw_polyline_straightness','points_original_xy_px_json','endpoint_protocol','note','created_at'];const lines=[fields.join(',')];for(const trace of manualTraces){const m=polylineMetrics(trace.points);lines.push([runId,trace.image_id,trace.condition,trace.sample_id,trace.series_id,trace.z_index,trace.trace_id,'clicked_polyline_no_smoothing_no_resampling',trace.points.length,m.length,m.chord,m.waviness,m.straightness,JSON.stringify(trace.points),'Choose one identifiable continuous fiber; stop before ambiguous crossings, signal gaps, or image boundaries; click centerline sequentially from chosen start to chosen end.',trace.note||'',trace.created_at||''].map(csvValue).join(','));}const blob=new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='fiber_waviness_manual_polylines_'+new Date().toISOString().slice(0,10)+'.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('export').onclick=()=>{const fields=['analysis_id','image_id','condition','sample_id','series_id','z_index','segment_id','auto_status','manual_decision','manual_note','contour_length_px','end_to_end_px','waviness','straightness','flags','reviewed_at'];const lines=[fields.join(',')];for(const image of images)for(const s of image.segments||[]){const d=decisions[key(image,s)]||{};const row=[runId,image.image_id,image.condition,image.sample_id,image.series_id,image.z_index,s.segment_id,autoStatus(s),d.decision||'',d.note||'',s.contour_length_px,s.end_to_end_px,s.waviness,s.straightness,flags(s),d.reviewed_at||''];lines.push(row.map(csvValue).join(','));}const blob=new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='fiber_waviness_manual_review_'+new Date().toISOString().slice(0,10)+'.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
function summaryTable(id,title,summary){const root=$(id);if(!Array.isArray(summary)||!summary.length){const p=document.createElement('p');p.className='small';p.textContent=title+': not provided';root.append(p);return;}const h=document.createElement('h3');h.textContent=title;h.style.fontSize='14px';root.append(h);const keys=[...new Set(summary.flatMap(row=>Object.keys(row)))];const wrap=document.createElement('div');wrap.className='table-scroll';const table=document.createElement('table'),thead=document.createElement('thead'),hr=document.createElement('tr');for(const k of keys){const th=document.createElement('th');th.textContent=k;hr.append(th);}thead.append(hr);table.append(thead);const body=document.createElement('tbody');for(const row of summary){const tr=document.createElement('tr');for(const k of keys){let value=row[k];if(value&&typeof value==='object')value=JSON.stringify(value);cell(tr,typeof value==='number'?fmt(value,4):str(value));}body.append(tr);}table.append(body);wrap.append(table);root.append(wrap);}
for(let i=0;i<images.length;i++){const option=document.createElement('option');option.value=String(i);option.textContent=[str(images[i].image_id),str(images[i].condition),'Sample '+str(images[i].sample_id),'z '+str(images[i].z_index)].join(' · ');$('imageSelect').append(option);}
const limits=Array.isArray(meta.limitations)?meta.limitations:[];for(const limit of limits){const li=document.createElement('li');li.textContent=typeof limit==='string'?limit:JSON.stringify(limit);$('limits').append(li);}
$('scopeNote').textContent=images.length<Number(meta.analysis_image_count||images.length)?'This interactive reviewer embeds '+images.length+' representative fields. The full analysis contains '+meta.analysis_image_count+' images. Manual-review CSV exports from this page cover only the embedded fields.':'This interactive reviewer embeds all '+images.length+' analyzed images.';
$('runId').textContent=' Analysis ID: '+runId;
summaryTable('seriesSummary','Series summary',DATA.series_summary);summaryTable('sampleSummary','Sample summary',DATA.sample_summary);persist();loadImage();
</script>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", nargs="?", type=Path, default=Path(__file__).with_name("report_data.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", action="store_true", help="Embed only automatic-QC and needs-review paths; preserve recorded summaries")
    args = parser.parse_args()
    print(generate_report(args.json_path, args.output, compact=args.compact))


if __name__ == "__main__":
    main()
