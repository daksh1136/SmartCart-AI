"""Optional YOLO API behavior tested without torch/downloads."""
from types import SimpleNamespace
import cv2
import numpy as np
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def jpeg():
    ok, buf = cv2.imencode('.jpg', np.full((360,640,3),120,dtype=np.uint8))
    assert ok
    return buf.tobytes()


def test_status_bad_frame_and_generic_tracking_does_not_change_cart(monkeypatch):
    assert client.get('/api/vision/ai/status').json()['sku_verified'] is False
    assert client.post('/api/vision/ai/frame',content=b'invalid').status_code == 422

    class FakeTensor:
        def __init__(self,data): self.data=data
        def cpu(self): return self
        def tolist(self): return self.data

    class FakeModel:
        def track(self,**kwargs):
            assert kwargs['persist'] and kwargs['tracker']=='bytetrack.yaml'
            return [SimpleNamespace(names={39:'bottle'}, boxes=SimpleNamespace(
                xyxy=FakeTensor([[20,25,120,290]]), conf=FakeTensor([.89]),
                cls=FakeTensor([39]), id=FakeTensor([7])))]

    monkeypatch.setattr(main.yolo_assist,'_create_model',lambda:FakeModel())
    main.yolo_assist._model=None
    before=client.get('/api/status').json()['products']
    res=client.post('/api/vision/ai/frame',content=jpeg())
    assert res.status_code==200,res.text
    assert res.json()['detections'][0]['track_id']==7
    assert res.json()['detections'][0]['label']=='bottle'
    assert client.get('/api/status').json()['products']==before
