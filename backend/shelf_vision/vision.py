"""
SmartCart shelf vision - runs the trained shelf model inside the web backend.

Needs only:  onnxruntime, numpy, pillow   (no PyTorch, small enough for Render)

Files used (all in this folder):
    shelf_cls.onnx      the trained model
    shelf_labels.json   class names in model order
    shelf_setup.json    camera size + the shelf zones and which product sits in each

Usage:
    from shelf_vision.vision import ShelfVision
    vision = ShelfVision()                      # load once at startup
    result = vision.process(session_id, image)  # image = PIL image or JPEG bytes
    result["events"]  -> [{"zone": "B", "product": "cocacola", "event_type": "pickup", ...}]
    result["zones"]   -> what the camera currently sees in every zone (for drawing boxes)
"""
from __future__ import annotations

import io
import json
import threading
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

HERE = Path(__file__).resolve().parent
IMG_SIZE = 224
WINDOW = 6          # frames used to decide a stable state
AGREE = 0.75        # fraction of those frames that must agree
CONF_MIN = 0.60     # below this a prediction counts as "uncertain"
IGNORE = {"hand", "uncertain"}


# ----------------------------------------------------------------------------- tracking
class ZoneTracker:
    """Turns a noisy stream of per-frame predictions into clean pickup/return events."""

    def __init__(self, name: str, products: set[str]):
        self.name = name
        self.products = products
        self.history: deque = deque(maxlen=WINDOW)
        self.confs: deque = deque(maxlen=WINDOW)
        self.state: str | None = None   # last stable label: a product or "empty"

    def update(self, label: str, conf: float) -> list[dict]:
        if conf < CONF_MIN:
            label = "uncertain"
        self.history.append(label)
        self.confs.append(conf)
        if len(self.history) < self.history.maxlen:
            return []
        top, n = Counter(self.history).most_common(1)[0]
        if n < AGREE * len(self.history) or top in IGNORE or top == self.state:
            return []
        avg = sum(c for l, c in zip(self.history, self.confs) if l == top) / n
        old, self.state = self.state, top
        if old is None:                       # first stable reading = starting stock
            return []
        events = []
        if old in self.products:
            events.append(self._event(old, "pickup", avg))
        if top in self.products:
            events.append(self._event(top, "return", avg))
        return events

    def _event(self, product: str, kind: str, conf: float) -> dict:
        return {
            "zone": self.name,
            "product": product,
            "event_type": kind,
            "confidence": round(float(conf), 3),
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "source": "shelf_camera",
        }


# ----------------------------------------------------------------------------- model
def _preprocess(img: Image.Image) -> np.ndarray:
    """Same steps as Ultralytics: shortest side -> 224, centre crop 224, RGB, 0..1, CHW."""
    w, h = img.size
    if w <= h:
        nw, nh = IMG_SIZE, int(IMG_SIZE * h / w)
    else:
        nw, nh = int(IMG_SIZE * w / h), IMG_SIZE
    img = img.resize((nw, nh), Image.BILINEAR)
    left = int(round((nw - IMG_SIZE) / 2.0))
    top = int(round((nh - IMG_SIZE) / 2.0))
    img = img.crop((left, top, left + IMG_SIZE, top + IMG_SIZE))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr.transpose(2, 0, 1)


class ShelfVision:
    def __init__(self, folder: str | Path = HERE):
        folder = Path(folder)
        self.labels: list[str] = json.loads((folder / "shelf_labels.json").read_text())
        self.setup: dict = json.loads((folder / "shelf_setup.json").read_text())
        self.zones: list[dict] = self.setup["zones"]
        self.ref_w: int = self.setup["width"]
        self.ref_h: int = self.setup["height"]

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(folder / "shelf_cls.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        batch_dim = self.session.get_inputs()[0].shape[0]
        self.fixed_batch = batch_dim if isinstance(batch_dim, int) else None

        self.products = {z["product"] for z in self.zones if z.get("product")}
        self._trackers: dict[str, dict[str, ZoneTracker]] = {}
        self._lock = threading.Lock()

    # -- helpers
    def config(self) -> dict:
        """Zones + products, for the frontend to draw boxes."""
        return {"width": self.ref_w, "height": self.ref_h, "zones": self.zones,
                "labels": self.labels}

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._trackers.pop(session_id, None)

    def _trackers_for(self, session_id: str) -> dict[str, ZoneTracker]:
        if session_id not in self._trackers:
            self._trackers[session_id] = {z["name"]: ZoneTracker(z["name"], self.products)
                                          for z in self.zones}
        return self._trackers[session_id]

    def _run(self, batch: np.ndarray) -> np.ndarray:
        if self.fixed_batch:   # model exported with a fixed batch size: run one at a time
            outs = [self.session.run(None, {self.input_name: batch[i:i + 1]})[0] for i in range(len(batch))]
            out = np.concatenate(outs, 0)
        else:
            out = self.session.run(None, {self.input_name: batch})[0]
        out = out.astype(np.float32)
        if not np.allclose(out.sum(1), 1.0, atol=1e-3):      # logits -> probabilities
            e = np.exp(out - out.max(1, keepdims=True))
            out = e / e.sum(1, keepdims=True)
        return out

    def classify_zones(self, img: Image.Image) -> list[dict]:
        """Classify every zone of one frame. Each zone only chooses between its own
        product, empty and hand (the shelf 'planogram')."""
        img = img.convert("RGB")
        sx, sy = img.width / self.ref_w, img.height / self.ref_h
        crops = []
        for z in self.zones:
            box = (int(z["x"] * sx), int(z["y"] * sy),
                   int((z["x"] + z["w"]) * sx), int((z["y"] + z["h"]) * sy))
            crops.append(_preprocess(img.crop(box)))
        probs = self._run(np.stack(crops))

        results = []
        for z, p in zip(self.zones, probs):
            product = z.get("product")
            allowed = {product, "empty", "hand"} if product else set(self.labels)
            idx = [i for i, n in enumerate(self.labels) if n in allowed]
            total = float(p[idx].sum()) or 1e-9
            best = max(idx, key=lambda i: p[i])
            results.append({"zone": z["name"], "label": self.labels[best],
                            "confidence": round(float(p[best]) / total, 3)})
        return results

    def process(self, session_id: str, image) -> dict:
        """Run one frame for a shopping session. Returns current zone states and any
        new pickup/return events."""
        if isinstance(image, (bytes, bytearray)):
            image = Image.open(io.BytesIO(image))
        preds = self.classify_zones(image)
        events = []
        with self._lock:
            trackers = self._trackers_for(session_id)
            for pred in preds:
                t = trackers[pred["zone"]]
                events += t.update(pred["label"], pred["confidence"])
                pred["state"] = t.state
        return {"zones": preds, "events": events}
