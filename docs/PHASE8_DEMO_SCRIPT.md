# SmartCart AI — 2-minute hackathon demo script

**Use the reliable simulation-first route.** Confirm both servers are running, open the Shopper screen, set browser zoom to 90–100%, and clear previous transactions by clicking **Reset demo**. Put the application in full-screen mode. Use a backup recorded screen capture if the venue network or camera is unstable.

| Time | Screen / action | Speaker notes |
| --- | --- | --- |
| 0:00–0:18 | Title / Shopper app | “In scan-and-go shopping, the phone knows what was scanned — but not necessarily what left the shelf. SmartCart AI compares those two stories before checkout.” |
| 0:18–0:35 | Shelf operations → **Pickup Shampoo** | “This controlled demo uses a simulated shelf event for reliability. Our optional webcam monitor can supply an observation after calibration.” |
| 0:35–0:53 | Shopper app → **Simulate Customer Reaching Exit** | “The physical cart contains one shampoo. The digital cart is empty. The exit request is flagged for review; no mock charge occurs.” |
| 0:53–1:15 | **Demo scan Shampoo** | “Now the phone records Shampoo. Both carts show one item, and reconciliation reports a match, ₹199.” |
| 1:15–1:34 | **Simulate Customer Reaching Exit** again | “With no mismatch or unresolved evidence, SmartCart generates one simulated receipt. Repeating exit returns that receipt instead of duplicating billing.” |
| 1:34–1:53 | Switch to architecture slide | “The same pipeline can accept fixed-zone camera events, then corroborate them with simulated shelf-weight readings. Conflicting evidence remains pending and blocks exit.” |
| 1:53–2:00 | Closing slide | “The roadmap is real sensor hardware, field accuracy tests, multi-shopper association and authorized payments. Today we are demonstrating the decision workflow end to end.” |

## Alternative: camera proof (only after local validation)

Calibrate with an empty view, stock Shampoo in A / Biscuits in B / Cola in C, remove Shampoo after the camera is stable, and point out the physical cart change **only if you observe it**. If live detection is uncertain, demonstrate the simulator and explain that the camera is a research component undergoing validation. Do **not** present a button-generated pickup as a computer-vision detection.

## Likely judge questions and precise answers

**Q: Is this a real theft detector?** No. It's discrepancy detection; an unscanned item could be a mistake or uncertain sensor data. The right action is correction or review.

**Q: Is your weight sensor real?** Not yet. The prototype uses a sensor simulator; physical load cells are on the roadmap.

**Q: Does YOLO identify all products?** No. The optional generic detection/tracking overlay doesn't drive SKU or checkout decisions. The current shelf detector uses fixed zones.

**Q: Can two shoppers use it at once?** Not safely in this version. It's one session; reliable anonymous customer-to-event association is future work.

**Q: Are you charging customers automatically?** No. The payment is a mock transaction. Real integration would require consent and secure payment handling.

**Q: How do you avoid false accusations?** We never infer intent, keep uncertain evidence separate from verified changes, and block automatic checkout pending review.

## Rehearsal checklist

- Both services respond; no browser console errors.
- One complete simulator run without resetting midway.
- Repeat exit confirms identical receipt ID.
- Backup screenshot/video saved locally (with no sensitive customer data).
- Spoken differentiation between **simulated** and **real** observations.
