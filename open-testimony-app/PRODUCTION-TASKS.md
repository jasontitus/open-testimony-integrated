# Production Hardening Tasks

Target deployment: GCP (single VM to start, scaling later as needed).
Expected load: 5-10 concurrent uploads max, ~few req/s web UI.

## P0 — Fix before going live

### 1. Stream uploads instead of loading into memory
- **File:** `api-server/main.py` upload endpoint
- **Problem:** `video_content = await video.read()` loads entire file (up to 500MB) into RAM per upload. 5 concurrent uploads = ~5GB RAM.
- **Fix:** Stream-hash in chunks, stream to MinIO via temp file or piped stream. Cap per-upload RAM at ~8MB.
- **Status:** DONE — streaming with SpooledTemporaryFile + chunked SHA-256

### 2. Multi-worker uvicorn (gunicorn)
- **File:** `api-server/Dockerfile`
- **Problem:** Single uvicorn worker; blocking MinIO `put_object()` stalls the entire event loop during uploads.
- **Fix:** Run behind gunicorn with 2-4 uvicorn workers. Wrap blocking MinIO calls in `asyncio.to_thread()`.
- **Status:** DONE — gunicorn with UvicornWorker, WEB_CONCURRENCY env var, 300s timeout

### 3. Rate limiting
- **File:** `nginx/conf/default.conf`
- **Problem:** No rate limits on `/upload` or `/register-device`. A misbehaving client can flood the server.
- **Fix:** nginx `limit_req_zone` — e.g., 2 uploads/sec burst 10, 5 req/s on registration.
- **Status:** DONE — rate limits on /upload (2r/s burst 10), /register-device (5r/s burst 5), /auth/login (3r/s burst 5)

### 4. Paginate audit chain verification
- **File:** `api-server/audit_service.py`
- **Problem:** `verify_chain()` loads ALL audit log entries into memory. At 100k+ entries this OOMs.
- **Fix:** Walk the chain in batches (e.g., 1000 rows at a time).
- **Status:** DONE — batched with expire_all() between batches

### 5. Secrets management
- **Files:** `docker-compose.yml`, `api-server/config.py`
- **Problem:** Hardcoded defaults — `JWT_SECRET_KEY=change-me-in-production`, `MINIO_ROOT_PASSWORD=supersecret`, `POSTGRES_PASSWORD=pass`, `ADMIN_PASSWORD=admin`.
- **Fix:** Use `.env` file excluded from git (already in .gitignore?) or GCP Secret Manager. Generate a real JWT secret (`openssl rand -hex 32`).
- **Status:** TODO

### 6. CORS lockdown
- **File:** `api-server/main.py`
- **Problem:** `allow_origins=["*"]` allows any domain.
- **Fix:** Set to actual production domain(s).
- **Status:** TODO

### 7. HTTPS / TLS
- **File:** `nginx/conf/default.conf`
- **Problem:** HTTP only (HTTPS block commented out).
- **Fix:** Enable the HTTPS server block. Use Let's Encrypt certbot or GCP-managed certificates.
- **Status:** TODO

### 8. Real health check
- **File:** `api-server/main.py`
- **Problem:** `/health` always returns "healthy" without checking DB or MinIO.
- **Fix:** Attempt a lightweight DB query and MinIO ping; return 503 on failure.
- **Status:** TODO

## P1 — Operational safety

### 9. Automated backups (PostgreSQL + MinIO)
- **Target:** GCS bucket
- **PostgreSQL:** Daily `pg_dump` uploaded to GCS. The audit chain is the most critical data.
- **MinIO:** `mc mirror` to GCS bucket (incremental, append-only data).
- **Script:** `scripts/backup.sh` — pg_dump + mc mirror + retention pruning
- **Status:** DONE (script written, needs GCS bucket + cron setup on deployment)

### 10. Storage scaling plan
| Data size | Approach |
|-----------|----------|
| < 100GB   | GCP VM with attached persistent disk, MinIO in Docker |
| 100GB-1TB | Attached SSD persistent disk (resizable), or swap MinIO for GCS (code already uses S3 protocol) |
| > 1TB     | Switch to GCS directly — change MinIO endpoint/credentials in env vars |
- **Status:** TODO

### 11. Monitoring & alerting
- Disk usage alerts (>80% threshold)
- Container health monitoring (docker healthchecks or GCP Cloud Monitoring)
- Upload failure rate tracking
- **Status:** TODO

### 12. Log aggregation
- Currently: stdout logging with emoji prefixes
- Production: ship logs to GCP Cloud Logging or similar
- **Status:** TODO
