"""
FastAPI routes for the shelf camera. Add to the existing backend with two lines:

    from shelf_vision.api import router as shelf_router, set_event_handler
    app.include_router(shelf_router)

Then connect the events to the cart (same logic as a manual pickup/return):

    def on_shelf_event(session_id: str, event: dict):
        # event = {"zone": "B", "product": "cocacola", "event_type": "pickup"|"return", ...}
        # pickup -> physical qty + 1 ; return -> physical qty - 1 ; then re-check the cart
        ...
    set_event_handler(on_shelf_event)

Routes
------
GET  /vision/config                       zones, products, frame size (for drawing boxes)
POST /vision/frame?session_id=...         body: a JPEG image (raw bytes or multipart "file")
                                          -> {"zones": [...], "events": [...]}
GET  /vision/demo/info                    number of frames + fps of the recorded demo shelf video
GET  /vision/demo/step?session_id=..&i=.. runs the model on demo frame i
                                          -> {"i", "image" (data URL), "zones", "events", "done"}
POST /vision/reset?session_id=...         clears the zone memory for a session
POST /shelf-events?session_id=...         events sent by the live laptop camera (shelf_monitor.py)
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .vision import HERE, ShelfVision

router = APIRouter()
vision = ShelfVision()
DEMO_DIR = HERE / "demo_frames"
DEMO_FRAMES = sorted(DEMO_DIR.glob("*.jpg")) if DEMO_DIR.exists() else []
DEMO_FPS = json.loads((HERE / "shelf_setup.json").read_text()).get("fps", 8)

_handler: Callable[[str, dict], None] | None = None
_log: list[dict] = []          # recent events, handy for a dashboard


def _require_operator(x_smartcart_operator_key: str | None = Header(default=None)) -> None:
    operator_key = os.environ.get("SMARTCART_OPERATOR_KEY", "")
    if operator_key and x_smartcart_operator_key != operator_key:
        raise HTTPException(401, "Operator key required to change the shared demo")


def _check_session(session_id: str) -> None:
    # This app currently has one shared cart, so vision state must use its demo session.
    if session_id != "demo":
        raise HTTPException(409, "Shelf vision is connected to the single shared demo session")


def set_event_handler(fn: Callable[[str, dict], None]) -> None:
    """Register the function that applies a shelf event to the shopper's cart."""
    global _handler
    _handler = fn


def _dispatch(session_id: str, events: list[dict]) -> None:
    for ev in events:
        ev["session_id"] = session_id
        if _handler:
            _handler(session_id, ev)
        _log.append(ev)
        del _log[:-200]


@router.get("/vision/config")
def get_config():
    return vision.config()


@router.post("/vision/frame", dependencies=[Depends(_require_operator)])
async def post_frame(request: Request, session_id: str = "demo"):
    _check_session(session_id)
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            raise HTTPException(400, "send the image in a form field called 'file'")
        data = await upload.read()
    else:
        data = await request.body()
    if not data:
        raise HTTPException(400, "empty image")
    result = await run_in_threadpool(vision.process, session_id, data)
    _dispatch(session_id, result["events"])
    return result


@router.get("/vision/demo/info")
def demo_info():
    return {"frames": len(DEMO_FRAMES), "fps": DEMO_FPS}


@router.get("/vision/demo/step", dependencies=[Depends(_require_operator)])
def demo_step(i: int, session_id: str = "demo"):
    _check_session(session_id)
    if not DEMO_FRAMES:
        raise HTTPException(404, "no demo frames uploaded")
    if i <= 0:
        vision.reset(session_id)
    i = max(0, min(i, len(DEMO_FRAMES) - 1))
    data = DEMO_FRAMES[i].read_bytes()
    result = vision.process(session_id, data)
    _dispatch(session_id, result["events"])
    result.update({
        "i": i,
        "done": i >= len(DEMO_FRAMES) - 1,
        "image": "data:image/jpeg;base64," + base64.b64encode(data).decode(),
    })
    return result


@router.post("/vision/reset", dependencies=[Depends(_require_operator)])
def reset(session_id: str = "demo"):
    _check_session(session_id)
    vision.reset(session_id)
    return {"ok": True}


@router.post("/shelf-events", dependencies=[Depends(_require_operator)])
async def shelf_events(request: Request, session_id: str = "demo"):
    _check_session(session_id)
    ev = await request.json()
    if ev.get("event_type") not in ("pickup", "return") or not ev.get("product"):
        raise HTTPException(400, "need product and event_type pickup/return")
    _dispatch(session_id, [ev])
    return {"ok": True}


@router.get("/vision/events")
def recent_events(session_id: str | None = None):
    return [e for e in _log if session_id is None or e.get("session_id") == session_id]
