"""Phase 6 end-to-end acceptance tests: API + OpenCV + mocked exit billing.

All camera images below are synthetic; tests do not validate a real webcam.
"""
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def new_session():
    assert client.post("/api/reset").status_code == 200


def post(endpoint, payload=None):
    return client.post(endpoint, json=payload) if payload is not None else client.post(endpoint)


def get_product(product_id):
    return next(p for p in client.get("/api/status").json()["products"] if p["id"] == product_id)


def snap(stocked):
    """Generate an actual JPEG with distinct product-zone occupancy."""
    image = np.full((360, 640, 3), 215, dtype=np.uint8)
    for i, z in enumerate('ABC'):
        if z in stocked:
            x = i * 640 // 3
            cv2.rectangle(image, (x + 45, 110), (x + 165, 290), (30, 75, 160), -1)
    ok, encoded = cv2.imencode('.jpg', image)
    assert ok
    return encoded.tobytes()


def test_exit_rejects_empty_session_and_audits_decision():
    before = client.get('/api/status').json()
    assert before['exit']['state'] == 'EMPTY_CART'
    response = post('/api/exit/attempt')
    assert response.status_code == 409
    assert 'empty' in response.json()['detail'].lower()
    after = client.get('/api/status').json()
    assert after['receipt'] is None
    assert any(e['kind'] == 'EXIT_BLOCKED' for e in after['events'])


def test_wrong_product_unscanned_and_exit_idempotency():
    assert post('/api/simulate', {'product_id':'shampoo','action':'pickup'}).status_code == 200
    assert client.get('/api/status').json()['exit']['state'] == 'REVIEW_REQUIRED'
    assert post('/api/exit/attempt').status_code == 409
    assert post('/api/scan', {'barcode':'8901234500026'}).status_code == 200
    assert client.get('/api/status').json()['discrepancy_count'] == 2
    assert post('/api/exit/attempt').status_code == 409
    assert post('/api/unscan', {'product_id':'biscuits'}).status_code == 200
    assert post('/api/scan', {'barcode':'8901234500019'}).status_code == 200
    state = client.get('/api/status').json()
    assert state['exit']['state'] == 'READY' and state['total_paise'] == 19900
    first = post('/api/exit/attempt')
    assert first.status_code == 200
    assert first.json()['checkout_source'] == 'exit_simulator'
    assert first.json()['payment'].startswith('SIMULATED')
    second = post('/api/exit/attempt')
    assert second.status_code == 200 and second.json() == first.json()
    state = client.get('/api/status').json()
    assert state['exit']['state'] == 'COMPLETED'
    assert sum(e['kind'] == 'EXIT_APPROVED' for e in state['events']) == 1
    assert post('/api/scan', {'barcode':'8901234500019'}).status_code == 409


def test_fusion_requires_two_signals_and_disallows_manual_bypass():
    assert post('/api/fusion/mode', {'enabled':True}).status_code == 200
    manual = post('/api/simulate', {'product_id':'shampoo','action':'pickup'})
    assert manual.status_code == 409
    assert post('/api/fusion/camera', {'product_id':'shampoo','action':'pickup'}).status_code == 200
    assert post('/api/scan', {'barcode':'8901234500019'}).status_code == 200
    blocked = client.get('/api/status').json()
    assert blocked['fusion']['pending_count'] == 1
    assert blocked['exit']['state'] == 'REVIEW_REQUIRED'
    assert get_product('shampoo')['physical_qty'] == 0
    assert post('/api/exit/attempt').status_code == 409
    assert post('/api/fusion/weight', {'product_id':'shampoo','weight_grams':0}).status_code == 200
    assert get_product('shampoo')['physical_qty'] == 1
    assert client.get('/api/status').json()['exit']['state'] == 'READY'
    assert post('/api/exit/attempt').status_code == 200


def test_camera_jpeg_to_fusion_to_exit_path():
    empty = snap(set())
    stocked = snap(set('ABC'))
    without_a = snap(set('BC'))
    assert client.post('/api/vision/calibrate/empty', content=empty).status_code == 200
    assert client.post('/api/vision/calibrate/full', content=stocked).json()['ready']
    assert post('/api/fusion/mode', {'enabled':True}).status_code == 200
    for _ in range(4):
        assert client.post('/api/vision/frame', content=without_a).status_code == 200
    assert get_product('shampoo')['physical_qty'] == 0
    assert client.get('/api/status').json()['fusion']['pending_count'] == 1
    assert post('/api/fusion/weight', {'product_id':'shampoo','weight_grams':0}).status_code == 200
    assert get_product('shampoo')['physical_qty'] == 1
    assert post('/api/exit/attempt').status_code == 409
    assert post('/api/scan', {'barcode':'8901234500019'}).status_code == 200
    assert post('/api/exit/attempt').status_code == 200


def test_return_removes_physical_item_then_requires_scan_correction():
    post('/api/simulate', {'product_id':'cola','action':'pickup'})
    post('/api/scan', {'barcode':'8901234500033'})
    assert client.get('/api/status').json()['exit']['state'] == 'READY'
    post('/api/simulate', {'product_id':'cola','action':'return'})
    assert client.get('/api/status').json()['exit']['state'] == 'REVIEW_REQUIRED'
    assert post('/api/exit/attempt').status_code == 409
    post('/api/unscan', {'product_id':'cola'})
    assert client.get('/api/status').json()['exit']['state'] == 'EMPTY_CART'
    assert post('/api/exit/attempt').status_code == 409


def test_parallel_exit_triggers_do_not_duplicate_receipts():
    post('/api/simulate', {'product_id':'biscuits','action':'pickup'})
    post('/api/scan', {'barcode':'8901234500026'})
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: post('/api/exit/attempt'), range(4)))
    assert all(r.status_code == 200 for r in responses)
    ids = {r.json()['id'] for r in responses}
    assert len(ids) == 1
    state = client.get('/api/status').json()
    assert sum(e['kind'] == 'EXIT_APPROVED' for e in state['events']) == 1


def test_invalid_barcode_does_not_create_an_item():
    assert post('/api/scan', {'barcode':'NOT-A-REAL-SKU'}).status_code == 404
    assert not any(p['scanned_qty'] for p in client.get('/api/status').json()['products'])
