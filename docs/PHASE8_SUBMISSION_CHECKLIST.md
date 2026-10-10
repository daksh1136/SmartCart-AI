# Phase 8 — Submission & Validation Checklist

**Purpose:** Prepare a persuasive hackathon entry without confusing implemented code with verified physical hardware.

## Ready in this package

- [x] Project abstract and proposed approach
- [x] Architecture diagram (PNG / SVG / editable Mermaid)
- [x] Pitch deck (PowerPoint)
- [x] 2-minute demo and judge Q&A script
- [x] Reorganized README with setup and limitations
- [x] Phase 7 backend acceptance report (22 passed at Phase 7 handoff)

## To validate on your Windows laptop

- [ ] Backend starts with `python -m uvicorn main:app --reload --port 8000`
- [ ] `python scripts/run_phase7_acceptance.py` reports PASS locally
- [ ] `npm install`, `npm run build` and `npm run dev` succeed inside `frontend`
- [ ] Two complete five-step judge-demo walkthroughs succeed
- [ ] Blocked exit produces **no** mock receipt
- [ ] Matching scan allows mock receipt; repeat exit uses **same** receipt ID
- [ ] Camera calibration, pickup and return are tested on your actual webcam, or camera is clearly labeled experimental
- [ ] Smartphone barcode scan validated on a trusted HTTPS origin **or** demo uses barcode input/buttons
- [ ] Record a 90–120-second demo video from a working local run
- [ ] Capture 2–4 clear screenshots of the actual app
- [ ] Attach GitHub repository URL, team details and live demo URL **only if working and secure**
- [ ] Check event rules/eligibility, required slide count, file size and submission portal fields

## Exact release claim

> “We built a single-session Scan & Go prototype that independently reconciles shelf-side events and mobile barcode scans, demonstrates discrepancy-safe mock checkout, and supports experimental webcam monitoring with simulated weight sensor fusion. Backend tests cover the workflow; physical hardware and multi-customer use remain future development.”

## Important prohibitions for the presentation

- Do **not** claim a measured retail shrink reduction or a validated accuracy percentage.
- Do **not** imply mock billing moves money.
- Do **not** represent simulated sensor buttons as installed hardware.
- Do **not** imply YOLO identifies all SKUs or proves theft.
- Do **not** publicly expose the unauthenticated demo API.
