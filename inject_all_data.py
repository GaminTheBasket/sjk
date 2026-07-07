#!/usr/bin/env python3
"""
Script để gửi dữ liệu test cho toàn bộ hệ thống (Vision, Access, Metrics)
Dùng urllib built-in thay vì requests
"""
import json
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
CORE_BUSINESS_URL = "http://localhost:8020"
HEADERS = {
    "Authorization": "Bearer local-dev-token",
    "Content-Type": "application/json"
}

def send_request(url, data):
    """Gửi POST request"""
    try:
        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers=HEADERS, method='POST')
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return None, str(e)

def send_vision_detect():
    """Gửi dữ liệu phát hiện hình ảnh"""
    print("\n=== SENDING VISION DETECT DATA ===")
    vision_payloads = [
        {
            "requestId": "vision-001",
            "cameraId": "CAM-001",
            "capturedAt": "2026-07-06T10:00:00Z",
            "imageType": "URL",
            "imageUrl": "https://campus.local/images/cam-001/frame-1.jpg",
            "locationId": "GATE-01"
        },
        {
            "requestId": "vision-002",
            "cameraId": "CAM-002",
            "capturedAt": "2026-07-06T10:05:00Z",
            "imageType": "URL",
            "imageUrl": "https://campus.local/images/cam-002/frame-2.jpg",
            "locationId": "GATE-02"
        },
        {
            "requestId": "vision-003",
            "cameraId": "CAM-003",
            "capturedAt": "2026-07-06T10:10:00Z",
            "imageType": "URL",
            "imageUrl": "https://campus.local/images/cam-003/frame-3.jpg",
            "locationId": "BUILDING-A"
        }
    ]
    
    for payload in vision_payloads:
        status, resp = send_request(f"{BASE_URL}/vision/detect", payload)
        if status:
            print(f"✓ Vision detect {payload['cameraId']}: {status}")
        else:
            print(f"✗ Vision detect error: {resp}")
        time.sleep(0.5)

def send_access_check():
    """Gửi dữ liệu kiểm tra truy cập"""
    print("\n=== SENDING ACCESS CHECK DATA ===")
    access_payloads = [
        {
            "requestId": "access-001",
            "cardId": "CARD-123456",
            "gateId": "GATE-01",
            "direction": "IN",
            "timestamp": "2026-07-06T10:00:00Z"
        },
        {
            "requestId": "access-002",
            "cardId": "CARD-789012",
            "gateId": "GATE-02",
            "direction": "IN",
            "timestamp": "2026-07-06T10:05:00Z"
        },
        {
            "requestId": "access-003",
            "cardId": "CARD-345678",
            "gateId": "GATE-01",
            "direction": "OUT",
            "timestamp": "2026-07-06T10:15:00Z"
        },
        {
            "requestId": "access-004",
            "cardId": "CARD-999999",
            "gateId": "GATE-03",
            "direction": "IN",
            "timestamp": "2026-07-06T10:20:00Z"
        },
        {
            "requestId": "access-005",
            "cardId": "CARD-111111",
            "gateId": "GATE-02",
            "direction": "OUT",
            "timestamp": "2026-07-06T10:25:00Z"
        }
    ]
    
    for payload in access_payloads:
        status, resp = send_request(f"{BASE_URL}/access/check", payload)
        if status:
            print(f"✓ Access check {payload['cardId']}: {status}")
        else:
            print(f"✗ Access check error: {resp}")
        time.sleep(0.5)

def send_core_policy():
    """Gửi dữ liệu chính sách cốt lõi"""
    print("\n=== SENDING CORE POLICY DATA ===")
    policy_payloads = [
        {
            "requestId": "policy-001",
            "policyId": "POLICY-ACCESS-STRICT",
            "action": "ENFORCE",
            "target": "GATE-01",
            "timestamp": "2026-07-06T10:00:00Z"
        },
        {
            "requestId": "policy-002",
            "policyId": "POLICY-ALERT-SYSTEM",
            "action": "ENABLE",
            "target": "ALARM-SYSTEM",
            "timestamp": "2026-07-06T10:05:00Z"
        },
        {
            "requestId": "policy-003",
            "policyId": "POLICY-LOG-EVENTS",
            "action": "START",
            "target": "EVENT-LOG",
            "timestamp": "2026-07-06T10:10:00Z"
        }
    ]
    
    for payload in policy_payloads:
        status, resp = send_request(f"{BASE_URL}/core-policy/enforce", payload)
        if status:
            print(f"✓ Core policy {payload['policyId']}: {status}")
        else:
            print(f"✗ Core policy error: {resp}")
        time.sleep(0.5)

def get_request(url):
    """Gửi GET request"""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return None, str(e)

def wait_and_fetch_metrics():
    """Chờ và lấy metrics từ Core Business"""
    print("\n=== WAITING FOR ANALYTICS PROCESSING ===")
    print("Waiting 10 seconds for Analytics to process events...")
    time.sleep(10)
    
    print("\n=== FETCHING METRICS FROM CORE BUSINESS ===")
    status, resp = get_request(f"{CORE_BUSINESS_URL}/analytics/metrics/latest")
    
    if status == 200:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"collections/core_business_metrics_{timestamp}.json"
        
        with open(filename, 'w') as f:
            f.write(resp)
        
        print(f"✓ Metrics saved to: {filename}\n")
        print("--- Metrics Content ---")
        try:
            data = json.loads(resp)
            print(json.dumps(data, indent=2))
        except:
            print(resp)
        
        return resp
    else:
        print(f"✗ Error fetching metrics: {status} - {resp}")
        return None

if __name__ == "__main__":
    print("="*60)
    print("Data Injection for Full System")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)
    
    send_vision_detect()
    send_access_check()
    send_core_policy()
    
    metrics = wait_and_fetch_metrics()
    
    print("\n" + "="*60)
    print("✓ Data injection completed!")
    print("="*60)
