# Live Camera speed v1 — reversible experiment

## Tóm tắt bàn giao

- Đã build APK thử nghiệm số 2009, mặc định vẫn dùng **Ổn định**.
- Bật thử ở **Chấm điểm → Live Camera → Bộ xử lý → Thử nghiệm — tăng tốc marker**.
- Trở về bản cũ bằng lựa chọn **Ổn định**, hoặc yêu cầu khôi phục mã nguồn theo
  mốc đã lưu. Không gỡ app, không xóa dữ liệu.
- Đo trên Windows: bước chuẩn bị ảnh giảm trung bình 25,4%; chưa đo Android.
- Đây là bước tăng tốc marker sau chụp, chưa phải engine chấm offline tức thì.

## APK đã xác minh

- File: `gradeflow_app/build/app/outputs/flutter-apk/gradeflow-live-speed-v1-2009-arm64.apk`
- Size: 46,767,666 bytes, arm64-v8a, minimum SDK 24.
- SHA-256: `0AA54ABBFCC0DC92E2D67C2370B5FE0AC239650B2B72573B43D49D776E46C4D6`.
- Package: `com.gradeflow.gradeflow_app`.
- Flutter build number 2009; actual APK **versionCode 4009**, verified by aapt.
  Flutter split-per-ABI adds the ARM64 offset; these numbers are not identical.

## Status and scope

This is the first, byte-preserving performance step, NOT the complete on-device
OMR/instant-result architecture. Preview detection, its 500 ms stability gate,
manual shutter, camera resolution, JPEG orientation/resize/quality, network
grading, answer recognition and scoring are unchanged. No GPU, TFLite model or
competitor code/assets were added.

Only the normal **Chấm điểm → Live Camera** entry point exposes the experiment.
Import, batch and admin camera callers default to `allowSpeedTrial: false` and
continue calling the original `prepareLiveCapture`. Upload and exam creation
services/backend were not changed.

APK 2009 defaults to **Bộ xử lý: Ổn định**. Tap that selector and choose
**Thử nghiệm — tăng tốc marker** to opt in. Selecting **Ổn định — bộ xử lý cũ**
returns to the original implementation without reinstalling. Selection persists.
An explicit `LIVE_SPEED_DISABLED=true` build disables the trial regardless of
stored preference. `LIVE_SPEED_TRIAL=true` exists for controlled test builds;
it is NOT enabled in the delivered APK.

## What changed

- New `lib/services/live_speed/native_still_detector.dart` accelerates local
  box sums, double-precision threshold operations and 8-connected labeling with
  OpenCV already bundled by the project's existing dependency.
- Means use the actual clipped window population, not reflected borders.
  Arithmetic retains the legacy contrast floor 12, fractions 0/0.3/0.5 and
  strict less-than comparison. No uint8 rounding of decision thresholds.
- CCL_WU/SAUF preserves row-major component discovery order. Original square
  shape check, density, size, quartet ranking and ambiguity rejection are kept.
- Matrices are explicitly disposed in `finally`; no native pointer or borrowed
  camera buffer crosses the isolate boundary. One accepted JPEG is processed in
  a worker, not on the UI thread. No second engine continuously runs in parallel.
- Decode, orientation, grayscale, content gate and JPEG encode intentionally
  remain equivalent to the stable function. The new profiler reports each stage.
- Native preparation failure retries the SAME raw JPEG once through the original
  stable function. It never substitutes old preview corners or bypasses validation.
  If the native runtime fails and stable validation also rejects, both failure
  reasons survive the worker boundary and the camera disables/persists off the
  broken native engine. A valid fallback also persists the stable selection.
- Opening the engine selector suspends detection/capture eligibility; changing
  mode clears readiness. In-flight analysis cannot update readiness while the
  selector is open or a preference write is pending.
- Conditional import avoids adding dart:ffi/OpenCV dependencies to Flutter web.

## Evidence: measured, not estimated

`tests/ketqua/live_speed_v1/final-benchmark.json` records six paired runs:
two unannotated source JPEGs, three repetitions each. Platform is Windows Flutter
test/JIT with locally built dartcv/OpenCV 4.12. These are NOT Android release,
camera, network, full grading, p95, thermal or power benchmarks.

| Stage (arithmetic mean of 6 runs) | Stable | Native experiment |
|---|---:|---:|
| Marker detection | 399.9 ms | 220.6 ms |
| Entire JPEG preparation | 720.5 ms | 537.6 ms |

Marker time decreased 44.8%; total preparation time decreased 25.4% in that run.
All six pairs produced **identical JPEG bytes, dimensions and corner coordinates**.
Input images: `tests/fixtures/exam_import_capture_20260912.jpg` and
`tests/fixtures/exam_import_v1.jpg` (not result overlays).

The initial native attempt was slower: it repeatedly allocated/copy-converted
large matrices and still performed the threshold loop in Dart. Its diagnostic
reports are retained (`benchmark.json`, `benchmark-optimized.json`,
`benchmark-stages.json`). The final implementation reuses per-radius means,
avoids Mat.fromList's extra conversions, and performs thresholding in native
double precision. Library inclusion alone did not produce a speedup.

## Verification

- Native-specific suite: **18 passed**, including same-output comparisons,
  missing corners, circles with blur, blank/clipped/ambiguous frames, seeded
  noise, illumination gradient, rotation and EXIF orientations 1–8.
- Combined Flutter Live/import/UI regression: **53 passed, 7 skipped**. Skipped
  cases are pre-existing optional LIVE_SCREENSHOT/LIVE_OVERLAY fixtures, not
  disabled assertions or skipped native tests.
- Deliberately missing native DLL: **3 passed**; exact legacy fallback, corrupt
  input rejection and native failure plus legacy rejection across an isolate
  are verified in a separate process.
- Flutter targeted analyzer: no issues at the final review before packaging.
- Backend exam-import regression: **12 passed**. Expected error-case logging
  appears during tests; no database write or backend deployment performed.
- Backend identifier regression: **6 passed, 1 failed because fixtures missing**.
  The separate bubble-reader suite fails setup for the same missing fixtures.
  Five `media/submissions/2026/09/live*.jpg` originals referenced by the 11 Sep
  log are absent. Existing diagnostic warped images cannot replace those JPEGs
  for a faithful full replay. Tests were not weakened or rewritten to hide this.
- SHA-256 comparison confirms 12 protected files unchanged from the checkpoint,
  including both old detectors, old JPEG preparation, Live transport, Upload
  service, import service/screen/backend, template reader and pubspec.yaml.
- Restore tool fixture test: dry run, all-file conflict guard, exact restoration,
  recoverable quarantine and repeat/idempotent behavior all pass.
- ADB inspection: no connected device. No APK installed; no claim of measured
  speed, memory stability, preview FPS or accuracy across phones.

### Reproduce the native test

The diagnostic Windows wrapper DLL was built from the locally cached matching
dartcv source and installed OpenCV 4.12 SDK. It is NOT an APK asset. Its build
helper and build/configure logs are in `scratch/live_speed_native_windows/`.

```powershell
cd 'D:\chamtrac nghien v2\gradeflow_app'
$env:DARTCV_LIB_PATH = 'D:\chamtrac nghien v2\scratch\live_speed_native_windows\bin\dartcv.dll'
$env:PATH = 'C:\Users\Thang\Downloads\opencv\build\x64\vc16\bin;' + $env:PATH
& C:\flutter\bin\flutter.bat test --no-pub test/live_speed_test.dart test/live_capture_test.dart test/live_marker_detector_test.dart test/exam_import_service_test.dart test/academic_ui_test.dart
```

Use `--dart-define=LIVE_SPEED_REPORT=<absolute JSON path>` to save measurements.
Do not interpret concurrent desktop test timings as a phone benchmark.

For fallback verification, run `tool/live_speed_fallback_test.dart` with
`DARTCV_LIB_PATH` set to a deliberately nonexistent path, in a fresh process.

## Verified restore point — before_live_speed_20260912_234959

Location: `scratch/restore_points/before_live_speed_20260912_234959/`.

- `manifest.json`: 416 tracked/untracked source/config entries, original SHA-256,
  original git status/HEAD and pre-existing deletions. Dirty working versions
  were copied, not replaced with HEAD. This is NOT a database/media/full-disk
  backup; excluded generated caches, APK research/clones and datasets remain in
  place and are not targets of restoration.
- `source/`: verified original files.
- `stable-2008-arm64.apk`: stable APK before this optimization.
- Stable APK SHA-256:
  `04DAA6933B66B99AA06934F0E9C6C673199C53331BB4914DAD942847E2D52032`.
- `live-speed-changes.json`: exact eight-file app/test allowlist and after hashes.
  Diagnostics and this report intentionally remain after rollback.

Verify only (does NOT restore production files):

```powershell
& 'D:\chamtrac nghien v2\tools\diagnostics\restore_live_speed.ps1'
```

Only when the user asks to restore:

```powershell
& 'D:\chamtrac nghien v2\tools\diagnostics\restore_live_speed.ps1' -Apply
```

The tool checks ALL current and backup hashes before writing. Any later edit to
an affected file blocks automatic restoration and requires a selective merge.
Replaced/new trial files are retained in a timestamped recovery directory, not
deleted. No git reset, recursive delete, database change or app-data wipe.

**Android downgrade caveat:** do not uninstall the app to install APK 2008 over
2009. Runtime selector is the fastest rollback. For an exact source rollback,
restore the source and rebuild/sign with a versionCode higher than the installed
version. With the same ARM64 split build, `--build-number=2010` produces versionCode
4010, higher than this APK's 4009. Verify the packaged value before installing,
preserving application data and the same signing certificate.

## Android acceptance before enabling by default

1. Run the same paper at least 20 times in each mode, alternating order, same
   lighting, distance and device. Save `[LiveCamera timing]` and `[LiveSpeed timing]`.
2. Record median/p95 shutter, marker and total preparation separately from HTTP
   and backend grading. Include cold first call and at least five minutes of
   repeated scanning to check RAM, thermal throttling and battery impact.
3. Include faint marks, blank controls, all four missing corners, slight shake,
   SBD 011232 / code 001 / P3 Q5=22 and the original P2/P3 false-positive controls.
4. Exercise manual capture, background/resume, close during processing, selector
   menu while a sheet is aligned, and both runtime rollback and kill-switch build.
5. Require unchanged answers/unknown states plus meaningful p50/p95 improvement;
   do not trade recognition accuracy for speed. Recover missing original test
   JPEGs before claiming full historical backend regression coverage.

Next performance stages (not implemented): native JPEG preprocessing only after
pixel/OMR parity tests; live-frame OMR and local results only after backend-equivalent
algorithm validation. Network grading still exists in this version, so it does
not promise instant offline results or 60 full-sheet recognitions per second.
