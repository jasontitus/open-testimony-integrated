# Open Testimony

A secure, self-hosted platform for recording, verifying, and searching video testimony. Mobile apps capture video with hardware-backed cryptographic signatures (ECDSA P-256 via Secure Enclave / StrongBox), GPS coordinates, and timestamps. Uploaded videos are integrity-verified on the server, stored in MinIO, and indexed by an AI bridge service that makes every frame and spoken word searchable via OpenCLIP or PE-Core vision models and Whisper transcription.

## Architecture

```
                          +-------------------+
                          |    Mobile App     |
                          |  (Flutter/Dart)   |
                          +--------+----------+
                                   |
                                   v
+------------------------------------------------------------------+
|  Docker Compose Stack           :18080                           |
|                                                                  |
|  +----------+    +----------+    +---------+    +-----------+    |
|  |  nginx   |--->| api      |--->|   db    |    |   minio   |    |
|  |  :80     |    | (FastAPI)|    | pgvector|<---|  (S3)     |    |
|  +----+-----+    +----+-----+    +----+----+    +-----------+    |
|       |               |              ^                           |
|       |          webhook fires       |                           |
|       |               |              |                           |
|       |          +----v-----+        |                           |
|       +--------->|  bridge  |--------+                           |
|       |          | (AI/ML)  |                                    |
|       |          +----------+                                    |
|       |                                                          |
|       |          +----------+                                    |
|       +--------->|  web-ui  |                                    |
|                  | (React)  |                                    |
|                  +----------+                                    |
+------------------------------------------------------------------+
```

**6 services:**
- **nginx** -- reverse proxy, TLS termination, routes `/api/` to api, `/ai-search/` to bridge, `/` to web-ui, `/video-stream/` to minio
- **api** -- FastAPI backend: video upload, device registration, ECDSA verification, user auth, audit log
- **db** -- PostgreSQL 16 + pgvector: metadata, users, audit chain, frame/transcript embeddings
- **minio** -- S3-compatible object storage for video files
- **bridge** -- AI search service: OpenCLIP/PE-Core vision encoding, Whisper transcription, pgvector similarity search
- **web-ui** -- React SPA: map view, video list, AI search (text-to-video, image-to-video, transcript search)

## Quick Start

### Prerequisites

- Docker and Docker Compose v2+

### 1. Start the stack

```bash
cd open-testimony-app
docker compose up -d
```

### 2. Run database migrations

```bash
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/001_add_annotations.sql
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/002_add_audit_log.sql
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/003_add_users.sql
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/004_add_search_indexes.sql
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/005_add_pgvector.sql
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/006_add_tags_table.sql
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/007_upgrade_frame_embedding_dim.sql
```

Or use the Makefile shorthand:

```bash
make migrate
```

### 3. Access the web UI

Open http://localhost:18080 and log in with **admin / admin**.

The admin account is seeded on first startup from the `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables in `docker-compose.yml`.

## Mobile App

The Flutter app lives in `open-testimony-app/mobile-app/`.

```bash
cd open-testimony-app/mobile-app
flutter pub get
flutter run
```

The app includes a **server selector dropdown** in Settings -- pick a preset server or enter a custom URL (e.g., `http://192.168.1.100:18080/api`). No need to edit source code to switch servers.

Features: live recording with GPS + ECDSA signing, gallery import with EXIF extraction, upload with retry/progress, annotations, audit trail.

## AI Search

The bridge service indexes every uploaded video automatically:

1. **Visual indexing** -- extracts frames at a configurable interval (default 2s), encodes each frame with the vision model, stores 1280-dim embeddings in pgvector
2. **Transcript indexing** -- transcribes audio with Whisper, encodes segments with Qwen3-Embedding-8B, stores 4096-dim embeddings in pgvector

Search modes available in the web UI's AI Search tab:
- **Visual (Text)** -- describe what you're looking for ("person holding a sign")
- **Visual (Image)** -- upload a reference image to find similar frames
- **Transcript (Semantic)** -- find segments by meaning, not exact words
- **Transcript (Exact)** -- case-insensitive substring search on transcribed text

### Upgrading from ViT-L-14 (768-dim)

If you previously ran with the ViT-L-14 model (768-dim embeddings), follow these steps:

1. **Run the dimension migration** to widen the `frame_embeddings` column from `vector(768)` to `vector(1280)`:

```bash
cd open-testimony-app
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/007_upgrade_frame_embedding_dim.sql
```

2. **Rebuild the bridge** to load the new ViT-bigG-14 model:

```bash
docker compose up -d --build bridge
```

3. **Re-index all videos** (old 768-dim embeddings are incompatible with 1280-dim queries):

```bash
curl -X POST http://localhost:18080/ai-search/indexing/reindex-all \
  -H "Cookie: <your-jwt-cookie>"
```

### Switching vision models

The default is OpenCLIP ViT-bigG-14. To use PE-Core instead, update the bridge environment in `docker-compose.yml`:

```yaml
- VISION_MODEL_FAMILY=pe_core
- VISION_MODEL_NAME=PE-Core-L14-336
- VISION_EMBEDDING_DIM=768
```

Then rebuild the bridge: `docker compose up -d --build bridge`

If switching model families, re-index existing videos (embeddings are model-specific):

```bash
curl -X POST http://localhost:18080/ai-search/indexing/reindex-all \
  -H "Cookie: <your-jwt-cookie>"
```

### Triggering indexing manually

Indexing happens automatically on upload. To re-index a single video:

```bash
curl -X POST http://localhost:18080/ai-search/indexing/reindex/<video-id> \
  -H "Cookie: <your-jwt-cookie>"
```

## Configuration

Key environment variables (set in `open-testimony-app/docker-compose.yml`):

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `MINIO_EXTERNAL_ENDPOINT` | api | `localhost:18080/video-stream` | Public URL base for presigned video URLs |
| `MINIO_EXTERNAL_SCHEME` | api | `http` | `https` for production |
| `ADMIN_USERNAME` | api | `admin` | Initial admin login |
| `ADMIN_PASSWORD` | api | `admin` | Initial admin password |
| `JWT_SECRET_KEY` | api, bridge | `change-me-in-production...` | Shared JWT signing key |
| `VISION_MODEL_FAMILY` | bridge | `open_clip` | `open_clip` or `pe_core` |
| `VISION_MODEL_NAME` | bridge | `ViT-bigG-14` | Model name within family |
| `VISION_MODEL_PRETRAINED` | bridge | `laion2b_s39b_b160k` | OpenCLIP pretrained weights |
| `VISION_EMBEDDING_DIM` | bridge | `1280` | Must match model output dim |
| `WHISPER_MODEL` | bridge | `large-v3` | Whisper model size |
| `DEVICE` | bridge | `cpu` | `cpu` or `cuda` |
| `FRAME_INTERVAL_SEC` | bridge | `2.0` | Seconds between extracted frames |

## Project Structure

```
open-testimony-app/
  api-server/           FastAPI backend (upload, auth, audit, devices)
    migrations/         SQL migrations (001-007)
    tests/              API integration tests
  bridge/               AI search bridge service
    indexing/           Frame extraction, encoding, Whisper transcription
    search/             Visual + transcript search endpoints
    tests/              Bridge unit tests
  mobile-app/           Flutter app (iOS + Android)
    lib/                Dart source
    ios/                Xcode project
    android/            Android project
  nginx/                Reverse proxy config + certs
  web-ui/               React SPA (map, list, AI search, admin)
    src/
  scripts/              Utility scripts
  tests/                End-to-end API tests
  docker-compose.yml    Full stack definition (6 services)
  Makefile              Dev commands (make up/down/test/migrate/reset)
```

## Development

### Run API integration tests

Requires the Docker stack to be running:

```bash
cd open-testimony-app
make test-api
```

### Run bridge unit tests

```bash
cd open-testimony-app/bridge
pip install -r tests/requirements.txt
python -m pytest tests/ -v
```

### Rebuild a single service

```bash
cd open-testimony-app
docker compose up -d --build bridge   # or api, web-ui
docker compose restart nginx          # pick up upstream changes
```

### Reset everything

```bash
cd open-testimony-app
make reset   # destroys all data, rebuilds, re-migrates
```

## License

MIT -- see [LICENSE](LICENSE).
