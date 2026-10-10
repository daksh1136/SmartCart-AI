import os
import tempfile
from pathlib import Path

os.environ["SMARTCART_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def setup_function():
    client.post("/api/reset")


def test_pickup_scan_checkout():
    assert client.post("/api/simulate", json={"product_id": "shampoo", "action": "pickup"}).status_code == 200
    cart = client.get("/api/status").json()
    assert cart["discrepancy_count"] == 1
    assert not cart["verified"]
    assert client.post("/api/checkout").status_code == 409
    assert client.post("/api/scan", json={"barcode": "8901234500019"}).status_code == 200
    cart = client.get("/api/status").json()
    assert cart["verified"] and cart["total_paise"] == 19900
    receipt = client.post("/api/checkout")
    assert receipt.status_code == 200
    assert receipt.json()["payment"].startswith("SIMULATED")
    assert client.post("/api/scan", json={"barcode": "8901234500019"}).status_code == 409


def test_return_without_scan_and_wrong_scan():
    assert client.post("/api/simulate", json={"product_id": "cola", "action": "return"}).status_code == 409
    client.post("/api/simulate", json={"product_id": "shampoo", "action": "pickup"})
    client.post("/api/scan", json={"barcode": "8901234500026"})
    assert client.get("/api/status").json()["discrepancy_count"] == 2
    client.post("/api/simulate", json={"product_id": "shampoo", "action": "return"})
    assert client.get("/api/status").json()["discrepancy_count"] == 1
    assert client.post("/api/unscan", json={"product_id": "biscuits"}).status_code == 200
    assert client.get("/api/status").json()["discrepancy_count"] == 0
    assert client.post("/api/checkout").status_code == 409


def test_calibrated_camera_pickup_and_return():
    import cv2
    import numpy as np

    def render(zones):
        image = np.full((360, 640, 3), 210, dtype=np.uint8)
        for index, zone in enumerate('ABC'):
            if zone in zones:
                start = index * 640 // 3
                cv2.rectangle(image, (start + 45, 110), (start + 165, 290), (50, 70, 105), -1)
        ok, buff = cv2.imencode('.jpg', image)
        assert ok
        return buff.tobytes()

    empty = render(set())
    all_stocked = render({'A', 'B', 'C'})
    missing_a = render({'B', 'C'})
    assert client.post('/api/vision/calibrate/empty', content=empty,
                       headers={'Content-Type': 'image/jpeg'}).status_code == 200
    calib = client.post('/api/vision/calibrate/full', content=all_stocked,
                        headers={'Content-Type': 'image/jpeg'}).json()
    assert calib['ready'] is True
    assert calib['calibration_warning'] == []
    for _ in range(4):
        client.post('/api/vision/frame', content=missing_a, headers={'Content-Type': 'image/jpeg'})
    assert client.get('/api/status').json()['products'][0]['physical_qty'] == 1
    for _ in range(4):
        client.post('/api/vision/frame', content=all_stocked, headers={'Content-Type': 'image/jpeg'})
    assert client.get('/api/status').json()['products'][0]['physical_qty'] == 0


def test_fusion_two_signals_required_for_physical_cart():
    assert client.post('/api/fusion/mode', json={'enabled': True}).status_code == 200
    signal = client.post('/api/fusion/camera', json={'product_id':'shampoo', 'action':'pickup'})
    assert signal.status_code == 200
    before = signal.json()
    assert before['fusion']['pending_count'] == 1
    assert before['products'][0]['physical_qty'] == 0
    client.post('/api/scan', json={'barcode': '8901234500019'})
    assert not client.get('/api/status').json()['verified']
    assert client.post('/api/checkout').status_code == 409
    confirmed = client.post('/api/fusion/weight', json={'product_id':'shampoo', 'weight_grams':0})
    assert confirmed.status_code == 200
    after = confirmed.json()
    assert after['fusion']['pending_count'] == 0
    assert after['products'][0]['physical_qty'] == 1
    assert after['verified']
    # Identical weight reading must never count twice.
    unchanged = client.post('/api/fusion/weight', json={'product_id':'shampoo', 'weight_grams':0})
    assert unchanged.json()['products'][0]['physical_qty'] == 1
    assert client.post('/api/checkout').status_code == 200


def test_fusion_return_and_sensor_mismatch():
    client.post('/api/fusion/mode', json={'enabled':True})
    client.post('/api/fusion/camera', json={'product_id':'shampoo','action':'pickup'})
    bad_weight = client.post('/api/fusion/weight', json={'product_id':'biscuits', 'weight_grams':0})
    assert bad_weight.json()['fusion']['pending_count'] == 2
    assert bad_weight.json()['products'][0]['physical_qty'] == 0
    assert client.post('/api/fusion/mode',json={'enabled':False}).status_code == 409
    good_weight = client.post('/api/fusion/weight', json={'product_id':'shampoo', 'weight_grams':0})
    assert good_weight.json()['products'][0]['physical_qty'] == 1
    assert good_weight.json()['fusion']['pending_count'] == 1  # unmatched biscuit signal
    assert client.post('/api/fusion/clear').status_code == 200
    # Reconcile return in reverse order (weight then camera).
    client.post('/api/fusion/weight', json={'product_id':'shampoo','weight_grams':250})
    end = client.post('/api/fusion/camera', json={'product_id':'shampoo','action':'return'})
    assert end.json()['products'][0]['physical_qty'] == 0
    assert end.json()['fusion']['pending_count'] == 0


def test_fusion_uncertain_weight_and_invalid_weight():
    client.post('/api/fusion/mode',json={'enabled':True})
    assert client.post('/api/fusion/weight',json={'product_id':'cola','weight_grams':9999}).status_code == 422
    uncertain = client.post('/api/fusion/weight',json={'product_id':'cola','weight_grams':160})
    assert uncertain.json()['fusion']['blocked'] is True
    assert uncertain.json()['fusion']['weight_states']['cola'] == 'UNCERTAIN'
    cleared = client.post('/api/fusion/weight',json={'product_id':'cola','weight_grams':330})
    assert cleared.json()['fusion']['blocked'] is False


def test_camera_frames_feed_fusion_without_double_count():
    import cv2
    import numpy as np

    def snap(zones):
        img = np.full((360,640,3),210,dtype=np.uint8)
        for idx, z in enumerate('ABC'):
            if z in zones:
                x = idx * 640//3
                cv2.rectangle(img,(x+45,110),(x+165,290),(50,70,105),-1)
        ok, buf = cv2.imencode('.jpg',img)
        assert ok
        return buf.tobytes()

    client.post('/api/vision/calibrate/empty',content=snap(set()),headers={'Content-Type':'image/jpeg'})
    client.post('/api/vision/calibrate/full',content=snap({'A','B','C'}),headers={'Content-Type':'image/jpeg'})
    client.post('/api/fusion/mode',json={'enabled':True})
    for _ in range(4):
        client.post('/api/vision/frame',content=snap({'B','C'}),headers={'Content-Type':'image/jpeg'})
    pending = client.get('/api/status').json()
    assert pending['fusion']['pending_count'] == 1
    assert pending['products'][0]['physical_qty'] == 0
    matched = client.post('/api/fusion/weight',json={'product_id':'shampoo','weight_grams':0}).json()
    assert matched['products'][0]['physical_qty'] == 1
    assert matched['fusion']['pending_count'] == 0
