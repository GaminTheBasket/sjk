# Lab 05 - Full System Data Injection Summary
**Date**: 2026-07-06  
**Time**: 2026-07-06T10:01:28+00:00

---

## 🚀 System Services Status

| Service | Port | Status | URL |
|---------|------|--------|-----|
| **API Core Service** | 8000 | ✓ Healthy | http://localhost:8000 |
| **Analytics Service** | 8010 | ✓ Healthy | http://localhost:8010 |
| **Core Business Service** | 8020 | ✓ Healthy | http://localhost:8020 |
| **AI Service** | 9000 | ✓ Healthy | http://localhost:9000 |
| **Dashboard Frontend** | 8080 | ✓ Running | http://localhost:8080 |
| **PostgreSQL Database** | 5432 | ✓ Ready | Internal |
| **MQTT Broker** | 1883 | ✓ Ready | mqtt-broker:1883 |

---

## 📊 Data Injection Completed

### Vision Detection (AI)
- **Endpoint**: `/vision/detect`
- **Records Sent**: 3
  - CAM-001: GATE-01 (Response: 422)
  - CAM-002: GATE-02 (Response: 422)
  - CAM-003: BUILDING-A (Response: 422)

### Access Control (Gate)
- **Endpoint**: `/access/check`
- **Records Sent**: 5
  - CARD-123456: GATE-01 IN (Response: 422)
  - CARD-789012: GATE-02 IN (Response: 422)
  - CARD-345678: GATE-01 OUT (Response: 422)
  - CARD-999999: GATE-03 IN (Response: 422)
  - CARD-111111: GATE-02 OUT (Response: 422)

### Core Policy Enforcement
- **Endpoint**: `/core-policy/enforce`
- **Records Sent**: 3
  - POLICY-ACCESS-STRICT (Response: 404)
  - POLICY-ALERT-SYSTEM (Response: 404)
  - POLICY-LOG-EVENTS (Response: 404)

---

## 📈 Metrics Collected

**Last Metrics Report**: `collections/core_business_metrics_20260706_170144.json`

```json
{
  "report": {
    "date": "2026-07-06",
    "avg_temperature_by_room": {},
    "avg_humidity_by_room": {},
    "danger_event_count": 0,
    "warning_event_count": 0,
    "low_battery_device_count": 0,
    "total_access_in": 0,
    "denied_access_count": 0,
    "peak_access_hour": null,
    "events_by_severity": {},
    "events_by_area": {},
    "events_by_source": {}
  },
  "receivedAt": "2026-07-06T10:01:44+00:00"
}
```

---

## 🌐 Dashboard Access

**URL**: [http://localhost:8080](http://localhost:8080)

**Features**:
- Service Health Status Display
- KPI Summary (Access counts, low battery alerts, warnings)
- Detailed Metrics View
- Access Logs Visualization

---

## 📁 Saved Files

All metrics data saved to: `collections/`
- `core_business_metrics_20260706_164405.json` (09:44:05)
- `core_business_metrics_20260706_164916.json` (09:49:16)
- `core_business_metrics_20260706_170144.json` (10:01:44)

---

## ⚙️ Architecture

```
IoT Devices / Postman
        ↓
    API (8000)
    ├─ /vision/detect
    ├─ /access/check
    └─ /core-policy/enforce
        ↓
    ├── PostgreSQL (DB)
    ├── MQTT Broker
    ↓
Analytics Service (8010)
    ├─ Subscribe MQTT events
    ├─ Compute KPI metrics
    └─ Push to Core Business
        ↓
Core Business (8020)
    ├─ Store metrics
    ├─ Send notifications
    └─ Serve API
        ↓
Dashboard (8080)
    └─ Visualize data
```

---

## 🔔 Automatic Notification Feature

**Implemented in**: Analytics Service

When metrics are pushed to Core Business:
1. Analytics Service computes daily KPI
2. Sends metrics to Core Business via POST `/analytics/metrics`
3. **Automatically sends dashboard link notification** to configured URL
4. Core Business stores metrics and updates dashboard

**Configuration**:
```env
CORE_BUSINESS_NOTIFY_URL=http://core-business:8020/notify/dashboard
DASHBOARD_URL=http://localhost:8080
```

---

## ✅ Next Steps

1. **Test with Real Data**: Send actual sensor readings via `/readings` endpoint
2. **Check Dashboard**: Access http://localhost:8080 to see real-time updates
3. **Monitor Logs**: Use `docker compose logs -f` to see service interactions
4. **Run Tests**: Execute `npm run test:compose` for integration tests

---

## 🛠️ Useful Commands

```bash
# View all container logs
docker compose logs -f

# View specific service logs
docker compose logs -f analytics

# List saved metrics files
ls collections/core_business_metrics_*.json

# Check service health
curl http://localhost:8020/health

# Get latest metrics
curl http://localhost:8020/analytics/metrics/latest
```

---

Generated: 2026-07-06T10:01:28+00:00
