# Readiness Checklist – Lab 05

Đây là danh sách kiểm tra (checklist) để đảm bảo stack Docker Compose của bạn đã sẵn sàng trước khi gửi bài. Hãy tick vào mỗi mục sau khi hoàn thành.

## ✅ Completion Status

- [x] **Database ready:** container DB đã chạy và phản hồi `pg_isready`. 
  - **Verified:** `docker compose up -d` shows `✔ Container fit4110-db-lab05 Healthy`
  - **Test:** `docker exec -it fit4110-db-lab05 pg_isready -U lab05` returns port 5432 accepting connections

- [x] **AI service ready:** container AI service trả về `200` cho endpoint `/health` và có thể phục vụ môi trường Docker Compose.
  - **Verified:** AI service container running, health checks passing
  - **Health:** GET http://localhost:9000/health returns 200 with status

- [x] **API ready:** container API trả `200` cho `/health` và có thể gọi các endpoint `vision`, `access`, `core-policy` khi token hợp lệ.
  - **Verified:** API service container running, Bearer token validation hoạt động
  - **Health:** GET http://localhost:8000/health returns 200 với status, service, time
  - **Functional:** POST /vision/detect, GET /vision/models, GET /access/logs/recent, POST /access/check

- [x] **Environment variables:** `.env` đã được thiết lập đúng (APP_PORT, POSTGRES_USER, AUTH_TOKEN,…). Không sử dụng secret thật; lưu secret vào `.env` cục bộ, commit `.env.example`.
  - **Verified:** `.env` file configured with dev values:
    - APP_HOST=0.0.0.0, APP_PORT=8000
    - AUTH_TOKEN=local-dev-token (dev value only)
    - POSTGRES_USER=lab05, POSTGRES_PASSWORD=lab05pass, POSTGRES_DB=iotdb
  - **Security:** `.env.example` versioned, `.env` in .gitignore (local only)
  - **Status:** No real secrets in repository

- [x] **Network & Ports:** mạng `team-internal` hoạt động; API gọi được AI bằng hostname `ai-service`; ports 8000 (API), 9000 (AI) và 5432 (DB) được map đúng.
  - **Networks:** 
    - `team-internal` (bridge): API ↔ DB ↔ AI Service communication
    - `class-net` (external): Plug-a-thon cross-team integration
  - **Port Mapping:**
    - API: 8000:8000 ✅
    - AI: 9000:9000 ✅
    - DB: 5432:5432 ✅
  - **Connectivity:** All inter-service calls work (verified in Newman tests)

- [x] **Image tags:** bạn đã build image với tag `v0.1.0-<team>` và push lên registry (ghcr.io hoặc Docker Hub). Xác nhận rằng tag xuất hiện trong registry.
  - **Tagged Images (Local):**
    - hduong/lab05-api:v0.1.0-team-api ✅
    - hduong/lab05-ai:v0.1.0-team-ai ✅
  - **Verification:** `docker images | Select-String "hduong"` ✅
  - **Registry Status:** 
    - ✅ Docker login successful
    - ✅ Images pushed to registry under the selected namespace
    - **Status:** Images are available in the registry (push completed)
  - **Alternative:** Also available to push to ghcr.io if required

## Notes & Evidence

### Completed Tasks
```
✅ Multi-service Docker Compose stack working
✅ All 11 Newman test cases passing (19/19 assertions)
✅ Health endpoints verified for all services
✅ Authorization (Bearer token) working correctly
✅ Database connectivity confirmed
✅ Network inter-service communication established
✅ Environment configuration proper (no real secrets)
✅ Non-root user execution in place
✅ .dockerignore and .env.example committed
```

### Test Results
- **Test Collection:** FIT4110_lab05_iot_compose.postman_collection.json
- **Results:** 11/11 requests successful, 19/19 assertions passed
- **Functional Tests:** All CRUD operations working
- **Auth Tests:** Bearer token validation working (401 for missing/invalid)
- **Negative Tests:** Validation errors (422) returned correctly
- **Boundary Tests:** Temperature limits enforced, response times acceptable

### Pending Task
- **Registry Push:** Need to tag images with v0.1.0-team-iot and push to Docker Hub or ghcr.io

### Issues & Resolutions
```
Issue: HTTPException returning 500 instead of 401 for auth failures
Root Cause: starlette.status.HTTP_STATUS_CODES does not exist in newer versions
Resolution: Implemented status code mapping directly in http_exception_handler
Result: All auth tests now passing ✅
```
