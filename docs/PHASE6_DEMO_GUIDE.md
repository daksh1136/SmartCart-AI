# SmartCart AI — Phase 6 Acceptance and Live Demo

## What we can and cannot claim

- **Automated tests:** Backend APIs, OpenCV on synthetic JPEGs, two-signal matching, exit validation and *mock* receipt generation.
- **Needs testing on your laptop:** React/Vite build, actual webcam, appearance recognition under real lighting, barcode camera, demo performance.
- **Not implemented:** A physical exit sensor, load cell, identity attribution, real payment processing, multi-customer tracking, production theft detection.
- **Important:** A simulated exit button is not automatic physical exit detection. YOLO tracking and experimental SKU appearance matching **do not** authorize billing.

## Step A — Update the project (PowerShell)

First back up your existing project, then extract the Phase 6 patch directly into its root, replacing the matching code files. Do not copy the patch *directory* as an extra nested folder.

```powershell
Copy-Item "$HOME\Desktop\SmartCart-AI" "$HOME\Desktop\SmartCart-AI-before-phase6" -Recurse
Expand-Archive -Path "$HOME\Downloads\SmartCart-AI-phase6-patch.zip" -DestinationPath "$HOME\Desktop\SmartCart-AI" -Force
```

The update doesn't intentionally delete your SQLite database. Testing uses its **own temporary test database**.

## Step B — Backend and tests (PowerShell)

```powershell
cd "$HOME\Desktop\SmartCart-AI\backend"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python scripts/run_acceptance.py
python -m uvicorn main:app --reload --port 8000
```

Check `http://localhost:8000/api/health` in your browser and open API documentation at `/docs`.

Tests generate `reports/phase6-acceptance.json`, which you can attach to your submission as engineering evidence. **Passing synthetic-image tests does not prove webcam reliability.**

## Step C — Frontend (new PowerShell window)

```powershell
cd "$HOME\Desktop\SmartCart-AI\frontend"
npm install
npm run build
npm run dev
```

Open `http://localhost:5173`. Camera permissions require `localhost` or HTTPS, especially on mobile.

## Four-minute judges' demo — simulator first

1. **Reset session** from the event feed. Operations → **Enable 2-signal mode**.
2. In Operations for Shampoo: **Camera pickup**. Show that *physical qty remains 0* while camera evidence is pending. (This camera button is a **simulation**, not webcam inference.)
3. Click **Remove weight** (simulated 250g→0g). Physical qty becomes 1. Show pending evidence is cleared.
4. In Shopper, press **Simulate customer reaching exit** *without scanning*. The exit should **block** with an item-mismatch reason. The event feed records the rejection.
5. In Shopper, press **Demo scan** on Shampoo. Status becomes **READY** and amount ₹199.
6. Press **Simulate customer reaching exit** again. One mock receipt is issued. Press it a second time: the **same receipt ID** is returned (no duplicate mock payment).
7. Reset and optionally demonstrate *wrong item scan* (Shampoo physically removed, Biscuits scanned), then fix it by unscanning Biscuits and scanning Shampoo.

## Webcam upgrade (optional live proof)

For a **real camera event**, mount your laptop camera rigidly; Operations → Start Camera → Capture empty scene → place one item in each of left/center/right thirds → Capture stocked. If two-signal mode is enabled, remove Shampoo physically from zone A and then press *Remove weight*. The webcam action (not the simulated Camera pickup button) should become the camera-side event. Tests use synthetic images, so verify this in person before demonstrating it.

If anything is misdetected, stop the camera, reset (with zones restocked) and recalibrate. Avoid mixing the simulated camera pickup button with a real webcam event for the same item.

## Acceptance checklist

| Requirement | How to confirm | Automated? |
|---|---|---|
| Pickup causes physical/cart mismatch | Operations Pickup / synthetic OpenCV event | Yes |
| Wrong barcode creates two quantity discrepancies | Shampoo pickup + scan Biscuits | Yes |
| Fusion holds until camera + weight agree | Two-signal mode | Yes |
| Manual pickup cannot bypass fusion | Call `/api/simulate` while fusion enabled → 409 | Yes |
| Item return updates physical cart | Return + unscan | Yes |
| Exit blocked on mismatch / pending evidence | POST `/api/exit/attempt` → 409 | Yes |
| Checkout generates one simulated receipt | Repeat exit attempt → same receipt | Yes |
| Parallel exit triggers are idempotent | Concurrent test | Yes |
| React production build | `npm run build` | Local manual test |
| Actual webcam removal/return | Calibrated webcam, physical objects | Local manual test |
| Phone barcode scanner | Smartphone with HTTPS or desktop localhost | Local manual test |

### Risks and limitations

One shopper and three shelf zones only. Fusion state lives in server memory (not persistent across backend restarts), whereas cart/receipts live in SQLite. The camera alone has no way to associate a product removal with a specific customer. Before a real store pilot you need session association, validated sensor telemetry, false-positive evaluation, tamper resistance, privacy safeguards and an authorized payment flow.
