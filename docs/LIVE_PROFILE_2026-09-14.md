# Live profiling: recognition reuse and measured bottlenecks

## Scope

Diagnostic work only. No production engine, API, Flutter, template, thresholds,
database or camera settings changed. All monkey patches are limited to a separate
offline process. Original fixture and corner metadata are preserved; generated
images and even automatic ketqua copies go inside the diagnostic run directory.
Engine text logs still print their original intended copy paths; the actual copies
are `auto_*` files inside each run directory.

Input: `tests/fixtures/exam_import_v1.jpg` with matching `.json` corner coordinates.
Flags: `fast_mode=True`, `live_bubble_mode=True`, template `40-08-06`.
This is one original JPEG replayed locally, NOT the actual request behind the
user's 3.5-second screenshot. No network/DB latency or on-phone profiling included.

## 1. Does changing variant require another recognition pass?

No, provided the image, template/calibration, part counts and recognition settings
are identical. Source evidence:

- `api/views.py:539` calls `grade_image` using the first variant.
- `api/views.py:560` calls it again if the matched variant's answer string differs.
- `grading/engine/hi.py:3990` first consults `correct_answers` only AFTER recognition
  and validation, for `grade_part1/2/3` and result drawing.
- `grading/grader.py:280` can obtain `parts_config` from answer-key JSON. Therefore
  recognition configuration must be separated/compared explicitly; reusing data
  across a changed question limit is not automatically equivalent.

Experiment: derive a synthetic answer key from the observed reading, then change
Q1 in a second key. Full reruns preserve SBD, code, all answers, detailed evidence,
offsets, confidence, method and warnings. Reusing the original in-memory answers
and calling existing `grade_part1/2/3` produces the SAME three raw part scores as
the full second pipeline, verified 100 times. This is not a new official answer
key and does not establish ground-truth accuracy for every cell.

Rescoring the cached reading (including answer-key parsing) averaged 0.306 ms in
the final run. It does NOT include weighted-score calculation, result image
regeneration, DB persistence or the HTTP response. The existing weighted-score
function must consume the newly computed scores and the matched key afterward.

Implementation boundary proposed, NOT implemented:

1. Recognize once, retaining answers, uncertain/multiple states, confidence,
   corners, warped paper/evidence, offsets and exact recognition configuration.
2. Match the detected variant; compare with its answer key using the existing
   comparison functions and existing weighting configuration.
3. Render annotations once against the FINAL key. Never return an old result image
   whose circles/score were rendered against the first key.
4. Retain this context inside ONE request; do not use a global previous-frame
   cache. Missing/different configuration requires explicit handling.

This eliminates a full pass ONLY when the different-key branch executes. If 001
is already the first variant, it will not improve that single-pass request.

The current `processing_time` measures one `grade_image` call, and API reassignment
retains the final call's time. It does not sum both passes, upload, preparation,
DB work or response transport. End-to-end timing and pass count are needed too.

## 2. Measured breakdown

Final run: `scratch/live_profile_20260914_b/report.json`.
Three alternating debug-on/off pairs after a separate cold run. Tables use
`perf_counter` exclusive timings so nested functions are not counted twice.
A separate cProfile run is excluded from these averages.

| Measured work, debug ON | Mean |
|---|---:|
| Entire grader call | 4,122.15 ms |
| Gaussian blur, sigma 120 | 3,125.66 ms |
| Non-local means denoising | 570.74 ms |
| Gaussian blur, sigma 30 | 90.05 ms |
| Other preprocessing (exclusive) | 120.28 ms |
| Read input JPEG | 14.84 ms |
| Grid alignment | 18.51 ms |
| Live identifiers | 30.37 ms |
| Read P1 / P2 / P3 | 7.30 / 12.41 / 54.79 ms |
| Draw debug grid | 6.35 ms |
| Write four debug JPEGs | 24.37 ms |
| Write result / overlay JPEG | 10.10 / 6.00 ms |
| Compare answers within full call | 0.039 ms |

This table lists selected categories, not every category. Marker coordinates were
already supplied, so this does NOT benchmark finding four corners in a camera
stream. Rendering, image blends and forward/inverse transforms are also measured
in the JSON rather than conflated with debug writes.

Debug draw + write: **30.71 ms, about 0.75%** of this run. Removing debug cannot
explain saving several seconds here. Debug-on total averaged 4,122.15 ms versus
4,111.76 ms off: the 10.40 ms wall difference is affected by run-to-run CPU/filter
variation, not a reliable isolated estimate of debug cost. Use the direct stage
measurements for attribution. A prior independent three-pair run found ~31.44 ms
debug work; it is retained in `scratch/live_profile_20260914_a/`.

All paired runs retained identical recognition and evidence with debug disabled.
This sample alone is not enough to change a shared engine default safely.

## 3. Actual dominant path

`preprocess(..., mode='fast')` automatically switches to `phone` mode when
`_is_phone_camera` returns true (`hi.py:1954–1961`). In phone mode it runs full-size
non-local means and multi-scale Gaussian background estimation, including
**sigma 120** (`hi.py:2003–2012`). That blur alone is ~76% of measured time.

The outer process log says `Preprocess FAST`, and the returned mode may still say
`fast`, because the caller does not observe the internal local-mode switch. Thus
the existing log label is insufficient proof that the inexpensive path ran.
The recorded sigma-120 and denoising calls establish the actual path on this image.

cProfile artifact: `cprofile_debug_on/pipeline.prof` and `profile.txt`. Its separate
run confirms GaussianBlur and fastNlMeansDenoising dominate native CPU work.
Do not sum cumulative timings from nested frames. The exclusive monotonic timer
measurements are the attribution used above.

## 4. Priority justified by measurements

1. Separate recognition from key comparison: low algorithmic risk, large savings
   on different-key requests. Test final weighted score AND final image consistency.
2. Investigate full-resolution sigma-120 background filtering: biggest opportunity
   on ordinary single-pass requests. Benchmark equivalent optimized filtering;
   any downsample/filter/upsample approximation requires image and OMR parity tests,
   particularly faint marks, shadows and P1. Do not disable phone preprocessing or
   lower recognition thresholds merely to improve time.
3. Make debug artifacts opt-in for Live after validation, retaining a diagnostics
   path. Useful cleanup, but a secondary performance gain in this measured case.
4. Instrument the full request, both passes, serialization and mobile transport
   on the actual device/server before promising a sub-second result.

## Reproduction and validation

```powershell
python tools/diagnostics/profile_live_pipeline.py --output scratch/live_profile_NEW --pairs 3
python -m unittest discover -s tests -p test_live_profiler.py
```

Output must be a new directory inside the workspace; the script refuses an
existing directory. Three instrumentation tests cover nested exclusive accounting,
exception propagation/stack cleanup and debug-vs-result image classification.
The benchmark asserts reading/evidence equality across debug toggles/key changes,
and raw-score parity for cached recognition. No source image, exam or submission
record is overwritten. Broader historical-image/device acceptance remains pending.
