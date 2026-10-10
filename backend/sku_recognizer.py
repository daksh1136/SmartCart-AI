"""Experimental example-based SKU appearance matching for a fixed 3-zone demo.

This is NOT a trained retail SKU detector. Operators enroll one example image
of each actual item in its assigned zone. Matching is advisory only and never
modifies or authorizes the cart. Persisted examples stay on the local machine.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException

SKU_ZONES = {"shampoo": "A", "biscuits": "B", "cola": "C"}


def decode_frame(frame_bytes: bytes) -> np.ndarray:
    frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or frame.shape[0] < 120 or frame.shape[1] < 240:
        raise HTTPException(422, "Expected JPEG frame at least 240x120")
    return cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)


def crop_zone(frame: np.ndarray, zone: str) -> np.ndarray:
    index = "ABC".index(zone)
    width = 640
    # The bounds deliberately match the Phase 2 occupancy detector.
    roi = frame[38:335, index * width // 3:(index + 1) * width // 3]
    # Crop central area of region: reduce unchanging shelf background.
    h, w = roi.shape[:2]
    roi = roi[int(.08 * h):int(.93 * h), int(.14 * w):int(.86 * w)]
    return cv2.resize(roi, (160, 160), interpolation=cv2.INTER_AREA)


def make_signature(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [20, 12], [0, 180, 0, 256])
    histogram = cv2.normalize(histogram, None).astype(np.float32)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # ORB descriptors help on printed packaging but may be absent on plain objects.
    orb = cv2.ORB_create(nfeatures=250, fastThreshold=8)
    _, descriptors = orb.detectAndCompute(gray, None)
    return histogram, gray, descriptors


def similarity(a: tuple, b: tuple) -> dict:
    a_hist, a_gray, a_desc = a
    b_hist, b_gray, b_desc = b
    histogram = max(0.0, min(1.0, float(cv2.compareHist(a_hist, b_hist, cv2.HISTCMP_CORREL) + 1) / 2))
    # Adjacent pixels and lighting changes: absolute normalized image comparison.
    pixel_diff = float(np.mean(cv2.absdiff(a_gray, b_gray)))
    structure = max(0.0, 1.0 - pixel_diff / 100.0)
    # Only reward feature matches if enough print features exist in both images.
    features = 0.0
    if a_desc is not None and b_desc is not None and len(a_desc) >= 8 and len(b_desc) >= 8:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        pairs = matcher.knnMatch(a_desc, b_desc, k=2)
        good = sum(1 for match in pairs if len(match) == 2 and match[0].distance < 0.7 * match[1].distance)
        features = min(1.0, good / 12.0)
    score = 0.55 * structure + 0.35 * histogram + 0.10 * features
    return {"score": round(score, 3), "structural": round(structure, 3),
            "color": round(histogram, 3), "features": round(features, 3)}


class SKURecognizer:
    """Simple example-image matching with explicit uncertainty and safe outputs."""

    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory or os.environ.get(
            "SMARTCART_SKU_DIR", str(Path(__file__).parent / "sku_templates")))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.examples: dict[str, tuple] = {}
        self.last_result: dict | None = None
        for product_id in SKU_ZONES:
            path = self.directory / f"{product_id}.png"
            img = cv2.imread(str(path)) if path.exists() else None
            if img is not None and img.shape[:2] == (160, 160):
                self.examples[product_id] = make_signature(img)

    def status(self) -> dict:
        with self.lock:
            return {
                "enrolled": list(self.examples),
                "required": list(SKU_ZONES),
                "ready": len(self.examples) == len(SKU_ZONES),
                "last_result": self.last_result,
                "mode": "reference-image-similarity",
                "note": "Experimental appearance matching only, not trained SKU recognition. No cart changes.",
            }

    def enroll(self, product_id: str, frame_bytes: bytes) -> dict:
        if product_id not in SKU_ZONES:
            raise HTTPException(404, "Unknown demo SKU")
        frame = decode_frame(frame_bytes)
        crop = crop_zone(frame, SKU_ZONES[product_id])
        with self.lock:
            path = self.directory / f"{product_id}.png"
            if not cv2.imwrite(str(path), crop):
                raise HTTPException(500, "Could not save local SKU example")
            self.examples[product_id] = make_signature(crop)
            self.last_result = None
            return self.status()

    def recognize(self, frame_bytes: bytes, occupied: dict[str, bool] | None = None) -> dict:
        frame = decode_frame(frame_bytes)
        with self.lock:
            if len(self.examples) < 3:
                raise HTTPException(409, "Teach all three product appearances before checking")
            output = []
            for product_id, zone in SKU_ZONES.items():
                if occupied is not None and not occupied.get(zone, True):
                    output.append({"zone": zone, "expected": product_id, "predicted": None,
                                   "result": "EMPTY", "confidence": None, "alternatives": []})
                    continue
                candidate = make_signature(crop_zone(frame, zone))
                options = sorted(((sku, similarity(candidate, template))
                                  for sku, template in self.examples.items()),
                                 key=lambda x: x[1]["score"], reverse=True)
                best_sku, best_stats = options[0]
                runner_score = options[1][1]["score"]
                lead = best_stats["score"] - runner_score
                # Conservative prototype thresholds: with no separation, say uncertain.
                confident = best_stats["score"] >= .73 and lead >= .045
                result = ("MATCH" if best_sku == product_id else "POSSIBLE_MISMATCH") if confident else "UNCERTAIN"
                output.append({"zone": zone, "expected": product_id,
                               "predicted": best_sku if confident else None,
                               "candidate": best_sku, "result": result,
                               "confidence": best_stats["score"], "lead": round(lead, 3),
                               "alternatives": [{"sku": sku, **stats} for sku, stats in options]})
            snapshot = {
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "zones": output,
                "note": "Experimental visual hints; no identity, charge or loss-prevention decision is inferred.",
            }
            self.last_result = snapshot
            return snapshot

    def reset_session(self):
        # Keep learned templates across sessions. Clear potentially stale current snapshot.
        with self.lock:
            self.last_result = None
