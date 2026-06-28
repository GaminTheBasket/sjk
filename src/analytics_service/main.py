import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional

import paho.mqtt.client as mqtt
import paho.mqtt.publish as mqtt_publish
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "analytics-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
APP_PORT = int(os.getenv("ANALYTICS_PORT", "8010"))
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
CORE_BUSINESS_URL = os.getenv("CORE_BUSINESS_URL", "http://core-business:8020/analytics/metrics")
CORE_PUSH_INTERVAL_SECONDS = int(os.getenv("CORE_PUSH_INTERVAL_SECONDS", "60"))
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")

app = FastAPI(
    title="FIT4110 Lab 05 - Analytics Service",
    version=SERVICE_VERSION,
    description=(
        "Service tổng hợp KPI cho Smart Campus. Thu thập event qua MQTT, tính toán xu hướng và trả về metrics cho dashboard."
    ),
)

LOCK = threading.Lock()
SENSOR_STATS: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"temp_sum": 0.0, "temp_count": 0, "humidity_sum": 0.0, "humidity_count": 0}))
SEVERITY_COUNTS: Dict[str, Counter] = defaultdict(Counter)
AREA_EVENT_COUNTS: Dict[str, Counter] = defaultdict(Counter)
EVENT_SOURCE_COUNTS: Dict[str, Counter] = defaultdict(Counter)
LOW_BATTERY_DEVICES: set = set()
ACCESS_COUNTS: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total_access_in": 0, "denied_access_count": 0})
ACCESS_HOUR_COUNTS: Dict[str, Counter] = defaultdict(Counter)


class HealthStatus(BaseModel):
    status: str
    service: str
    time: str


class MetricsResponse(BaseModel):
    date: str
    avg_temperature_by_room: Dict[str, float] = Field(default_factory=dict)
    avg_humidity_by_room: Dict[str, float] = Field(default_factory=dict)
    danger_event_count: int = 0
    warning_event_count: int = 0
    low_battery_device_count: int = 0
    total_access_in: int = 0
    denied_access_count: int = 0
    peak_access_hour: Optional[str] = None
    events_by_severity: Dict[str, int] = Field(default_factory=dict)
    events_by_area: Dict[str, int] = Field(default_factory=dict)
    events_by_source: Dict[str, int] = Field(default_factory=dict)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def bucket_date(dt: Optional[datetime]) -> str:
    if dt is None:
        dt = now_utc()
    return dt.date().isoformat()


def get_event_source(topic: str) -> str:
    if "sensor" in topic:
        return "sensor"
    if "access" in topic:
        return "access"
    if "camera" in topic:
        return "camera"
    if "alerts" in topic or "event" in topic:
        return "alerts"
    return "unknown"


def increment_source_count(topic: str, payload: Dict[str, Any]) -> None:
    timestamp = parse_iso_ts(payload.get("timestamp")) or now_utc()
    bucket = bucket_date(timestamp)
    source = get_event_source(topic)
    with LOCK:
        EVENT_SOURCE_COUNTS[bucket][source] += 1


def update_sensor_stats(payload: Dict[str, Any]) -> None:
    room = payload.get("room") or payload.get("locationId") or payload.get("area")
    if not room:
        return

    temp = payload.get("temperature")
    humidity = payload.get("humidity")
    timestamp = parse_iso_ts(payload.get("timestamp")) or now_utc()
    bucket = bucket_date(timestamp)

    with LOCK:
        stats = SENSOR_STATS[bucket][room]
        if isinstance(temp, (int, float)):
            stats["temp_sum"] += float(temp)
            stats["temp_count"] += 1
        if isinstance(humidity, (int, float)):
            stats["humidity_sum"] += float(humidity)
            stats["humidity_count"] += 1


def update_alert_stats(topic: str, payload: Dict[str, Any]) -> None:
    severity = payload.get("severity") or payload.get("level") or "unknown"
    severity_key = str(severity).lower()
    timestamp = parse_iso_ts(payload.get("timestamp")) or now_utc()
    bucket = bucket_date(timestamp)
    area = payload.get("area") or payload.get("room") or payload.get("locationId") or "unknown"
    device_id = payload.get("device") or payload.get("deviceId")

    with LOCK:
        if severity_key in {"danger", "critical"}:
            SEVERITY_COUNTS[bucket]["danger"] += 1
        elif severity_key in {"warning", "caution"}:
            SEVERITY_COUNTS[bucket]["warning"] += 1
        elif severity_key in {"low", "low_battery", "battery"}:
            SEVERITY_COUNTS[bucket]["warning"] += 1
        else:
            SEVERITY_COUNTS[bucket][severity_key] += 1

        AREA_EVENT_COUNTS[bucket][area] += 1
        if device_id and "battery" in payload:
            level = payload.get("battery")
            if isinstance(level, (int, float)) and level < 20:
                LOW_BATTERY_DEVICES.add(str(device_id))
        if payload.get("status") == "LOW_BATTERY" or payload.get("batteryStatus") == "LOW":
            if device_id:
                LOW_BATTERY_DEVICES.add(str(device_id))


def update_policy_stats(payload: Dict[str, Any]) -> None:
    severity = payload.get("severity") or payload.get("level") or "unknown"
    severity_key = str(severity).lower()
    timestamp = parse_iso_ts(payload.get("timestamp")) or now_utc()
    bucket = bucket_date(timestamp)
    area = payload.get("target") or payload.get("target_team") or "unknown"

    with LOCK:
        if severity_key in {"danger", "critical"}:
            SEVERITY_COUNTS[bucket]["danger"] += 1
        elif severity_key in {"warning", "caution"}:
            SEVERITY_COUNTS[bucket]["warning"] += 1
        else:
            SEVERITY_COUNTS[bucket][severity_key] += 1

        AREA_EVENT_COUNTS[bucket][area] += 1


def update_access_stats(payload: Dict[str, Any]) -> None:
    direction = str(payload.get("direction", "")).upper()
    status_text = str(payload.get("status", "")).upper()
    timestamp = parse_iso_ts(payload.get("timestamp")) or now_utc()
    bucket = bucket_date(timestamp)
    hour_bucket = timestamp.strftime("%H:00-%H:59")

    with LOCK:
        if direction == "IN":
            ACCESS_COUNTS[bucket]["total_access_in"] += 1
        if status_text == "DENIED" or status_text == "BLOCKED":
            ACCESS_COUNTS[bucket]["denied_access_count"] += 1
        ACCESS_HOUR_COUNTS[bucket][hour_bucket] += 1

        area = payload.get("area") or payload.get("locationId") or payload.get("gateId") or "unknown"
        AREA_EVENT_COUNTS[bucket][area] += 1


def handle_event(topic: str, payload: Dict[str, Any]) -> None:
    increment_source_count(topic, payload)
    if "sensor" in topic:
        update_sensor_stats(payload)
        return
    if "access" in topic:
        update_access_stats(payload)
        return
    if "policy" in topic:
        update_policy_stats(payload)
        return
    if "camera" in topic or "alerts" in topic or "event" in topic:
        update_alert_stats(topic, payload)
        return


def mqtt_on_connect(client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
    logger.info("Connected to MQTT broker %s:%s with rc=%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT, rc)
    topics = [
        ("smart-campus/events/sensor", 0),
        ("smart-campus/events/access", 0),
        ("smart-campus/events/camera", 0),
        ("smart-campus/events/alerts", 0),
        ("smart-campus/events/policy", 0),
    ]
    for topic, qos in topics:
        client.subscribe(topic, qos)
        logger.info("Subscribed to MQTT topic %s", topic)


def mqtt_on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    payload_bytes = message.payload
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        logger.warning("Skipping invalid JSON MQTT message on %s: %s", message.topic, exc)
        return

    logger.info("MQTT event received topic=%s payload=%s", message.topic, payload)
    handle_event(message.topic.decode() if isinstance(message.topic, bytes) else message.topic, payload)


def start_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id="analytics-service-client")
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message
    client.reconnect_delay_set(min_delay=2, max_delay=30)
    client.connect_async(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()
    return client


def publish_demo_events() -> None:
    demo_events = [
        ("smart-campus/events/sensor", {"timestamp": now_utc().isoformat(), "room": "lab-a101", "temperature": 27.3, "humidity": 61}),
        ("smart-campus/events/access", {"timestamp": now_utc().isoformat(), "gateId": "gate-a", "direction": "IN", "status": "ALLOWED", "area": "gate-a"}),
        ("smart-campus/events/camera", {"timestamp": now_utc().isoformat(), "area": "lab-a101", "severity": "warning", "device": "camera-01"}),
        ("smart-campus/events/alerts", {"timestamp": now_utc().isoformat(), "severity": "danger", "area": "lab-a101", "device": "sensor-05", "battery": 12}),
    ]
    for topic, payload in demo_events:
        try:
            mqtt_publish.single(topic, payload=json.dumps(payload), hostname=MQTT_BROKER_HOST, port=MQTT_BROKER_PORT)
            logger.info("Published demo event to %s", topic)
        except Exception as exc:
            logger.warning("Could not publish demo MQTT event to %s: %s", topic, exc)


@app.on_event("startup")
def startup_event() -> None:
    logger.info("Starting Analytics Service on port %s", APP_PORT)
    app.state.mqtt_client = start_mqtt_client()
    time.sleep(2)
    publish_demo_events()
    if CORE_PUSH_INTERVAL_SECONDS > 0:
        core_thread = threading.Thread(target=core_push_worker, daemon=True)
        core_thread.start()
        app.state.core_thread = core_thread


@app.on_event("shutdown")
def shutdown_event() -> None:
    client = getattr(app.state, "mqtt_client", None)
    if client is not None:
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT client stopped")


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", service=SERVICE_NAME, time=now_utc().isoformat())


def build_daily_metrics(target: str) -> MetricsResponse:
    with LOCK:
        sensor_by_room = SENSOR_STATS.get(target, {})
        severity = SEVERITY_COUNTS.get(target, Counter())
        access = ACCESS_COUNTS.get(target, {"total_access_in": 0, "denied_access_count": 0})
        hour_counts = ACCESS_HOUR_COUNTS.get(target, Counter())
        area_counts = AREA_EVENT_COUNTS.get(target, Counter())
        source_counts = EVENT_SOURCE_COUNTS.get(target, Counter())
        low_battery_count = len(LOW_BATTERY_DEVICES)

    avg_temp = {
        room: stats["temp_sum"] / stats["temp_count"]
        for room, stats in sensor_by_room.items()
        if stats["temp_count"] > 0
    }
    avg_humidity = {
        room: stats["humidity_sum"] / stats["humidity_count"]
        for room, stats in sensor_by_room.items()
        if stats["humidity_count"] > 0
    }

    peak_hour = None
    if hour_counts:
        best_hour, _ = hour_counts.most_common(1)[0]
        peak_hour = best_hour

    return MetricsResponse(
        date=target,
        avg_temperature_by_room={k: round(v, 2) for k, v in avg_temp.items()},
        avg_humidity_by_room={k: round(v, 2) for k, v in avg_humidity.items()},
        danger_event_count=int(severity.get("danger", 0)),
        warning_event_count=int(severity.get("warning", 0)),
        low_battery_device_count=low_battery_count,
        total_access_in=int(access.get("total_access_in", 0)),
        denied_access_count=int(access.get("denied_access_count", 0)),
        peak_access_hour=peak_hour,
        events_by_severity={k: int(v) for k, v in severity.items()},
        events_by_area={k: int(v) for k, v in area_counts.items()},
        events_by_source={k: int(v) for k, v in source_counts.items()},
    )


def push_metrics_to_core(metrics: MetricsResponse) -> Dict[str, Any]:
    payload = json.dumps(metrics.model_dump()).encode("utf-8")
    request = urllib.request.Request(
        CORE_BUSINESS_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            logger.info("Pushed metrics for date=%s to core business, status=%s", metrics.date, response.status)
            return {"success": True, "status": response.status, "response": body}
    except urllib.error.HTTPError as http_err:
        logger.warning("Failed to push metrics to core business, HTTP %s: %s", http_err.code, http_err.reason)
        return {"success": False, "status": http_err.code, "error": str(http_err)}
    except Exception as exc:
        logger.warning("Failed to push metrics to core business: %s", exc)
        return {"success": False, "error": str(exc)}


def core_push_worker() -> None:
    while True:
        time.sleep(CORE_PUSH_INTERVAL_SECONDS)
        metrics = build_daily_metrics(date.today().isoformat())
        if metrics.events_by_severity or metrics.events_by_area or metrics.total_access_in or metrics.low_battery_device_count:
            push_metrics_to_core(metrics)


@app.get("/metrics/daily", response_model=MetricsResponse)
def get_daily_metrics(date_str: Optional[str] = Query(default=None, alias="date")) -> MetricsResponse:
    target = date_str or date.today().isoformat()
    metrics = build_daily_metrics(target)
    push_metrics_to_core(metrics)
    return metrics


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)
