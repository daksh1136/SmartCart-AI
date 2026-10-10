# Recorded shelf vision demo

The shelf vision model is integrated with SmartCart AI's FastAPI backend and Shelf Operations page.

- The ONNX model, labels, setup, and 362 JPEG frames live in this package.
- `DemoShelf.jsx` plays the recorded frames through the model at the configured 8 FPS.
- Detected events update the shared cart's physical quantity through the existing pickup/return checks.
- Camera IDs map to this catalog: `monster` → `monster`, `cocacola` → `cola`, and `lays` → `lays`.
- The single-cart demo only accepts `session_id=demo`. Recorded playback is disabled while simulated weight fusion is enabled because these products have no calibrated weight profiles.
- If `SMARTCART_OPERATOR_KEY` is set, playback and every shelf event write require that key; the frontend prompts for it on first playback.

## Verify

From the project root, run the backend tests and frontend build. The model metadata endpoint is `GET /vision/demo/info` and should return:

```json
{"frames": 362, "fps": 8}
```

Then open **Shelf operations**, press **Play** in the recorded shelf panel, and watch the activity feed and cart quantities update. Pressing **Reset session** also resets the model's zone tracking.

The ZIP does not include `shelf_monitor.py`; live USB-camera event streaming is not part of this integration. The package provides a recorded-frame demo and the existing SmartCart fixed-zone webcam flow remains available separately.
