# Synthetic validation

75 fixed checks; 0 failures. The results apply to the source SHA-256 recorded in `validation_results.json`.

These checks cover ordered straight, circular-arc and sinusoidal traces; reciprocal metric definitions; rigid transforms; scaled smoothing; degenerate endpoints; raster angle/width bias; and clean/noisy intensity images containing curves, a crossing, a gap, and an image boundary. The fixed seed is 20261120. No thresholds were changed after seeing these results.

Maximum ordered-trace relative waviness error: 0.133%. The clean synthetic-intensity line, arc and sine errors were 0.072%, 0.223%, 0.787%. These are errors for the fixed synthetic geometries, not uncertainty estimates for real images.

**Limits:** this is numerical and synthetic validation, not validation of biological fiber identity. The noise-only image generated many short rejected paths and a substantial mask area despite yielding zero accepted long paths. Consequently, detected mask area must not be interpreted as collagen density. Automatic QC acceptance is not manual confirmation. Smoothing variation is a parameter sensitivity, not a confidence interval. Physical calibration must be applied before lengths can be reported in micrometres.

The image montage uses green for automatic-QC accepted, amber for review, and gray for rejected paths.
