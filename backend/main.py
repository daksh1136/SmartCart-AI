"""SmartCart AI hackathon MVP — single-store, single-session demonstration.

This app is NOT a production loss-prevention system or payment processor.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from yolo_assist import yolo_assist
from sku_recognizer import SKURecognizer

DB_PATH = Path(os.environ.get("SMARTCART_DB", str(Path(__file__).parent / "smartcart.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_LOCK = threading.RLock()

PRODUCT_WEIGHTS = {"shampoo": 250, "biscuits": 100, "cola": 330}  # demo reference grams

PRODUCTS = [
    ("shampoo", "Shampoo", 19900, "8901234500019", "A", "🧴"),
    ("biscuits", "Biscuits", 2000, "8901234500026", "B", "🍪"),
    ("cola", "Cola", 4000, "8901234500033", "C", "🥤"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def initialize() -> None:
    with DB_LOCK, connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, price_paise INTEGER NOT NULL,
            barcode TEXT UNIQUE NOT NULL, zone TEXT NOT NULL, emoji TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cart (
            product_id TEXT PRIMARY KEY REFERENCES products(id),
            physical_qty INTEGER NOT NULL DEFAULT 0,
            scanned_qty INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            kind TEXT NOT NULL, product_id TEXT, message TEXT NOT NULL,
            source TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS receipts (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
        );
        """)
        for product in PRODUCTS:
            db.execute("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?)", product)
            db.execute("INSERT OR IGNORE INTO cart(product_id) VALUES (?)", (product[0],))


def log(db: sqlite3.Connection, kind: str, product_id: str | None, message: str, source: str) -> None:
    db.execute("INSERT INTO events (created_at, kind, product_id, message, source) VALUES (?,?,?,?,?)",
               (now(), kind, product_id, message, source))


def ensure_not_paid(db: sqlite3.Connection) -> None:
    if db.execute("SELECT 1 FROM receipts LIMIT 1").fetchone():
        raise HTTPException(409, "Session already checked out. Start a new session to continue.")


def get_product(db: sqlite3.Connection, product_id: str | None = None, barcode: str | None = None) -> sqlite3.Row:
    if product_id is not None:
        row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    else:
        row = db.execute("SELECT * FROM products WHERE barcode = ?", (barcode,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown product or barcode")
    return row


def change_physical(product_id: str, action: str, source: str = "simulator") -> None:
    if action not in ("pickup", "return"):
        raise HTTPException(422, "action must be pickup or return")
    with DB_LOCK, connect() as db:
        ensure_not_paid(db)
        product = get_product(db, product_id=product_id)
        row = db.execute("SELECT physical_qty FROM cart WHERE product_id = ?", (product_id,)).fetchone()
        qty = row["physical_qty"] + (1 if action == "pickup" else -1)
        if qty < 0:
            raise HTTPException(409, "Cannot return an item that was not picked up")
        if qty > 99:
            raise HTTPException(409, "Demo quantity limit reached")
        db.execute("UPDATE cart SET physical_qty = ? WHERE product_id = ?", (qty, product_id))
        log(db, action.upper(), product_id, f"{product['name']} {action} detected", source)


def status() -> dict:
    with DB_LOCK, connect() as db:
        rows = db.execute("""SELECT p.*, c.physical_qty, c.scanned_qty
                             FROM products p JOIN cart c ON p.id = c.product_id
                             ORDER BY p.zone""").fetchall()
        items = []
        total = 0
        discrepancies = 0
        for row in rows:
            p, s = row["physical_qty"], row["scanned_qty"]
            if p > s:
                state = "UNSCANNED"
            elif p < s:
                state = "OVER_SCANNED"
            elif p > 0:
                state = "MATCHED"
            else:
                state = "CLEAR"
            if p != s:
                discrepancies += 1
            total += s * row["price_paise"]
            items.append({**dict(row), "status": state})
        history = [dict(r) for r in db.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT 20").fetchall()]
        receipt_row = db.execute("SELECT payload FROM receipts LIMIT 1").fetchone()
    fusion_state = fusion.summary()
    if receipt_row:
        exit_state = "COMPLETED"
        exit_reason = "Mock checkout already completed"
    elif fusion_state["blocked"]:
        exit_state = "REVIEW_REQUIRED"
        exit_reason = "Unresolved camera/weight evidence"
    elif discrepancies:
        exit_state = "REVIEW_REQUIRED"
        exit_reason = "Physical and scanned quantities do not match"
    elif not any(i["scanned_qty"] for i in items):
        exit_state = "EMPTY_CART"
        exit_reason = "Scan and verify at least one item"
    else:
        exit_state = "READY"
        exit_reason = "Cart verified; eligible for simulated exit billing"
    # The judge walkthrough reflects genuine recorded events, never auto-generated successes.
    event_types = {e["kind"] for e in history}
    demo_steps = [
        {"title": "Reset demo session", "done": True,
         "help": "Reset before the live presentation; restock camera zones first."},
        {"title": "Remove Shampoo", "done": "PICKUP" in event_types,
         "help": "Use one physical pickup or the camera + simulated weight controls."},
        {"title": "Try exit without scanning", "done": "EXIT_BLOCKED" in event_types,
         "help": "Simulate reaching exit to show the unresolved-cart warning."},
        {"title": "Scan Shampoo", "done": "SCANNED" in event_types,
         "help": "Open Shopper app and scan the matching barcode or use Demo scan."},
        {"title": "Approve mock exit", "done": "EXIT_APPROVED" in event_types,
         "help": "Try the exit again. Only a simulated receipt is issued."},
    ]
    first_pending = next((i for i, step in enumerate(demo_steps[1:], start=1) if not step["done"]), None)
    return {
        "demo": {"steps": demo_steps, "current_step": first_pending,
                 "complete": all(step["done"] for step in demo_steps),
                 "sensor_type": "SIMULATED_WEIGHT" if fusion_state["enabled"] else "CAMERA_OR_MANUAL"},
        "exit": {"state": exit_state, "reason": exit_reason,
                 "payment_mode": "SIMULATED — no money charged"},
        "products": items,
        "events": history,
        "total_paise": total,
        "discrepancy_count": discrepancies,
        "verified": discrepancies == 0 and any(i["scanned_qty"] for i in items) and not fusion_state["blocked"],
        "receipt": json.loads(receipt_row["payload"]) if receipt_row else None,
        "vision": vision.summary(),
        "fusion": fusion_state,
        "sku": sku_recognizer.status(),
    }


class ScanRequest(BaseModel):
    barcode: str


class RemoveRequest(BaseModel):
    product_id: str


class PhysicalRequest(BaseModel):
    product_id: str
    action: str


class FusionModeRequest(BaseModel):
    enabled: bool


class FusionSignalRequest(BaseModel):
    product_id: str
    action: str


class WeightRequest(BaseModel):
    product_id: str
    weight_grams: float


class Vision:
    """Fixed-zone template comparison for a stationary demo camera.

    Calibrate first with ALL zones empty, then with ONE product in EACH zone.
    A frame must resemble an empty/full reference for 4 consecutive samples
    before a physical transition is emitted. This is NOT shopper tracking.
    """
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.empty_refs: dict[str, np.ndarray] = {}
        self.full_refs: dict[str, np.ndarray] = {}
        self.observed: dict[str, str] = {z: "UNKNOWN" for z in "ABC"}
        self.stable: dict[str, str] = {z: "OCCUPIED" for z in "ABC"}
        self.candidates: dict[str, str | None] = {z: None for z in "ABC"}
        self.counts: dict[str, int] = {z: 0 for z in "ABC"}
        self.reference_separation: dict[str, float] = {}
        self.frames_processed = 0
        self.last_frame_epoch: float | None = None
        self.rejected_events: list[dict] = []

    @staticmethod
    def regions(img_bytes: bytes) -> dict[str, np.ndarray]:
        data = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(422, "Invalid image; expected JPEG frame")
        h, w = frame.shape[:2]
        if h < 120 or w < 240:
            raise HTTPException(422, "Camera frame is too small")
        frame = cv2.resize(frame, (640, 360))
        parts = {}
        for idx, zone in enumerate("ABC"):
            roi = frame[38:335, idx * 640 // 3:(idx + 1) * 640 // 3]
            gray = cv2.cvtColor(cv2.resize(roi, (64, 64)), cv2.COLOR_BGR2GRAY)
            parts[zone] = cv2.GaussianBlur(gray, (7, 7), 0)
        return parts

    @staticmethod
    def distance(left: np.ndarray, right: np.ndarray) -> float:
        return float(np.mean(cv2.absdiff(left, right)))

    def ready(self) -> bool:
        return len(self.empty_refs) == 3 and len(self.full_refs) == 3

    def calibrate(self, kind: str, img_bytes: bytes) -> dict:
        if kind not in ("empty", "full"):
            raise HTTPException(404, "Calibration should be empty or full")
        refs = self.regions(img_bytes)
        with self.lock:
            if kind == "empty":
                self.empty_refs = refs
                self.full_refs = {}  # invalidate any previous full references
            else:
                if len(self.empty_refs) != 3:
                    raise HTTPException(409, "Capture the empty shelf first")
                self.full_refs = refs
                self.stable = {z: "OCCUPIED" for z in "ABC"}
                self.candidates = {z: None for z in "ABC"}
                self.counts = {z: 0 for z in "ABC"}
            self.observed = {z: "UNKNOWN" for z in "ABC"}
            self.frames_processed = 0
            self.last_frame_epoch = None
            self.rejected_events = []
            self.reference_separation = (
                {z: round(self.distance(self.empty_refs[z], self.full_refs[z]), 1)
                 for z in "ABC"} if self.ready() else {}
            )
            return self.summary()

    def summary(self) -> dict:
        with self.lock:
            return {
                "ready": self.ready(), "has_empty": len(self.empty_refs) == 3,
                "has_full": len(self.full_refs) == 3,
                "zones": dict(self.observed),
                "separation": dict(self.reference_separation),
                "calibration_warning": [z for z, v in self.reference_separation.items() if v < 5],
                "frames_processed": self.frames_processed,
                "last_frame_at": (
                    datetime.fromtimestamp(self.last_frame_epoch, timezone.utc).isoformat(timespec="seconds")
                    if self.last_frame_epoch is not None else None
                ),
                "stream_recent": self.last_frame_epoch is not None and time.time() - self.last_frame_epoch < 8,
                "rejected_events": list(self.rejected_events[-5:]),
            }

    def process(self, img_bytes: bytes) -> dict:
        refs = self.regions(img_bytes)
        transitions: list[tuple[str, str]] = []
        with self.lock:
            self.frames_processed += 1
            self.last_frame_epoch = time.time()
            if not self.ready():
                return self.summary()
            for z in "ABC":
                d_empty = self.distance(refs[z], self.empty_refs[z])
                d_full = self.distance(refs[z], self.full_refs[z])
                separation = self.reference_separation.get(z, 0)
                # If reference images look identical, we cannot detect presence.
                if separation < 5 or abs(d_empty - d_full) < 3:
                    label = "UNKNOWN"
                else:
                    label = "EMPTY" if d_empty < d_full else "OCCUPIED"
                self.observed[z] = label
                if label == "UNKNOWN" or label == self.stable[z]:
                    self.candidates[z] = None
                    self.counts[z] = 0
                else:
                    if self.candidates[z] == label:
                        self.counts[z] += 1
                    else:
                        self.candidates[z] = label
                        self.counts[z] = 1
                    if self.counts[z] >= 4:
                        self.stable[z] = label
                        self.candidates[z] = None
                        self.counts[z] = 0
                        transitions.append((z, "pickup" if label == "EMPTY" else "return"))
        accepted = []
        rejected = []
        for zone, action in transitions:
            product = next(p for p in PRODUCTS if p[4] == zone)
            try:
                if fusion.enabled:
                    fusion.record_signal("camera", product[0], action)
                else:
                    change_physical(product[0], action, source="camera")
                accepted.append({"zone": zone, "action": action})
            except HTTPException as exc:
                # A detected image change is NOT a confirmed cart mutation.
                rejected.append({"zone": zone, "action": action, "reason": str(exc.detail)})
        with self.lock:
            if rejected:
                self.rejected_events = (self.rejected_events + rejected)[-5:]
            result = self.summary()
        result["transitions"] = accepted
        result["rejected"] = rejected
        return result

    def reset_session(self) -> None:
        # On reset, re-arm for a fully stocked shelf.
        with self.lock:
            self.stable = {z: "OCCUPIED" for z in "ABC"}
            self.candidates = {z: None for z in "ABC"}
            self.counts = {z: 0 for z in "ABC"}
            self.observed = {z: "UNKNOWN" for z in "ABC"}
            self.rejected_events = []


class FusionEngine:
    """Single-SKU shelf demo: two independent signals must agree.

    Weight readings are SIMULATED; they are not real load-cell telemetry.
    Camera events are from live zone comparison or the camera demo buttons.
    State is intentionally ephemeral, while cart and event audit use SQLite.
    """
    WINDOW_SECONDS = 120

    def __init__(self):
        self.lock = threading.RLock()
        self.enabled = False  # preserve camera-only demo mode by default
        self.next_id = 1
        self.pending: list[dict] = []
        self.weights = dict(PRODUCT_WEIGHTS)
        self.weight_states = {p: "STOCKED" for p in PRODUCT_WEIGHTS}
        self.last_stable = {p: "STOCKED" for p in PRODUCT_WEIGHTS}

    def summary(self):
        with self.lock:
            active = [
                {k: v for k, v in event.items() if k != "epoch"}
                | {"state": "REVIEW_REQUIRED" if time.time() - event["epoch"] > self.WINDOW_SECONDS else "AWAITING_PAIR"}
                for event in self.pending
            ]
            unknown_weights = [p for p, state in self.weight_states.items() if state == "UNCERTAIN"]
            return {
                "enabled": self.enabled,
                "window_seconds": self.WINDOW_SECONDS,
                "weights": dict(self.weights),
                "weight_states": dict(self.weight_states),
                "expected_weights": dict(PRODUCT_WEIGHTS),
                "pending": active,
                "pending_count": len(active),
                "uncertain_weights": unknown_weights,
                "blocked": self.enabled and (bool(active) or bool(unknown_weights)),
            }

    def set_mode(self, enabled: bool):
        with self.lock:
            if not enabled and self.pending:
                raise HTTPException(409, "Clear pending evidence before turning sensor fusion off")
            with DB_LOCK, connect() as db:
                ensure_not_paid(db)
            self.enabled = enabled
            with DB_LOCK, connect() as db:
                log(db, "FUSION_MODE", None,
                    "Two-signal sensor fusion enabled" if enabled else "Camera-only mode enabled", "system")
        return self.summary()

    def clear(self):
        with self.lock:
            with DB_LOCK, connect() as db:
                ensure_not_paid(db)
            self.pending.clear()
            # Do not misrepresent ambiguous sensor readings as healthy;
            # the operator must provide a fresh stable weight reading.
            with DB_LOCK, connect() as db:
                log(db, "EVIDENCE_CLEARED", None, "Operator cleared unmatched fusion evidence; uncertain weights still require review", "operator")
        return self.summary()

    def reset(self):
        with self.lock:
            self.enabled = False
            self.pending.clear()
            self.weights = dict(PRODUCT_WEIGHTS)
            self.weight_states = {p: "STOCKED" for p in PRODUCT_WEIGHTS}
            self.last_stable = {p: "STOCKED" for p in PRODUCT_WEIGHTS}
            self.next_id = 1

    def record_signal(self, source: str, product_id: str, action: str):
        if source not in ("camera", "weight") or action not in ("pickup", "return"):
            raise HTTPException(422, "Expected camera/weight and pickup/return")
        if product_id not in PRODUCT_WEIGHTS:
            raise HTTPException(404, "Unknown demo product")
        with self.lock:
            if not self.enabled:
                raise HTTPException(409, "Enable sensor fusion first")
            with DB_LOCK, connect() as db:
                ensure_not_paid(db)
            current_time = time.time()
            # Ignore rapid duplicate observations from the same source.
            duplicate = next((e for e in self.pending if e["source"] == source
                              and e["product_id"] == product_id and e["action"] == action
                              and current_time - e["epoch"] < self.WINDOW_SECONDS), None)
            if duplicate:
                return {"result": "duplicate_ignored", "fusion": self.summary()}
            pair = next((e for e in self.pending if e["source"] != source
                         and e["product_id"] == product_id and e["action"] == action
                         and current_time - e["epoch"] <= self.WINDOW_SECONDS), None)
            if pair:
                # Only remove evidence after the authoritative physical-cart mutation succeeds.
                change_physical(product_id, action, source="sensor_fusion")
                self.pending.remove(pair)
                with DB_LOCK, connect() as db:
                    log(db, "FUSION_CONFIRMED", product_id,
                        f"Camera and weight agree on {action} for {product_id}", "sensor_fusion")
                return {"result": "confirmed", "fusion": self.summary()}
            event = {
                "id": self.next_id, "product_id": product_id,
                "source": source, "action": action, "created_at": now(), "epoch": current_time,
            }
            self.next_id += 1
            self.pending.append(event)
            with DB_LOCK, connect() as db:
                log(db, "FUSION_PENDING", product_id,
                    f"{source.title()} detected {action} for {product_id}; awaiting second signal", source)
            return {"result": "pending", "fusion": self.summary()}

    def record_weight(self, product_id: str, grams: float):
        if product_id not in PRODUCT_WEIGHTS:
            raise HTTPException(404, "Unknown demo product")
        expected = PRODUCT_WEIGHTS[product_id]
        if not 0 <= grams <= expected * 1.5:
            raise HTTPException(422, f"Demo weight must be between 0 and {expected * 1.5:g} grams")
        with self.lock:
            if not self.enabled:
                raise HTTPException(409, "Enable sensor fusion first")
            with DB_LOCK, connect() as db:
                ensure_not_paid(db)
            prior = self.last_stable[product_id]
            current = ("STOCKED" if grams >= expected * .75 else
                       "EMPTY" if grams <= expected * .25 else "UNCERTAIN")
            self.weights[product_id] = round(grams, 1)
            self.weight_states[product_id] = current
            if current == "UNCERTAIN":
                with DB_LOCK, connect() as db:
                    log(db, "WEIGHT_UNCERTAIN", product_id,
                        f"Ambiguous weight ({grams:g}g) for {product_id}; needs review", "weight")
                return {"result": "uncertain", "fusion": self.summary()}
            if current == prior:
                return {"result": "stable", "fusion": self.summary()}
            result = self.record_signal("weight", product_id, "pickup" if current == "EMPTY" else "return")
            self.last_stable[product_id] = current
            return result


vision = Vision()
fusion = FusionEngine()
sku_recognizer = SKURecognizer()
initialize()
app = FastAPI(title="SmartCart AI Demo API", version="0.1.0")
allowed_origins = os.environ.get(
    "SMARTCART_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "single-session-demo"}


@app.get("/api/status")
def current_status():
    return status()


@app.post("/api/scan")
def scan(payload: ScanRequest):
    with DB_LOCK, connect() as db:
        ensure_not_paid(db)
        p = get_product(db, barcode=payload.barcode.strip())
        row = db.execute("SELECT scanned_qty FROM cart WHERE product_id = ?", (p["id"],)).fetchone()
        if row["scanned_qty"] >= 99:
            raise HTTPException(409, "Demo quantity limit reached")
        db.execute("UPDATE cart SET scanned_qty = scanned_qty + 1 WHERE product_id = ?", (p["id"],))
        log(db, "SCANNED", p["id"], f"{p['name']} scanned on phone", "mobile")
    return status()


@app.post("/api/unscan")
def unscan(payload: RemoveRequest):
    with DB_LOCK, connect() as db:
        ensure_not_paid(db)
        p = get_product(db, product_id=payload.product_id)
        qty = db.execute("SELECT scanned_qty FROM cart WHERE product_id = ?", (p["id"],)).fetchone()[0]
        if qty <= 0:
            raise HTTPException(409, "Nothing to remove from digital cart")
        db.execute("UPDATE cart SET scanned_qty = scanned_qty - 1 WHERE product_id = ?", (p["id"],))
        log(db, "UNSCANNED", p["id"], f"One {p['name']} removed from digital cart", "mobile")
    return status()


@app.post("/api/simulate")
def simulate(payload: PhysicalRequest):
    # Enforce the same boundary server-side as the disabled frontend buttons:
    # manual events must not bypass camera+weight verification in fusion mode.
    with fusion.lock:
        if fusion.enabled:
            raise HTTPException(409, "Manual pickup simulation is disabled in two-signal mode")
        change_physical(payload.product_id, payload.action)
    return status()


@app.post("/api/reset")
def reset():
    with DB_LOCK, connect() as db:
        db.execute("UPDATE cart SET physical_qty = 0, scanned_qty = 0")
        db.execute("DELETE FROM events")
        db.execute("DELETE FROM receipts")
        log(db, "RESET", None, "New demo shopping session started", "system")
    vision.reset_session()
    fusion.reset()
    sku_recognizer.reset_session()
    return status()


def create_demo_receipt(*, exit_attempt: bool = False) -> dict:
    """Generate a fake receipt only after final cart reconciliation.

    Exit attempts are intentionally idempotent: a second exit signal returns
    the previous mock receipt, never creates another transaction.
    """
    if fusion.summary()["blocked"]:
        message = "Resolve or clear outstanding sensor evidence before checkout"
        if exit_attempt:
            with DB_LOCK, connect() as db:
                log(db, "EXIT_BLOCKED", None, message, "exit_simulator")
        raise HTTPException(409, message)
    with DB_LOCK, connect() as db:
        existing = db.execute("SELECT payload FROM receipts LIMIT 1").fetchone()
        if existing:
            if exit_attempt:
                return json.loads(existing["payload"])
            raise HTTPException(409, "Session already checked out. Start a new session to continue.")
        cart = db.execute("""SELECT p.id, p.name, p.price_paise, c.physical_qty, c.scanned_qty
                            FROM products p JOIN cart c ON p.id = c.product_id""").fetchall()
        mismatches = [r["name"] for r in cart if r["physical_qty"] != r["scanned_qty"]]
        if mismatches:
            message = "Resolve discrepancies before checkout: " + ", ".join(mismatches)
            if exit_attempt:
                log(db, "EXIT_BLOCKED", None, message, "exit_simulator")
                db.commit()  # rejection must remain visible in event feed
            raise HTTPException(409, message)
        lines = [dict(r) for r in cart if r["scanned_qty"] > 0]
        if not lines:
            message = "Cannot checkout an empty cart"
            if exit_attempt:
                log(db, "EXIT_BLOCKED", None, message, "exit_simulator")
                db.commit()  # rejection must remain visible in event feed
            raise HTTPException(409, message)
        receipt = {
            "id": "DEMO-" + uuid.uuid4().hex[:8].upper(),
            "created_at": now(),
            "items": lines,
            "total_paise": sum(r["price_paise"] * r["scanned_qty"] for r in lines),
            "payment": "SIMULATED — no money charged",
            "checkout_source": "exit_simulator" if exit_attempt else "manual_demo",
        }
        db.execute("INSERT INTO receipts VALUES (?,?,?)",
                   (receipt["id"], receipt["created_at"], json.dumps(receipt)))
        log(db, "EXIT_APPROVED" if exit_attempt else "CHECKOUT", None,
            f"Simulated checkout {receipt['id']} complete", "exit_simulator" if exit_attempt else "system")
        return receipt


@app.post("/api/checkout")
def checkout():
    return create_demo_receipt()


@app.post("/api/exit/attempt")
def simulate_exit():
    """Mock exit sensor trigger; no real proximity detector or payment gateway."""
    return create_demo_receipt(exit_attempt=True)


async def image_body(request: Request) -> bytes:
    data = await request.body()
    if not data or len(data) > 2_000_000:
        raise HTTPException(413, "JPEG frame must be between 1B and 2MB")
    return data


@app.post("/api/vision/calibrate/{kind}")
async def calibrate(kind: str, request: Request):
    return vision.calibrate(kind, await image_body(request))


@app.post("/api/vision/frame")
async def frame(request: Request):
    return vision.process(await image_body(request))


@app.get("/api/vision/ai/status")
def ai_status():
    return yolo_assist.status()


@app.post("/api/vision/ai/frame")
async def ai_frame(request: Request):
    # AI output is experimental and never changes the cart.
    data = await image_body(request)
    return await run_in_threadpool(yolo_assist.analyze, data)


@app.get("/api/vision/sku/status")
def sku_status():
    return sku_recognizer.status()


@app.post("/api/vision/sku/enroll/{product_id}")
async def sku_enroll(product_id: str, request: Request):
    # Enrollment must be a deliberate operator action. Never auto-train on shoppers.
    return await run_in_threadpool(sku_recognizer.enroll, product_id, await image_body(request))


@app.post("/api/vision/sku/recognize")
async def sku_recognize(request: Request):
    frame_bytes = await image_body(request)
    # Appearance is deliberately independent of occupancy calibration;
    # only the fixed-zone engine is responsible for pickup/return events.
    return await run_in_threadpool(sku_recognizer.recognize, frame_bytes)


@app.post("/api/fusion/mode")
def fusion_mode(payload: FusionModeRequest):
    fusion.set_mode(payload.enabled)
    return status()


@app.post("/api/fusion/clear")
def fusion_clear():
    fusion.clear()
    return status()


@app.post("/api/fusion/camera")
def fusion_camera(payload: FusionSignalRequest):
    fusion.record_signal("camera", payload.product_id, payload.action)
    return status()


@app.post("/api/fusion/weight")
def fusion_weight(payload: WeightRequest):
    fusion.record_weight(payload.product_id, payload.weight_grams)
    return status()


# A single Render web service can serve the built React app and its same-origin API.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
