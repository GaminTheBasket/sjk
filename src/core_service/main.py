import json
import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "core-business")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
APP_PORT = int(os.getenv("CORE_BUSINESS_PORT", "8020"))
ACCESS_LOG_SERVICE_URL = os.getenv("ACCESS_LOG_SERVICE_URL", "http://api:8000/access/logs/recent")
ACCESS_LOG_AUTH_TOKEN = os.getenv("ACCESS_LOG_AUTH_TOKEN", "local-dev-token")

app = FastAPI(
    title="FIT4110 Lab 05 - Core Business Service",
    version=SERVICE_VERSION,
    description="Core Business trung tâm nhận và lưu trữ báo cáo KPI từ Analytics Service.",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTIONS_FILE = REPO_ROOT / "collections" / "access_logs_recent.json"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
    ,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

LATEST_METRICS: Dict[str, Any] = {}
LOCK = threading.Lock()

BUSINESS_CORE_NOTIFICATION_URL = os.getenv("BUSINESS_CORE_NOTIFICATION_URL", "")
DEFAULT_DASHBOARD_URL = os.getenv("DEFAULT_DASHBOARD_URL", f"http://localhost:{APP_PORT}/dashboard")


class HealthStatus(BaseModel):
    status: str
    service: str
    time: str


class MetricsReport(BaseModel):
    date: str
    avg_temperature_by_room: Dict[str, float]
    avg_humidity_by_room: Dict[str, float]
    danger_event_count: int
    warning_event_count: int
    low_battery_device_count: int
    total_access_in: int
    denied_access_count: int
    peak_access_hour: Optional[str] = None
    events_by_severity: Dict[str, int] = Field(default_factory=dict)
    events_by_area: Dict[str, int] = Field(default_factory=dict)
    events_by_source: Dict[str, int] = Field(default_factory=dict)


class DashboardNotification(BaseModel):
    dashboard_url: HttpUrl
    message: Optional[str] = None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def send_dashboard_notification(payload: DashboardNotification) -> None:
    if not BUSINESS_CORE_NOTIFICATION_URL:
        logger.info("BUSINESS_CORE_NOTIFICATION_URL not configured, skipping dashboard notification")
        return

    data = json.dumps(payload.model_dump()).encode("utf-8")
    request = urllib.request.Request(
        BUSINESS_CORE_NOTIFICATION_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            logger.info(
                "Sent dashboard notification to %s, status=%s",
                BUSINESS_CORE_NOTIFICATION_URL,
                response.status,
            )
    except urllib.error.HTTPError as http_err:
        logger.warning(
            "Failed to send dashboard notification, HTTP %s: %s",
            http_err.code,
            http_err.reason,
        )
    except Exception as exc:
        logger.warning("Failed to send dashboard notification: %s", exc)


@app.on_event("startup")
def startup_send_dashboard_link() -> None:
    if not BUSINESS_CORE_NOTIFICATION_URL:
        return

    payload = DashboardNotification(
        dashboard_url=os.getenv("DASHBOARD_URL", DEFAULT_DASHBOARD_URL),
        message="Dashboard đã sẵn sàng",
    )
    send_dashboard_notification(payload)


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", service=SERVICE_NAME, time=now_utc())


@app.get("/", response_class=HTMLResponse)
def dashboard_index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view() -> HTMLResponse:
    return dashboard_index()


@app.get("/collections/access_logs_recent.json")
def access_logs_recent() -> JSONResponse:
    request = urllib.request.Request(
        ACCESS_LOG_SERVICE_URL,
        headers={"Authorization": f"Bearer {ACCESS_LOG_AUTH_TOKEN}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            return JSONResponse(content=json.loads(body))
    except urllib.error.HTTPError as http_err:
        logger.warning("Failed to fetch live access logs, HTTP %s: %s", http_err.code, http_err.reason)
        try:
            content = json.loads(COLLECTIONS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            content = {"items": []}
        return JSONResponse(content=content)
    except Exception as exc:
        logger.warning("Failed to fetch live access logs: %s", exc)
        try:
            content = json.loads(COLLECTIONS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            content = {"items": []}
        return JSONResponse(content=content)


@app.post("/notify/dashboard", response_model=DashboardNotification)
def notify_dashboard_endpoint(payload: DashboardNotification) -> DashboardNotification:
    if not BUSINESS_CORE_NOTIFICATION_URL:
        raise HTTPException(status_code=500, detail="Business core notification URL is not configured")

    data = json.dumps(payload.model_dump()).encode("utf-8")
    request = urllib.request.Request(
        BUSINESS_CORE_NOTIFICATION_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            logger.info("Sent dashboard notification to %s, status=%s", BUSINESS_CORE_NOTIFICATION_URL, response.status)
    except urllib.error.HTTPError as http_err:
        logger.warning("Failed to send dashboard notification, HTTP %s: %s", http_err.code, http_err.reason)
        raise HTTPException(status_code=502, detail=f"Failed to send notification: {http_err.reason}")
    except Exception as exc:
        logger.warning("Failed to send dashboard notification: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to send notification")

    return payload


@app.post("/analytics/metrics", response_model=MetricsReport)
def receive_metrics(payload: MetricsReport) -> MetricsReport:
    with LOCK:
        LATEST_METRICS["report"] = payload.model_dump()
        LATEST_METRICS["receivedAt"] = now_utc()
    logger.info("Received metrics report for date=%s", payload.date)
    return payload


@app.get("/analytics/metrics/latest", response_model=Dict[str, Any])
def get_latest_metrics() -> Dict[str, Any]:
    with LOCK:
        if not LATEST_METRICS:
            return {
                "report": {
                    "date": date.today().isoformat(),
                    "avg_temperature_by_room": {},
                    "avg_humidity_by_room": {},
                    "danger_event_count": 0,
                    "warning_event_count": 0,
                    "low_battery_device_count": 0,
                    "total_access_in": 0,
                    "denied_access_count": 0,
                    "peak_access_hour": None,
                    "events_by_severity": {},
                    "events_by_area": {},
                    "events_by_source": {},
                },
                "receivedAt": now_utc(),
            }
        return LATEST_METRICS


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)
