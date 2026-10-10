"""Optional generic YOLO/ByteTrack experiment; never changes checkout state."""
import importlib.util
import os
import threading

import cv2
import numpy as np
from fastapi import HTTPException

class YoloAssist:
    def __init__(self, model_name='yolo11n.pt'):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._last_error = None
        self._frame_count = 0

    def status(self):
        return {
            'installed': importlib.util.find_spec('ultralytics') is not None,
            'loaded': self._model is not None, 'model': self.model_name,
            'tracker': 'ByteTrack', 'frame_count': self._frame_count,
            'last_error': self._last_error, 'sku_verified': False,
            'note': 'Generic COCO classes, not product SKU recognition or theft detection.',
        }

    def _create_model(self):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise HTTPException(503, 'Optional AI not installed. In backend venv: pip install -r requirements-ai.txt') from exc
        return YOLO(self.model_name)

    def analyze(self, frame_bytes):
        image = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[0] < 120 or image.shape[1] < 240:
            raise HTTPException(422, 'Expected a valid JPEG at least 240x120')
        if image.shape[0] > 1080 or image.shape[1] > 1920:
            image = cv2.resize(image, (640,360))
        with self._lock:
            try:
                if self._model is None:
                    self._model = self._create_model()
                result = self._model.track(source=image, persist=True, tracker='bytetrack.yaml', imgsz=480,
                                          conf=0.35, device='cpu', verbose=False)[0]
                h, w = image.shape[:2]
                detections = []
                boxes = result.boxes
                if boxes is not None:
                    coords = boxes.xyxy.cpu().tolist()
                    confidence = boxes.conf.cpu().tolist()
                    labels = boxes.cls.cpu().tolist()
                    ids = boxes.id.cpu().tolist() if boxes.id is not None else [None] * len(coords)
                    for bbox, score, cls, track_id in zip(coords, confidence, labels, ids):
                        if len(detections) >= 30: break
                        x1,y1,x2,y2 = bbox
                        x1 = max(0,min(w,float(x1))); y1=max(0,min(h,float(y1)))
                        x2 = max(0,min(w,float(x2))); y2=max(0,min(h,float(y2)))
                        class_number = int(cls)
                        name = result.names[class_number]
                        detections.append({'label':str(name), 'confidence':round(float(score),3),
                                           'track_id':int(track_id) if track_id is not None else None,
                                           'box':[round(x1,1),round(y1,1),round(x2,1),round(y2,1)]})
                self._frame_count += 1
                self._last_error = None
                return {'frame_width':w,'frame_height':h,'frame_count':self._frame_count,
                        'detections':detections,'sku_verified':False,
                        'note':'Generic detections only. No product SKU/pickup/checkout inference.'}
            except HTTPException:
                raise
            except Exception as exc:
                self._last_error = f'{type(exc).__name__}: {exc}'
                raise HTTPException(503,'YOLO tracking failed: '+self._last_error) from exc

yolo_assist = YoloAssist(os.getenv('SMARTCART_YOLO_WEIGHTS','yolo11n.pt'))
