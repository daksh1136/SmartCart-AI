# SmartCart AI — Scan & Go Loss Prevention (Hackathon Prototype)

**Pick → Detect → Confirm with simulated weight → Scan → Verify → Mock Checkout.**

A working single-session, three-SKU prototype that compares a *physical cart* (simulated shelf events or webcam image comparison) against a *mobile-scanned cart*. It flags quantity mismatches, blocks checkout if mismatched, and issues a **simulated** receipt when matching.

## What's implemented now

- Responsive React customer workspace and shelf operations dashboard
- Scan with phone/laptop camera using `@zxing/browser`, with manual input fallback
- Three *valid demo EAN-13* labels you can display or print from Operations
- FastAPI REST API and persistent SQLite prototype database
- Physical pickup/return simulation (works without camera or sensors)
- OpenCV fixed-zone webcam detection with two-point calibration (empty then fully stocked)
- Reconciliation, alerts, activity feed, and simulated checkout; session reset
- Two-signal fusion mode: camera pickup/return + simulated shelf weight change must agree before changing the physical cart
- Evidence waiting list, mismatch safety checks, checkout blocked while sensor evidence is unresolved
- Automated backend tests (including fusion scenarios)

Not included yet: actual weight hardware, **trained SKU classification**, multi-shopper association, secure payments, inventory integrations or production reliability. An optional YOLO tracking overlay and experimental reference-image appearance matching are implemented. Weight readings in fusion mode are simulated buttons, **not live hardware**.

## Prerequisites

- Windows 11 with **PowerShell**, Python 3.11–3.13, Node.js 20+
- A webcam for the camera demo (optional; simulator also works)
- Three physical objects and a stable camera position for the camera demo

## Start on Windows (PowerShell)

### Terminal 1 — Backend

```powershell
cd $HOME\Desktop\SmartCart-AI\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If your PowerShell blocks venv activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Then visit: http://localhost:8000/docs

### Terminal 2 — Frontend

```powershell
cd $HOME\Desktop\SmartCart-AI\frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your laptop browser.

Do not run `npm install` in the root `SmartCart-AI` folder: the `package.json` is inside `frontend`.

## Quick 60-second demo — NO camera needed

1. Open **Shelf operations** → click **Pickup** for Shampoo.
2. Open **Shopper app** → click **Demo scan** for Shampoo (or type `8901234500019`).
3. The cart reads **Physical 1 / Scanned 1 — Verified**.
4. In Operations, click **Pickup** for Biscuits but don't scan it. See mismatch.
5. Click **Return** for Biscuits (or scan it to resolve); mismatch clears.
6. Click **Complete mock checkout**. A receipt appears. No money is charged.
7. Click **Reset session** before replaying. Reset assumes all webcam zones have been restocked.

## Live webcam demo — fixed product zones

Use the **same laptop browser** to start the webcam under Operations.

1. Mount laptop webcam *without moving it* so it sees the entire tabletop.
2. Keep the view evenly lit. Divide table into left/center/right thirds. **Only one object per zone.**
3. Clear *all three zones*. Select **Start camera**, then **1. Capture empty**.
4. Put Shampoo on LEFT/A, Biscuits in CENTER/B, Cola on RIGHT/C. Move your hand away.
5. Select **2. Capture stocked**. Wait for **Shelf zones calibrated**.
6. Remove Shampoo and take your hand out of view. After several stable frames, the physical cart increments by 1.
7. In another tab (or on your phone) scan the matching printed barcode or press **Demo scan** in Shopper. Mismatch resolves.
8. Put Shampoo back; physical cart decrements. Remove the corresponding digital scan before checkout.

The method compares blurred image templates of each zone, sampled about twice per second. It requires a fixed camera angle, stable lighting, and substantial visual differences between empty and stocked references. It may flag hand occlusions, moved objects, or shadows; this is a **controlled demo**, not a robust retail vision system. Calibration with very similar empty/full images displays a warning. This code does **not** identify or track customers.

**Avoid using manual pickup simulation while camera detection is active for the same item**, or both can count the removal. Simulations and camera events use the same physical-cart ledger.

## NEW: Phase 3 — two-signal sensor fusion (no actual sensors required)

From **Shelf operations**, click **Enable 2-signal mode** under **Camera + simulated shelf weight**. Camera-only mode remains the default and the original demo continues to work.

**Quick demo without using a webcam:**

1. Click **Reset session** if you have previous test events, then enable fusion mode.
2. For Shampoo, click **Camera pickup**. A pending camera observation appears; the physical cart stays at **0** (the camera alone cannot verify the pickup).
3. Click **Remove weight** under Shampoo. The simulated shelf weight goes from **250g to 0g**. The camera and weight signal are now paired; physical cart becomes **1**.
4. Under Shopper app, **Demo scan** Shampoo. Cart reads **Physical 1 / Scanned 1 → Verified**, amount **₹199**. Mock checkout becomes available.
5. To test return before checkout: in Operations click **Camera return** then **Restock weight**. Physical cart goes back to 0. In Shopper, remove the digital shampoo scan to reconcile it.

**With a real webcam:** Instead of pressing **Camera pickup/return**, calibrate the webcam (empty, then stocked) and physically remove/return the object. Then use the simulated **Remove weight/Restock weight** button as independent evidence. Don't click the test camera button for a product that the live camera is already monitoring. All signals must agree on *product ID* and *action* within **120 seconds**.

**Mismatches and safety:** If Camera reports Shampoo but you drop Biscuits' simulated shelf weight, both signals remain pending and checkout is blocked. The UI provides **Clear pending evidence** for the operator to discard unmatched events; this does not alter the authoritative physical cart, and should only be used after investigating what happened. A mid-range ambiguous weight is marked uncertain. Reset session clears cart, all pending fusion signals, returns weights to their stocked references, and disables fusion mode for the next demo.

**Prototype limitations:** Our demo uses one product per zone, binary stocked/empty simulated weights, one customer, and ephemeral fusion state. It doesn't infer product identity from weight alone, securely link customers to shelf interactions, or detect actual theft. No real payment takes place.

## Printed barcodes

Open **Operations → Demo barcodes → Show labels → Print product labels**. Attach the three labels to physical objects. The examples are demo codes, not actual retail GS1 allocations:

| Zone | Product | Demo EAN-13 | Price |
| --- | --- | --- | --- |
| A | Shampoo | 8901234500019 | ₹199 |
| B | Biscuits | 8901234500026 | ₹20 |
| C | Cola | 8901234500033 | ₹40 |

Use the app's **Demo scan** buttons when testing on an HTTP LAN connection or without a second camera.

## Using a phone on the same Wi-Fi

The frontend Vite server binds to the network. On the laptop, run `ipconfig` in PowerShell and note its local IPv4 address. On the phone, connect to the same Wi-Fi and visit `http://YOUR-LAPTOP-IP:5173`. If Windows Firewall prompts, allow local/private networks for Node.js and Python. The Vite frontend transparently proxies `/api` calls to the laptop's FastAPI backend.

**Important camera limitation:** Mobile browsers generally require **HTTPS** to use `getUserMedia`. `http://localhost:5173` is trusted *only on the device running it*. Opening `http://YOUR-LAPTOP-IP:5173` on a phone often permits the website but **not the phone camera**. For the phone-camera scanning demo, use a trusted HTTPS deployment/tunnel with an HTTPS-compatible backend connection and appropriate access controls, or just use the manual barcode input on the phone. A frontend-only HTTPS tunnel pointed at a Vite server can proxy `/api`, but verify the HTTPS origin, route protection, and privacy before exposing any demo services. **Do not expose the backend publicly without authentication.**

## API endpoints

| Method | Route | Use |
| --- | --- | --- |
| GET | `/api/health` | Backend health |
| GET | `/api/status` | Products, both carts, discrepancies, events, vision status |
| POST | `/api/scan` | Body: `{"barcode":"8901234500019"}` |
| POST | `/api/unscan` | Body: `{"product_id":"shampoo"}` |
| POST | `/api/simulate` | Body: `{"product_id":"shampoo","action":"pickup"}` |
| POST | `/api/fusion/mode` | `{"enabled":true}` to require two signals (false disables) |
| POST | `/api/fusion/camera` | `{"product_id":"shampoo","action":"pickup"}` simulated camera observation |
| POST | `/api/fusion/weight` | `{"product_id":"shampoo","weight_grams":0}` simulated shelf sensor reading |
| POST | `/api/fusion/clear` | Discard pending unmatched fusion evidence (operator action) |
| POST | `/api/vision/calibrate/empty` | Raw JPEG captured with all zones empty |
| POST | `/api/vision/calibrate/full` | Raw JPEG captured with 3 objects in zones |
| POST | `/api/vision/frame` | Raw JPEG camera frame for occupancy detection |
| POST | `/api/checkout` | Simulated checkout, rejects mismatch |
| POST | `/api/reset` | Clear demo cart, events, receipt; rearm vision state |

## Backend tests

```powershell
cd $HOME\Desktop\SmartCart-AI\backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Architecture

```text
React + Vite (Shopper)          React + Vite (Operations)
Barcode scan + manual input    Laptop camera + zone overlay
          |                    |             |
          |              JPEG snapshots    Simulator buttons
          |                    |             |
          +--------------------+-------------+
                               |
                         FastAPI REST API
                               |
                   +-----------+-----------+
                   |                       |
            OpenCV Zone Vision       Physical Event Ledger
                   |                       |
                   +-----------------------+
                               |
                     Reconciliation engine
                               |
                    SQLite + Activity Feed
                               |
                    Verified? → Mock receipt
```

## Design limitations / safety

- **Single-session demo:** No login, session tokens, shopper identity association, or payment authorization.
- **SQLite for first-run simplicity:** PostgreSQL can replace SQLite in the next phase.
- **Fixed zones only:** Each shelf zone has one SKU and one physical item initially. No detection of two identical items per zone.
- **Not production theft detection:** Computer vision is a heuristic, never proof of intent; low-confidence observations require human review.
- **No real charging:** All receipts say `SIMULATED — no money charged`.
- **Privacy:** Video frames are sent transiently to local FastAPI and are not saved. Raw recordings are not stored by the application.
- **Access:** No authentication. Run on a trusted machine/network, do not deploy publicly until protected.

## Next build stages

1. Sensor simulator with weight readings and confidence; reconcile camera + load-cell events.
2. Calibration and detection reliability improvements, verification history with event IDs and duplicate suppression.
3. Real ESP32/HX711/load cell integration.
4. Optional trained YOLO object model and multi-shopper research.
5. PostgreSQL, user/session authentication, automated integration tests.


## Phase 4: YOLO + ByteTrack (optional experiment)

The standard prototype is functional without YOLO. In the backend virtual environment:

```powershell
pip install -r requirements-ai.txt
uvicorn main:app --reload --port 8000
```

Open **Shelf operations**, start your camera, then click **Enable AI overlay**.
First inference may download `yolo11n.pt` (free; Internet required once if not cached).
Tracking requests run about every 2.8 seconds; a CPU may be slower.

`GET /api/vision/ai/status` and `POST /api/vision/ai/frame` expose diagnostics
and generic object detections and ByteTrack anonymous IDs. This is **not** SKU
recognition, pickup attribution, customer tracking or a theft alarm; object
detections intentionally do not mutate cart quantities. Existing fixed-zone
monitoring and simulated weight confirmation still govern the demo cart.

Production next steps: gather shelf SKU data, train product recognition, verify
hand-product interactions, attribute anonymous events to sessions, add real
weight telemetry, and quantify false alarms with appropriate privacy controls.

## Phase 5: Example-based product appearance verification (new)

**Goal:** distinguish the three *specific physical sample products* in fixed shelf
zones without downloading a large SKU model or training on a retail dataset.
This version uses an operator-labeled image of each sample and compares color,
coarse appearance, and packaging feature points via local OpenCV. The result is
an **advisory similarity assessment**, not a reliable SKU classifier, and does
not automatically alter the physical cart or decide payment eligibility.

**Setup (Shelf operations):**

1. Stop movement and clear the three zones. If needed, calibrate the fixed-zone
   monitor first using the existing **Capture empty** / **Capture stocked** steps.
2. Put Shampoo in A (left), Biscuits in B (middle), and Cola in C (right).
3. Keep the camera position fixed and the products fully visible and still.
4. Press **Teach Shampoo**, **Teach Biscuits**, then **Teach Cola**. Each click
   captures the relevant portion of the current webcam image and stores it as a
   local example under `backend/sku_templates/` (gitignored).
5. Click **Check product appearances** to compare the *current* camera frame to
   those references. Results are `MATCH`, `POSSIBLE_MISMATCH`, or `UNCERTAIN`.
6. For a controlled demonstration, replace the object in zone A with the actual
   Biscuits package and check again. The system *may* report a possible
   mismatch. Repeating at a different lighting/angle may instead be uncertain.
7. Re-teach after changing camera position, lighting, shelf layout or packages.

This is a separate experimental appearance check; it does NOT continuously
analyze video, distinguish customers, or make a theft determination. The existing
OpenCV zone detector still handles occupancy and pickups; the two-signal fusion
engine still manages simulated weight evidence. A `POSSIBLE_MISMATCH` is a
prompt for human review only. Similarity percentages are **not probabilities**.

**New endpoints:**

- `GET /api/vision/sku/status`: which products have learned examples.
- `POST /api/vision/sku/enroll/{product_id}`: raw JPEG camera frame; the server
  crops that product's assigned shelf zone and overwrites its local example.
- `POST /api/vision/sku/recognize`: raw JPEG frame; returns per-zone advisory
  comparisons to the three learned examples. All three must be enrolled first.

**Requirements:** Only the core OpenCV requirements are needed for Phase 5.
YOLO is optional and unrelated. Offline test commands:

```powershell
cd "$HOME\Desktop\SmartCart-AI\backend"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The saved example images may reveal package details in a small webcam crop.
Store and delete them according to your privacy needs. The prototype offers no
authentication or production-ready access control.

## Phase 6 — End-to-end demo acceptance + simulated exit billing

**New in this update:** `POST /api/exit/attempt` simulates an exit sensor trigger. It does *not* sense a real customer or charge money. The backend checks physical/digital item quantities and outstanding sensor evidence, rejects unresolved carts with HTTP 409 (audited in event feed), and returns a single mock receipt if everything agrees. Repeated simulated exit triggers return the **same receipt**. Manual simulator pickups are now blocked server-side when two-signal fusion mode is active.

The Shopper screen includes an **Exit gate simulator** panel that shows readiness and lets judges try both rejected and approved exits. `GET /api/status` includes an `exit` object (`state`, `reason`, `payment_mode`).

To run automated acceptance tests in **PowerShell**:

```powershell
cd "$HOME\Desktop\SmartCart-AI\backend"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts/run_acceptance.py
```

The runner creates `reports/phase6-acceptance.json` without writing to your shopping database. Detailed guide: [docs/PHASE6_DEMO_GUIDE.md](docs/PHASE6_DEMO_GUIDE.md). Real webcams, frontend build, physical sensors and mobile camera permission still require local testing.

## Phase 7 — reliable judge walkthrough (current)

- New 5-step demo guide in the web app; completion state is derived from actual backend event history.
- Camera health: number of processed frames, last received frame, weak calibration zones and **rejected** cart mutations. A vision transition is no longer reported as successful if the cart update was rejected.
- Tests for checkout refusal, idempotent exit, real recorded progress, synthetic camera frames, weak calibration and uncertain sensor evidence.
- **[Phase 7 step-by-step instructions](docs/PHASE7_DEMO_GUIDE.md)** and `python scripts/run_phase7_acceptance.py`.

The camera detection model, payment method and simulated-weight limitations from earlier phases still apply. Phase 7 prioritizes a demonstrable, honest prototype, not production autonomous checkout.
