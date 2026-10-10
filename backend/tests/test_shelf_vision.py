import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app, on_shelf_event

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_demo():
    assert client.post("/api/reset").status_code == 200


def test_demo_metadata_and_model_inference():
    info = client.get("/vision/demo/info")
    assert info.status_code == 200
    assert info.json() == {"frames": 362, "fps": 8}

    frame = client.get("/vision/demo/step?i=0&session_id=demo")
    assert frame.status_code == 200
    body = frame.json()
    assert body["i"] == 0 and body["done"] is False
    assert body["image"].startswith("data:image/jpeg;base64,")
    assert {zone["label"] for zone in body["zones"]}


def test_model_events_map_to_existing_catalog_and_fusion_guards():
    on_shelf_event("demo", {"product": "cocacola", "event_type": "pickup"})
    cola = next(p for p in client.get("/api/status").json()["products"] if p["id"] == "cola")
    assert cola["physical_qty"] == 1

    client.post("/api/fusion/mode", json={"enabled": True})
    with pytest.raises(HTTPException, match="weight fusion"):
        on_shelf_event("demo", {"product": "monster", "event_type": "pickup"})
    monster = next(p for p in client.get("/api/status").json()["products"] if p["id"] == "monster")
    assert monster["physical_qty"] == 0


def test_demo_step_is_operator_protected(monkeypatch):
    monkeypatch.setenv("SMARTCART_OPERATOR_KEY", "shelf-test-key")
    assert client.get("/vision/demo/step?i=0").status_code == 401
    assert client.get("/vision/demo/step?i=0", headers={
        "X-SmartCart-Operator-Key": "shelf-test-key",
    }).status_code == 200
