# Phase 7 — judge-ready runbook (controlled prototype)

## What this version demonstrates

A **single active shopping session**, three **fixed SKU zones**, camera-based shelf occupancy (optional), simulated weight confirmation (optional), real barcode/mocked barcode scan, a quantity discrepancy, and **mock** exit billing. This is not unattended theft detection, identity tracking, a real shelf sensor, or real charging.

## Start (Windows PowerShell)

In Terminal 1:

```powershell
cd "$HOME\Desktop\SmartCart-AI\backend"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

In Terminal 2:

```powershell
cd "$HOME\Desktop\SmartCart-AI\frontend"
npm install
npm run build
npm run dev
```

Open http://localhost:5173. If build fails, capture the exact terminal output.

## 2-minute reliable walkthrough (no camera)

1. Open **Shopper app** → **Phase 7: Five-step judge walkthrough** → **Reset demo**. Camera zones must be restocked when using a webcam.
2. Open **Shelf operations** and manually **Pickup Shampoo**. Explain this is the fallback simulator (not a camera reading).
3. Return to **Shopper app**, simulate customer reaching exit **before scanning**. Show the **review-required** result, audit entry and unscanned cart.
4. Use **Demo scan** on Shampoo. Physical quantity 1 matches scanned quantity 1; ₹199 total.
5. **Simulate customer reaching exit** again. Show one mock receipt. Trigger the exit a second time to show the same receipt (no double billing).

These steps are marked complete based on genuine backend events. For a presentation, do not perform extra tests before this walkthrough unless you reset the session.

## Camera walkthrough (real webcam required)

1. Set webcam stationary and keep lighting constant; place one distinct object in each of A / B / C.
2. Open Operations, **Start camera**. With all zones empty, select **Capture empty**.
3. Stock all three zones, keep hands away and select **Capture stocked**.
4. Check the **Camera health** line: no weak calibration zones, frames arriving and the processed count incrementing.
5. Remove Shampoo, move your hand completely away, wait for four consistent frames. Camera can be fooled by shadows/occlusion; inspect events.
6. Scan the demo shampoo barcode and simulate exit.
7. If camera reports rejection, it has *not* applied an accepted cart event. Stop the camera, inspect the rejection message, reset and restock before retrying.

Camera processing is only fixed-position image template comparison. YOLO tracking is an optional **overlay** and does not identify retail SKUs or authorize checkout.

## Two-signal fusion variant (simulated weight only)

- In Operations, reset session and enable **2-signal mode**.
- Either remove Shampoo using the *real calibrated camera*, **or** click **Camera pickup** — not both.
- Select **Remove weight** under Shampoo to provide the simulated shelf weight signal. Only then does the physical cart increase.
- Do not clear ambiguous weights as if healthy; provide a fresh stable weight sample. Pending or uncertain evidence blocks checkout.
- Return needs **Camera return + Restock weight** and, if scanned, removal of one digital scan.

## Limitations and safety

- This is designed for a local demo; the API has **no authentication**. Do not publish it on a public internet URL.
- Only one customer and one object per monitored shelf zone are modeled; no multi-customer matching or real shelf sensors.
- Camera and SKU similarity under real lighting require manual validation on the target device.
- All receipts are simulated; no payment method is attached.
- If frontend `npm install` or `npm run build` does not succeed locally, the release must not be presented as frontend-validated.

## Acceptance commands

```powershell
cd "$HOME\Desktop\SmartCart-AI\backend"
python -m pip install -r requirements-dev.txt
python scripts/run_phase7_acceptance.py
```

Tests use a separate temporary database and **synthetic JPEG frames**, not live hardware. Generated JSON report: `reports/phase7-acceptance.json`.
