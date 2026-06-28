import json
import logging
import os
import re
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AnyUrl, BaseModel, Field, constr, root_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Đọc biến môi trường với giá trị mặc định
SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-vision-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://localhost:8001")
RESULTS_FILE = os.getenv("RESULTS_FILE", "results.json")

app = FastAPI(
    title="FIT4110 Lab 05 - AI Vision and Core Business API",
    version=SERVICE_VERSION,
    description=(
        "Mock implementation của OpenAPI contract AI Vision / Access / Core Policy. "
        "Endpoint này được thiết kế để phù hợp với openapi.yaml và phục vụ thử nghiệm Docker Compose."
    ),
)


class Problem(BaseModel):
    type: str = Field(..., format="uri")
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: Optional[str] = None
    instance: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None


class HealthStatus(BaseModel):
    status: str
    service: str
    time: str


class ImageType(str, Enum):
    URL = "URL"
    BASE64 = "BASE64"


class Direction(str, Enum):
    IN = "IN"
    OUT = "OUT"


class AccessStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class GateState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"
    FAULT = "FAULT"


class HolderRole(str, Enum):
    STUDENT = "STUDENT"
    STAFF = "STAFF"
    GUEST = "GUEST"
    CONTRACTOR = "CONTRACTOR"


class CardStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


class BoundingBox(BaseModel):
    x: float = Field(..., ge=0.0)
    y: float = Field(..., ge=0.0)
    width: float = Field(..., ge=0.0)
    height: float = Field(..., ge=0.0)


class DetectionItem(BaseModel):
    type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    boundingBox: Optional[BoundingBox] = None


class VisionDetectRequest(BaseModel):
    requestId: UUID
    cameraId: constr(pattern=r"^CAM-[0-9]{3}$")
    capturedAt: datetime
    imageType: ImageType
    correlationId: Optional[UUID] = None
    locationId: Optional[str] = Field(default=None, min_length=1, max_length=80)
    metadata: Optional[Dict[str, Any]] = None
    imageUrl: Optional[AnyUrl] = None
    imageBase64: Optional[str] = None

    @root_validator(skip_on_failure=True)
    def validate_image_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        image_type = values.get("imageType")
        image_url = values.get("imageUrl")
        image_base64 = values.get("imageBase64")

        if image_type == ImageType.URL and not image_url:
            raise ValueError("imageUrl is required when imageType is URL")
        if image_type == ImageType.BASE64 and not image_base64:
            raise ValueError("imageBase64 is required when imageType is BASE64")
        if image_type == ImageType.BASE64 and image_base64:
            if not re.match(r"^data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+$", image_base64):
                raise ValueError("imageBase64 is not a supported data URI format")
        return values


class VisionDetectResult(BaseModel):
    requestId: UUID
    status: str
    detectedAt: datetime
    detections: List[DetectionItem]
    processingTimeMs: int = Field(..., ge=0)
    modelVersion: str = Field(..., min_length=1, max_length=80)
    notes: Optional[str] = Field(default=None, max_length=500)


class VisionDetectAsyncResponse(BaseModel):
    requestId: UUID
    status: str
    submittedAt: datetime
    estimatedDurationMs: int = Field(..., ge=0)


class ModelInfo(BaseModel):
    modelName: str
    version: str
    type: str
    status: str


class VisionDetectResultPage(BaseModel):
    items: List[VisionDetectResult]
    nextCursor: Optional[str]
    hasMore: bool


class AccessLog(BaseModel):
    logId: UUID
    cardId: constr(pattern=r"^CARD-[0-9]{6}$")
    gateId: constr(pattern=r"^GATE-[0-9]{2}$")
    direction: Direction
    timestamp: datetime
    status: AccessStatus
    note: Optional[str] = None


class AccessLogDetail(AccessLog):
    holderName: str
    holderRole: HolderRole
    readerModel: str


class AccessLogPage(BaseModel):
    items: List[AccessLog]
    nextCursor: Optional[str]
    hasMore: bool


class GateStatus(BaseModel):
    gateId: constr(pattern=r"^GATE-[0-9]{2}$")
    status: GateState
    lastActivityAt: datetime
    firmwareVersion: str


class CardDetail(BaseModel):
    cardId: constr(pattern=r"^CARD-[0-9]{6}$")
    holderName: str
    holderRole: HolderRole
    status: CardStatus
    issuedAt: datetime
    expiresAt: datetime


class AccessCheckRequest(BaseModel):
    requestId: UUID
    cardId: constr(pattern=r"^CARD-[0-9]{6}$")
    gateId: constr(pattern=r"^GATE-[0-9]{2}$")
    direction: Direction
    timestamp: datetime


class AccessCheckResponse(BaseModel):
    decisionId: UUID
    allow: bool
    reasonCode: str
    policyId: Optional[str] = None
    expiresAt: Optional[datetime] = None


class AccessPolicy(BaseModel):
    policyId: constr(pattern=r"^POL-[0-9]{3}$")
    name: str
    description: str
    department: str
    status: str


class AccessDecision(BaseModel):
    decisionId: UUID
    cardId: constr(pattern=r"^CARD-[0-9]{6}$")
    gateId: constr(pattern=r"^GATE-[0-9]{2}$")
    direction: Direction
    timestamp: datetime
    allow: bool
    reasonCode: str
    evaluatedPolicyId: Optional[str] = None
    operatorNote: Optional[str] = None


DETECTION_STORE: Dict[str, Dict[str, Any]] = {}
ACCESS_LOG_STORE: Dict[str, Dict[str, Any]] = {}


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "https://campus.local/errors/validation",
) -> Dict[str, Any]:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    problem["errors"] = []
    return problem


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        title_map = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            422: "Unprocessable Entity",
            429: "Too Many Requests",
            500: "Internal Server Error",
        }
        problem = build_problem(
            status_code=exc.status_code,
            title=title_map.get(exc.status_code, "HTTP Error"),
            detail=str(exc.detail),
            instance=str(request.url),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "code": err.get("type", "validation_error"),
            "message": err.get("msg", "Validation error"),
        }
        for err in exc.errors()
    ]
    detail = errors[0]["message"] if errors else "Request validation error"
    problem = build_problem(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Validation error",
        detail=detail,
        instance=str(request.url),
        problem_type="https://campus.local/errors/validation",
    )
    problem["errors"] = errors

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem,
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                instance="/",
                problem_type="https://campus.local/errors/unauthorized",
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                instance="/",
                problem_type="https://campus.local/errors/unauthorized",
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def make_detect_result(request_id: UUID) -> VisionDetectResult:
    return VisionDetectResult(
        requestId=request_id,
        status="SUCCESS",
        detectedAt=now_utc(),
        detections=[
            DetectionItem(
                type="UNKNOWN_PERSON",
                confidence=0.94,
                boundingBox=BoundingBox(x=120.5, y=85.0, width=45.2, height=110.8),
            )
        ],
        processingTimeMs=245,
        modelVersion="yolov8x-face-v2.1",
        notes="Phát hiện đối tượng chưa đăng ký trong khu vực.",
    )


def make_async_response(request_id: UUID) -> VisionDetectAsyncResponse:
    return VisionDetectAsyncResponse(
        requestId=request_id,
        status="PROCESSING",
        submittedAt=now_utc(),
        estimatedDurationMs=1500,
    )


def make_access_log(log_id: UUID) -> AccessLog:
    return AccessLog(
        logId=log_id,
        cardId="CARD-123456",
        gateId="GATE-01",
        direction=Direction.IN,
        timestamp=now_utc(),
        status=AccessStatus.ALLOWED,
        note="Quẹt thẻ bình thường.",
    )


def make_access_log_detail(log_id: UUID) -> AccessLogDetail:
    base = make_access_log(log_id)
    return AccessLogDetail(
        **base.model_dump(),
        holderName="Nguyễn Văn Hưởng",
        holderRole=HolderRole.STUDENT,
        readerModel="RFID-RDR-V3.2",
    )


def make_policy(policy_id: str) -> AccessPolicy:
    return AccessPolicy(
        policyId=policy_id,
        name="Chính sách ra vào sinh viên chính quy CNTT",
        description="Cho phép sinh viên khoa CNTT ra vào cổng chính từ 07:00 đến 22:00 hàng ngày.",
        department="IT",
        status="ACTIVE",
    )


def make_decision(decision_id: UUID) -> AccessDecision:
    return AccessDecision(
        decisionId=decision_id,
        cardId="CARD-123456",
        gateId="GATE-01",
        direction=Direction.IN,
        timestamp=now_utc(),
        allow=True,
        reasonCode="ALLOWED",
        evaluatedPolicyId="POL-101",
        operatorNote=None,
    )


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        service=SERVICE_NAME,
        time=now_utc().isoformat(timespec="seconds"),
    )


@app.post(
    "/vision/detect",
    responses={
        201: {"model": VisionDetectResult},
        202: {"model": VisionDetectAsyncResponse},
        400: {"model": Problem},
        401: {"model": Problem},
        403: {"model": Problem},
        409: {"model": Problem},
        422: {"model": Problem},
        500: {"model": Problem},
    },
    dependencies=[Depends(verify_bearer_token)],
)
def submit_vision_detect(payload: VisionDetectRequest, response: Response) -> Union[VisionDetectResult, VisionDetectAsyncResponse]:
    request_id = payload.requestId

    if payload.imageType == ImageType.BASE64:
        DETECTION_STORE[str(request_id)] = {
            "status": "PROCESSING",
            "submittedAt": now_utc(),
            "payload": payload.model_dump(),
        }
        response.headers["Location"] = f"/vision/detect/{request_id}"
        response.status_code = status.HTTP_202_ACCEPTED
        return make_async_response(request_id)

    result = make_detect_result(request_id)
    DETECTION_STORE[str(request_id)] = {"status": "SUCCESS", "result": result.model_dump()}
    response.status_code = status.HTTP_201_CREATED
    return result


@app.get(
    "/vision/detect/{request_id}",
    responses={
        200: {"model": VisionDetectResult},
        202: {"model": VisionDetectAsyncResponse},
        401: {"model": Problem},
        403: {"model": Problem},
        404: {"model": Problem},
        500: {"model": Problem},
    },
    dependencies=[Depends(verify_bearer_token)],
)
def get_vision_detect_result(request_id: UUID) -> Union[VisionDetectResult, VisionDetectAsyncResponse]:
    record = DETECTION_STORE.get(str(request_id))
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail="Yêu cầu phân tích không tồn tại",
                instance=f"/vision/detect/{request_id}",
                problem_type="https://campus.local/errors/not-found",
            ),
        )

    if record.get("status") == "PROCESSING":
        return make_async_response(request_id)

    return VisionDetectResult(**record["result"])


@app.get(
    "/vision/results/recent",
    response_model=VisionDetectResultPage,
    dependencies=[Depends(verify_bearer_token)],
)
def get_recent_results(
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> VisionDetectResultPage:
    items = [make_detect_result(uuid.uuid4()) for _ in range(min(limit, 5))]
    return VisionDetectResultPage(items=items, nextCursor=None, hasMore=False)


@app.get(
    "/vision/detections",
    response_model=VisionDetectResultPage,
    dependencies=[Depends(verify_bearer_token)],
)
def list_detections_history(
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> VisionDetectResultPage:
    items = [make_detect_result(uuid.uuid4()) for _ in range(min(limit, 5))]
    return VisionDetectResultPage(items=items, nextCursor=None, hasMore=False)


@app.get(
    "/vision/models",
    response_model=Dict[str, List[ModelInfo]],
    dependencies=[Depends(verify_bearer_token)],
)
def list_vision_models() -> Dict[str, List[ModelInfo]]:
    return {
        "models": [
            ModelInfo(modelName="yolov8x-face", version="v2.1", type="FACE_MATCH", status="ACTIVE"),
            ModelInfo(modelName="yolov8-license-plate", version="v1.4", type="LICENSE_PLATE", status="ACTIVE"),
        ]
    }


@app.post(
    "/vision/face-match",
    response_model=VisionDetectResult,
    dependencies=[Depends(verify_bearer_token)],
)
def face_match_legacy(response: Response) -> VisionDetectResult:
    response.headers["Sunset"] = "Thu, 31 Dec 2026 23:59:59 GMT"
    return make_detect_result(uuid.uuid4())


@app.get(
    "/access/logs/recent",
    response_model=AccessLogPage,
    dependencies=[Depends(verify_bearer_token)],
)
def get_access_logs_recent(
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> AccessLogPage:
    items = [make_access_log(uuid.uuid4()) for _ in range(min(limit, 5))]
    for item in items:
        ACCESS_LOG_STORE[str(item.logId)] = item.model_dump()
    return AccessLogPage(items=items, nextCursor=None, hasMore=False)


@app.get(
    "/access/logs/{log_id}",
    response_model=AccessLogDetail,
    dependencies=[Depends(verify_bearer_token)],
)
def get_access_log_by_id(log_id: UUID) -> AccessLogDetail:
    stored = ACCESS_LOG_STORE.get(str(log_id))
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail="Access log không tồn tại",
                instance=f"/access/logs/{log_id}",
                problem_type="https://campus.local/errors/not-found",
            ),
        )

    base_log = AccessLog(**stored)
    return AccessLogDetail(
        **base_log.model_dump(),
        holderName="Nguyễn Văn Hưởng",
        holderRole=HolderRole.STUDENT,
        readerModel="RFID-RDR-V3.2",
    )


@app.get(
    "/gates/{gate_id}/status",
    response_model=GateStatus,
    dependencies=[Depends(verify_bearer_token)],
)
def get_gate_status(gate_id: str) -> GateStatus:
    return GateStatus(
        gateId=gate_id,
        status=GateState.CLOSED,
        lastActivityAt=now_utc(),
        firmwareVersion="gate-fw-v1.4.2",
    )


@app.get(
    "/cards/{card_id}",
    response_model=CardDetail,
    dependencies=[Depends(verify_bearer_token)],
)
def get_card_detail(card_id: str) -> CardDetail:
    return CardDetail(
        cardId=card_id,
        holderName="Nguyễn Văn Hưởng",
        holderRole=HolderRole.STUDENT,
        status=CardStatus.ACTIVE,
        issuedAt=now_utc() - timedelta(days=365),
        expiresAt=now_utc() + timedelta(days=365),
    )


@app.post(
    "/access/check",
    response_model=AccessCheckResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def check_access_policy(payload: AccessCheckRequest) -> AccessCheckResponse:
    return AccessCheckResponse(
        decisionId=uuid.uuid4(),
        allow=True,
        reasonCode="ALLOWED",
        policyId="POL-101",
        expiresAt=now_utc() + timedelta(seconds=5),
    )


@app.get(
    "/policies/access/{policy_id}",
    response_model=AccessPolicy,
    dependencies=[Depends(verify_bearer_token)],
)
def get_access_policy_by_id(policy_id: str) -> AccessPolicy:
    return make_policy(policy_id)


@app.get(
    "/decisions/{decision_id}",
    response_model=AccessDecision,
    dependencies=[Depends(verify_bearer_token)],
)
def get_decision_by_id(decision_id: UUID) -> AccessDecision:
    return make_decision(decision_id)


def save_result_to_file(payload: VisionDetectResult, push_status: Dict[str, Any]) -> None:
    record = payload.model_dump(mode="json")
    record["savedAt"] = now_utc().isoformat()
    record["corePush"] = push_status
    try:
        existing = []
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []
        existing.append(record)
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        logger.info("Saved detection result %s, core push success=%s", payload.requestId, push_status.get("success"))
    except Exception:
        logger.exception("Failed to save detection result %s", payload.requestId)


def push_to_core_service(payload: VisionDetectResult) -> Dict[str, Any]:
    data = json.dumps(payload.model_dump(mode="json")).encode("utf-8")
    req = urllib.request.Request(
        CORE_SERVICE_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            success = 200 <= resp.status < 300
            logger.info(
                "Core push for %s returned %s %s",
                payload.requestId,
                resp.status,
                response_body[:200],
            )
            return {
                "attempted": True,
                "success": success,
                "statusCode": resp.status,
                "responseBody": response_body,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else None
        logger.error(
            "Core push for %s failed HTTP %s: %s",
            payload.requestId,
            exc.code,
            response_body,
        )
        return {
            "attempted": True,
            "success": False,
            "statusCode": exc.code,
            "responseBody": response_body,
            "error": str(exc),
        }
    except urllib.error.URLError as exc:
        logger.error("Core push for %s failed URLError: %s", payload.requestId, exc)
        return {
            "attempted": True,
            "success": False,
            "statusCode": None,
            "responseBody": None,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Core push for %s failed unexpectedly", payload.requestId)
        return {
            "attempted": True,
            "success": False,
            "statusCode": None,
            "responseBody": None,
            "error": str(exc),
        }


@app.post("/webhooks/onDetectionCompleted")
def on_detection_completed(payload: VisionDetectResult) -> Response:
    DETECTION_STORE[str(payload.requestId)] = {"status": "SUCCESS", "result": payload.model_dump()}
    push_status = push_to_core_service(payload)
    save_result_to_file(payload, push_status)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
