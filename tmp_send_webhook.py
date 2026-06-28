import json
import urllib.request

payload = {
    'requestId': '123e4567-e89b-12d3-a456-426614174002',
    'status': 'SUCCESS',
    'detectedAt': '2026-06-17T12:00:00Z',
    'detections': [
        {
            'type': 'UNKNOWN_PERSON',
            'confidence': 0.94,
            'boundingBox': {'x': 120.5, 'y': 85.0, 'width': 45.2, 'height': 110.8},
        }
    ],
    'processingTimeMs': 245,
    'modelVersion': 'yolov8x-face-v2.1',
}

req = urllib.request.Request(
    'http://127.0.0.1:8000/webhooks/onDetectionCompleted',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Authorization': 'Bearer local-dev-token', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode('utf-8')
        print('API RESP', resp.status, repr(body))
except Exception as exc:
    print('API ERR', type(exc).__name__, exc)
