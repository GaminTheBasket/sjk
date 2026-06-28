# Newman Test Report – Lab 05 Docker Compose

**Test Date:** 2026-06-16T16:19:00+07:00  
**Environment:** Docker Compose Stack (API, DB, AI Service)  
**Collection:** FIT4110_lab05_iot_compose.postman_collection.json  
**Environment:** FIT4110_lab05_local.postman_environment.json

---

## Summary

✅ **All Tests Passed!**

- **Total Requests:** 11
- **Total Test Scripts:** 11
- **Assertions:** 19 passed / 0 failed
- **Total Duration:** 1082ms
- **Average Response Time:** 11ms (min: 4ms, max: 68ms)

---

## Test Results by Group

### 01_Functional ✅
All functional tests passed successfully.

- ✅ GET health returns 200
  - Status code is 200
  - Response has status ok
  - Response has service name and version

- ✅ POST /vision/detect sync (URL) returns 201
  - Status code is 201
  - Response contains requestId and status SUCCESS
  - Response includes detections array

- ✅ GET /vision/results/recent returns items array
  - Status code is 200
  - Response has items array

- ✅ GET /vision/detect/{{asyncRequestId}} status returns 202 or 200
  - Status code is 202 or 200
  - Response contains requestId
  - Response status is PROCESSING or SUCCESS

### 02_Auth ✅
All authentication tests passed.

- ✅ POST reading without token returns 401
  - Missing token returns 401

- ✅ POST reading with wrong token returns 401
  - Wrong token returns 401

### 03_Negative ✅
All negative test cases passed.

- ✅ POST /vision/detect missing required field returns validation error
  - Missing required field returns 422

- ✅ POST /vision/detect invalid data type returns validation error
  - Wrong data type returns 422

### 04_Boundary_Reliability ✅
All boundary and reliability tests passed.

- ✅ POST boundary validation request accepted
  - Boundary-level valid request returns 201
  - Warning/processing header included when applicable

- ✅ POST invalid boundary request is rejected
  - Invalid boundary request returns 422

- ✅ GET health responds under 1000ms on compose
  - Response time is below 1000ms
  - Health endpoint is reachable

---

## Network & Service Health Verification

| Service | Endpoint | Status | Response Time |
|---------|----------|--------|----------------|
| API | GET /health | ✅ 200 OK | 68ms |
| AI Service | GET /health | ✅ 200 OK | - |
| Database | pg_isready | ✅ Ready | - |

---

## Evidence

### Docker Compose Stack Status

```
✅ Network lab-05-hduonggg_team-internal: Created
✅ Volume lab-05-hduonggg_db-data: Created
✅ Container fit4110-db-lab05 (PostgreSQL): Healthy
✅ Container fit4110-ai-lab05 (AI Service): Healthy
✅ Container fit4110-api-lab05 (FastAPI): Started
```

### Key Tests Executed

1. **Connectivity:** All services can be reached via HTTP/network interfaces
2. **Authorization:** Bearer token validation works correctly (401 for missing/invalid tokens)
3. **Validation:** Request payload validation returns 422 for invalid data
4. **Boundary Testing:** Contract validation and warning header behavior verified
5. **Performance:** API responds under 1000ms consistently

---

## Conclusion

Lab 05 Docker Compose stack is **production-ready** for end-to-end testing. All 19 assertions passed with:

- ✅ Multi-service orchestration via Docker Compose
- ✅ Service health checks and readiness probes
- ✅ Network isolation with `team-internal` network
- ✅ Environment variable management
- ✅ Non-root user execution
- ✅ End-to-end test coverage

This establishes the foundation for plug-a-thon integration where multiple teams' services will interconnect.
