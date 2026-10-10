# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Shoppers using a scan-and-go demonstration to add products, reconcile their carts, and complete a simulated checkout.
- Supermarket operators evaluating shelf monitoring, event review, and checkout verification.
- Hackathon judges and investors evaluating the prototype and its longer-term opportunity.

## Product Purpose

SmartCart AI demonstrates a friction-reduced supermarket shopping journey with loss-prevention checks: a shopper picks and scans products, the system compares the scanned cart with shelf-observed physical events, and a matching cart can complete a simulated checkout. Success means clearly demonstrating that end-to-end flow and surfacing discrepancies for review.

## Positioning

SmartCart AI combines barcode scans with shelf pickup and return observations, then reconciles the digital and physical carts before allowing a mock checkout. This prototype's two-signal mode can require a camera observation and a simulated weight change to agree before recording a shelf event.

## Operating Context

SmartCart AI is a Phase 7 hackathon prototype presented to investors, supermarket operators, and hackathon judges. The web application has a Shopper experience and a Shelf Operations experience. The most reliable demonstration uses manual shelf-event simulation and demo barcode scans; optional demonstrations use a laptop webcam and simulated shelf-weight events. The current demo supports one active session, three fixed product zones, and three demonstration products.

## Capabilities and Constraints

- React and Vite frontend; FastAPI backend; SQLite prototype state.
- Barcode scanning through a device camera where browser permissions and a secure context allow it, with manual/demo scan alternatives.
- Fixed-zone OpenCV image comparison can suggest pickup or return events after calibration. It is a heuristic and does not identify or associate shoppers.
- Two-signal fusion pairs camera events with simulated shelf-weight changes. No physical weight hardware is implemented.
- Cart reconciliation compares scanned and physical quantities per product. Unmatched or unresolved evidence blocks simulated checkout and requests review.
- Exit verification can reject a mismatched cart and issue a duplicate-safe mock receipt for a verified cart. No payment is charged and no physical gate is controlled.
- Optional YOLO/ByteTrack overlay and experimental reference-image SKU comparison are advisory; they do not update the authoritative cart.
- The project is a single-session demonstration, not a production loss-prevention or payment system. Authentication, multi-shopper identity association, inventory integrations, production infrastructure, and validated real-world sensor/camera performance are not established.
- Long-term vision: intelligent, frictionless supermarket shopping using computer vision, sensor fusion, and automated checkout. This is a direction, not a capability claim about the current prototype.

## Brand Commitments

- Product name: SmartCart AI.
- Tagline: “Pick. Scan. Go. Securely.”
- Current stage: Hackathon Prototype — Phase 7.
- The experience should prioritize the customer shopping journey, live camera monitoring, real-time cart reconciliation, and the automated checkout demonstration.

## Evidence on Hand

- Working project source is represented by `backend/`, `frontend/`, and `docs/` in this project.
- `README.md` documents the prototype workflows, setup, limitations, and test claims.
- `reports/phase7-acceptance.json` records the project's Phase 7 backend acceptance results. Those results cover automated backend scenarios, not real hardware, real-world camera accuracy, frontend build verification, or payment processing.
- `docs/PHASE8_ARCHITECTURE.md` and `docs/SmartCart-Architecture.png` document the prototype architecture. Phase 8 package materials are documentation/submission artifacts; the validation report says application code remains at Phase 7.
- The project includes a pitch deck and abstract under `submission/`. Do not invent customers, deployments, performance benchmarks, or production validation.

## Product Principles

- Keep the shopper's pick, scan, verify, and checkout journey easy to demonstrate.
- Make physical-versus-scanned quantity discrepancies visible and route uncertain evidence to review.
- Clearly distinguish camera observations, operator simulations, and simulated sensor evidence.
- Treat vision and appearance recognition as advisory evidence, never proof of identity, intent, or theft.
- Describe future capabilities as a vision; represent current prototype behavior accurately.
