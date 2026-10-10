"""No network, no YOLO download: test the exact API with synthetic package images."""

import cv2
import numpy as np
from fastapi.testclient import TestClient
import main
from sku_recognizer import SKURecognizer

client = TestClient(main.app)


def frame_for(items):
    img = np.full((360, 640, 3), 225, dtype=np.uint8)
    palette = {'shampoo': (230, 80, 70), 'biscuits': (30, 130, 230), 'cola': (55, 60, 55)}
    for i, zone in enumerate('ABC'):
        product = items.get(zone)
        if product is None:
            continue
        left = i * 640 // 3 + 58
        cv2.rectangle(img, (left, 82), (left + 104, 300), palette[product], -1)
        for n in range(5):
            cv2.line(img, (left + 5, 105 + n * 32), (left + 100, 100 + n * 32),
                     (255, 255, 255) if product != 'cola' else (185, 215, 170), 4)
        cv2.putText(img, product[:3].upper(), (left + 9, 204),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2)
    ok, data = cv2.imencode('.jpg', img)
    assert ok
    return data.tobytes()


def test_needs_enrollment_then_predicts_three_products(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'sku_recognizer', SKURecognizer(tmp_path))
    stocked = frame_for({'A': 'shampoo', 'B': 'biscuits', 'C': 'cola'})
    before = client.post('/api/vision/sku/recognize', content=stocked)
    assert before.status_code == 409
    for product in ('shampoo', 'biscuits', 'cola'):
        result = client.post(f'/api/vision/sku/enroll/{product}', content=stocked)
        assert result.status_code == 200
    results = client.post('/api/vision/sku/recognize', content=stocked)
    assert results.status_code == 200
    assert [z['result'] for z in results.json()['zones']] == ['MATCH'] * 3
    assert not any('physical_qty' in z for z in results.json()['zones'])
    assert set(client.get('/api/vision/sku/status').json()['enrolled']) == {'shampoo','biscuits','cola'}
    # No physical cart mutations from experimental SKU appearance.
    client.post('/api/reset')
    assert all(p['physical_qty'] == 0 for p in client.get('/api/status').json()['products'])
    reloaded = SKURecognizer(tmp_path)
    assert reloaded.status()['ready']


def test_possible_mismatch_is_only_an_advisory(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'sku_recognizer', SKURecognizer(tmp_path))
    stocked = frame_for({'A': 'shampoo', 'B': 'biscuits', 'C': 'cola'})
    for product in ('shampoo', 'biscuits', 'cola'):
        client.post(f'/api/vision/sku/enroll/{product}', content=stocked)
    # A appears to contain the biscuits package rather than shampoo.
    wrong = frame_for({'A': 'biscuits', 'B': 'biscuits', 'C': 'cola'})
    result = client.post('/api/vision/sku/recognize', content=wrong)
    assert result.status_code == 200
    assert result.json()['zones'][0]['result'] == 'POSSIBLE_MISMATCH'
    assert client.post('/api/vision/sku/enroll/not_a_product', content=stocked).status_code == 404
    assert client.post('/api/vision/sku/recognize', content=b'invalid').status_code == 422
