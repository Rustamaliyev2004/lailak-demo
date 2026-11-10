# Lailak: executed improvements
Prepared 10 November 2026.

## Working application
http://127.0.0.1:8502
Upload PDFs and scans; extract fields; compare a funding request with supporting invoices; inspect source pages; export JSON or printable HTML.
Local Apple Vision OCR is the default for uploads. Baidu Unlimited OCR 2 is available live only for generated samples. No bank or private uploaded record is sent to that public demo.

## Measured results
- Local extraction regression: 69/72 exact fields across 12 generated documents, English/Russian/Uzbek Latin; 9/12 complete documents.
- Fresh frozen-parser layout challenge: 36/36 fields across 6 new generated documents; parser fingerprint unchanged during evaluation.
- Baidu official-model trials: 18/18 fields across three generated pages, one in each language. Raw outputs and observed timings are saved.
- Clean funding packet: no consistency flags. Altered packet: repeated invoice + support-total mismatch, with source file/page citations.
- Seven document-rule regression tests, two satellite-filter tests and a complete Streamlit interaction test passed.

## Limits of the numbers
All documents are synthetic. The original regression was used to improve the parser, and that first failing run remains in initial_results.json. Templates share known label families. The new challenge used different layouts after a parser freeze but is still generated internally. These results do not establish accuracy on genuine bank documents. Three field errors from the regression remain visible and flagged for review.
The official Baidu trial is small and uses different examples from the full local regression. Do not rank the models from those numbers.
The local OCR engine needed serialisation and caching after concurrent calls stalled. Test output and source are retained.

## Satellite repair and rerun
40 usable radar site-observations and 45 usable optical site-observations across 5 areas. Multiple areas share acquisition dates; these are not independent satellite acquisitions or labelled validation cases.
Radar: fixed Sentinel-1A relative orbit173, ascending, IW. Case-normalised platform identifiers.
Optical: common20m scene-classification grid, clouds/shadows/snow excluded, surface-reflectance baseline offsets applied.
Bounded April/October sample; missing dates remain missing. Every acquisition, quality result and frozen sampling plan is saved.
A residential control and field illustration were included. No independently confirmed construction stage, crop identity, fraud or loan outcome is available. The rerun repairs comparability and calibration, not predictive accuracy.

## What still requires outside evidence
A banker assessment and a bank-data pilot have not occurred. BANK_PILOT_BRIEF.md contains the interview, data request, proposed evaluation and stopping criteria. No messages were sent.
The app runs locally. It has not been publicly hosted. A reviewer can inspect the supplied files without running code, or run it on macOS from source. Browser visual inspection was blocked by the local-file preview policy; programmatic interaction tests passed.

## Source records
benchmark/results.json
benchmark/initial_results.json
benchmark/frozen_holdout/manifest.json and results.json
benchmark/baidu_probe_result.json
benchmark/baidu_language_results.json
benchmark/app_test_results.json
satellite/frozen_plan.json, manifests, observations and monthly CSVs

## Product scope
Lailak helps a bank reconcile the evidence behind a construction-loan funding request. Satellites supplement documentary and site evidence. Buyer escrow release after commissioning is separate from a bank's loan-tranche decision.

## Final cloud-service limitation
The anonymous official Baidu demo quota was exhausted after the three successful language trials. A later end-to-end test of the integrated live adapter on a new sample was blocked. That failure is saved in baidu_adapter_check.json.
The adapter's event-decoding logic passed a replay test against an actual prior response; this does not count as another model inference.
The app disables the currently blocked cloud option and directs the reviewer to the working local OCR and saved model outputs. A dedicated production Baidu endpoint is not deployed.
