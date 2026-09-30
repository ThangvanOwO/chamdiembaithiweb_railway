# GradeFlow Web Academic v1 — implementation and verification

## Outcome / scope

Implemented a public teacher-oriented website with an academic navy/teal/paper
visual identity, a simplified authenticated workspace, help and an actual APK
download. The website uploads images and Excel answer keys; Live Camera belongs
to the Android application. No recognition/scoring engine, mobile code, data
models, authentication behavior or grading API contracts were changed by this task.

The repository already had substantial unrelated changes and a deleted web
`live_camera.html` before this task. Those changes remain untouched.

## Reference research

- [Azota](https://azota.vn/): clear product entry points, teacher-oriented messaging,
  login and guidance navigation. Adopted task-first navigation, not its text,
  branding, customer counts or accuracy/speed claims.
- [UnT answer sheets](https://untedu.com/tai-cac-phieu-tra-loi-trac-nghiem/): groups
  resources by sheet format and places usage guidance alongside downloads.
  GradeFlow's guide explains selecting a matching supported template and testing
  a sample first. UnT's sheets were not copied or advertised as compatible.

## Routes and user journeys

| Route | Purpose |
|---|---|
| `/` | Public homepage: prepare answer key, upload papers, download mobile app |
| `/huong-dan/` | Guide, actual Excel schema, image quality, templates, mobile setup, FAQ |
| `/tai-ung-dung/` | Stable APK, device requirements, server setup and installation guidance |
| `/downloads/gradeflow.apk` | GET/HEAD streaming of the configured stable APK |
| `/dashboard/` | Existing authenticated teacher dashboard with new task cards |
| `/grading/upload/` | Existing image upload/grading form; browser camera removed |
| `/grading/exams/import/` | Existing answer-key image/Excel import; browser camera removed |
| `/chamtn/` | Compatibility redirect to normal image upload; no alternate camera UI |

Only the navigation entry to the experimental ChamTN interface was retired. Its
source/assets and APIs remain on disk for compatibility/recovery. No exams or
submissions were deleted.

Excel is **answer-key import**, not a replacement for uploading student paper
images. The guide matches the current parser: first column is variant code,
numeric P1 headers, `1a…` P2 headers, numeric P3 headers after P2. It documents the
P3-without-P2 limitation instead of silently changing the parser. Keep leading
zeros by storing variant codes as Excel text.

## BUG FIX REPORT

- **ROOT CAUSE:** sidebar referenced the removed `grading:live_camera` route,
  causing authenticated rendering to fail. Upload and import retained separate
  browser-camera implementations, conflicting with the requested platform split.
  The import stepper's nowrap content expanded its flex parent at 768 px.
  Disabling animation without restoring final opacity hid staggered statistics
  for reduced-motion users; browser screenshots caught this during implementation.
- **FILES CHANGED:** `website/{views,urls,tests,test_web_contracts}.py`,
  `templates/website/*`, `static/css/{website,academic-web}.css`, root URL config,
  base/sidebar/navbar, dashboard, upload/import and login/register templates,
  `static/js/{app,sw}.js`. QA scripts are under `tools/diagnostics/`.
- **CHANGES MADE:** separate public pages, actual release endpoint with fixed
  server-selected path, missing-file handling and attachment headers; remove web
  camera controls/state/CSS/JS; replace broken navigation; consolidate duplicate
  dashboard actions; responsive/focus/reduced-motion rules; preserve zero-valued
  statistics with `default_if_none`; guard JS motion for reduced-motion users.
- **TESTS RUN:** `python manage.py test website --verbosity 0` (29 pass);
  `python -m unittest discover -s tests -p test_answer_image_import.py` (12 pass);
  `python tools/diagnostics/render_web_fixtures.py` then
  `node tools/diagnostics/web_academic_qa.cjs` (36 page/viewport combinations pass);
  `python manage.py collectstatic --noinput --verbosity 0` (pass);
  scoped `git diff --check` (pass); HTTP APK HEAD (200, 46,570,842 bytes);
  local APK SHA-256 checked against stable release; existing
  `tools/diagnostics/restore_live_speed.ps1` verify-only (ready, 8 files).
- **TEST RESULTS:** public routes/links/anchors and APK missing/error/HEAD cases
  pass; authenticated upload/import form fields, CSRF and endpoint contracts pass.
  Four widths: 1440, 768, 390 and 360 px. Nine pages: home, guide, download, login,
  register, dashboard, upload, import and exams. No horizontal overflow or JS
  errors. Upload file selection/removal, mocked import error, mobile navigation
  and reduced-motion statistic visibility pass. 404/405 logs in negative tests
  and deliberately rejected import payloads are expected.
- **REGRESSION RISK:** low for OMR because its code and contracts are unchanged;
  moderate for navigation/cache changes. `/` now shows a public homepage, while
  `/dashboard/` remains the workspace. `/chamtn/` now redirects. Returning browsers
  receive a new worker which retires only GradeFlow-prefixed old caches. Private
  HTML/API responses and APKs are no longer cached; offline grading is not promised.
- **UNRELATED ISSUES FOUND:** existing APK LAN server default and development
  signing configuration need a production release plan. Existing Excel P3 parsing
  limitation is documented, not modified. A local missing `staticfiles` warning
  was resolved by successfully running collectstatic.

## Verification limits

Authenticated browser screenshots use unsaved, database-free template fixtures;
the import response and chart library are mocked in the visual tests. They prove
the UI interaction, not a new full grading run. Existing import regression tests
were run separately. No real exam/grade records were created for QA. No camera,
phone installation, Internet-hosted deployment or production network benchmark
was performed. Desktop app browser-control initialization failed; visual QA used
the available bundled Playwright with headless Chrome instead.

Screenshots and `results.json`: `scratch/web_academic_qa/`.
Preview server: `http://127.0.0.1:8013/` (local machine only).

## Release and rollback

See `releases/README.md` for the exact binary, deployment and signing requirements.
APK binaries are Git-ignored and must be deployed separately. Missing APKs produce
an honest unavailable state, not a dead advertised download.

Original modified web files are copied under
`scratch/restore_points/before_web_academic_20260913/`; `web-changes.json` records
before/after hashes and the new-file list. To roll back on user request: first
check current hashes, preserve any later edits, then restore only the named web
files from that checkpoint and retire only task-created web files. Do not use a
repository reset. Restoring the exact old sidebar also restores its stale camera
link, so review that compatibility issue when choosing a rollback target.

The mobile speed-trial checkpoint and rollback script are separate and were
verified intact. This web task does not replace that path back to stable mobile.
