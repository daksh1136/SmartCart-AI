"""Phase 7 deterministic regression tests. No real cameras, sensors or payments."""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_demo():
    assert client.post('/api/reset').status_code == 200


def call(endpoint, data=None):
    return client.post(endpoint, json=data) if data is not None else client.post(endpoint)


def screenshot(zones):
    pixels = np.full((360, 640, 3), 225, dtype=np.uint8)
    for idx, zone in enumerate('ABC'):
        if zone in zones:
            x = idx * 640 // 3
            cv2.rectangle(pixels, (x+43, 90), (x+168, 280), (34, 75, 165), -1)
    ok, jpg = cv2.imencode('.jpg', pixels)
    assert ok
    return jpg.tobytes()


def test_guided_demo_progress_requires_actual_events():
    initial = client.get('/api/status').json()['demo']
    assert initial['steps'][0]['done'] is True
    assert sum(x['done'] for x in initial['steps']) == 1
    assert initial['current_step'] == 1

    assert call('/api/simulate', {'product_id':'shampoo', 'action':'pickup'}).status_code == 200
    assert client.get('/api/status').json()['demo']['steps'][1]['done'] is True
    assert call('/api/exit/attempt').status_code == 409
    assert client.get('/api/status').json()['demo']['steps'][2]['done'] is True
    assert call('/api/scan', {'barcode':'8901234500019'}).status_code == 200
    assert client.get('/api/status').json()['demo']['current_step'] == 4
    receipt = call('/api/exit/attempt')
    assert receipt.status_code == 200
    completed = client.get('/api/status').json()['demo']
    assert completed['complete'] and completed['current_step'] is None
    assert call('/api/exit/attempt').json()['id'] == receipt.json()['id']
    assert call('/api/reset').status_code == 200
    assert not client.get('/api/status').json()['demo']['complete']


def test_walkthrough_matches_shampoo_and_survives_long_event_history():
    assert call('/api/simulate', {'product_id':'biscuits', 'action':'pickup'}).status_code == 200
    assert not client.get('/api/status').json()['demo']['steps'][1]['done']
    assert call('/api/scan', {'barcode':'8901234500026'}).status_code == 200
    assert not client.get('/api/status').json()['demo']['steps'][3]['done']
    for _ in range(11):
        call('/api/simulate', {'product_id':'biscuits', 'action':'return'})
        call('/api/simulate', {'product_id':'biscuits', 'action':'pickup'})
    call('/api/simulate', {'product_id':'biscuits', 'action':'return'})
    call('/api/simulate', {'product_id':'shampoo', 'action':'pickup'})
    call('/api/scan', {'barcode':'8901234500019'})
    demo = client.get('/api/status').json()['demo']
    assert demo['steps'][1]['done'] and demo['steps'][3]['done']


def test_camera_upload_rejects_oversized_body():
    response = client.post('/api/vision/frame', content=b'x' * 2_000_001,
                           headers={'Content-Type':'image/jpeg'})
    assert response.status_code == 413


def test_camera_reports_rejection_and_does_not_claim_confirmed_pickup_after_exit():
    empty = screenshot(set())
    stocked = screenshot(set('ABC'))
    missing_shampoo = screenshot(set('BC'))
    assert client.post('/api/vision/calibrate/empty', content=empty).status_code == 200
    assert client.post('/api/vision/calibrate/full', content=stocked).status_code == 200

    assert call('/api/simulate', {'product_id':'biscuits','action':'pickup'}).status_code == 200
    assert call('/api/scan', {'barcode':'8901234500026'}).status_code == 200
    assert call('/api/exit/attempt').status_code == 200

    frames = [client.post('/api/vision/frame', content=missing_shampoo) for _ in range(4)]
    assert all(r.status_code == 200 for r in frames)
    last = frames[-1].json()
    assert last['transitions'] == []
    assert last['rejected'][0]['zone'] == 'A'
    assert 'already checked out' in last['rejected'][0]['reason']
    camera_health = client.get('/api/status').json()['vision']
    assert camera_health['frames_processed'] == 4
    assert camera_health['stream_recent'] is True
    assert camera_health['last_frame_at']
    assert camera_health['rejected_events']
    assert next(x for x in client.get('/api/status').json()['products'] if x['id']=='shampoo')['physical_qty'] == 0


def test_camera_low_contrast_does_not_change_cart():
    blank = screenshot(set())
    assert client.post('/api/vision/calibrate/empty', content=blank).status_code == 200
    result = client.post('/api/vision/calibrate/full', content=blank).json()
    assert set(result['calibration_warning']) == set('ABC')
    for _ in range(6):
        response = client.post('/api/vision/frame', content=blank).json()
        assert not response['transitions']
    assert all(p['physical_qty']==0 for p in client.get('/api/status').json()['products'])


def test_uncertain_weight_continues_to_block_after_operator_clears_pending():
    assert call('/api/fusion/mode', {'enabled':True}).status_code == 200
    assert call('/api/fusion/weight', {'product_id':'shampoo','weight_grams':120}).status_code == 200
    assert client.get('/api/status').json()['fusion']['blocked']
    assert call('/api/fusion/clear').status_code == 200
    assert client.get('/api/status').json()['fusion']['blocked']
    assert call('/api/fusion/weight', {'product_id':'shampoo','weight_grams':250}).status_code == 200
    assert not client.get('/api/status').json()['fusion']['blocked']


def test_reset_after_checkout_allows_fresh_receipt():
    assert call('/api/simulate',{'product_id':'cola','action':'pickup'}).status_code == 200
    assert call('/api/scan',{'barcode':'8901234500033'}).status_code == 200
    first = call('/api/exit/attempt').json()['id']
    assert call('/api/reset').status_code == 200
    assert call('/api/simulate',{'product_id':'cola','action':'pickup'}).status_code == 200
    assert call('/api/scan',{'barcode':'8901234500033'}).status_code == 200
    second = call('/api/exit/attempt').json()['id']
    assert first != second
