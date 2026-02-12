# Open Testimony

A secure, self-hosted platform for recording, verifying, and searching video testimony. Mobile apps capture video with hardware-backed cryptographic signatures (ECDSA P-256 via Secure Enclave / StrongBox), GPS coordinates, and timestamps. Uploaded videos are integrity-verified on the server, stored in MinIO, and indexed by an AI bridge service that makes every frame, spoken word, and action searchable via SigLIP2, OpenCLIP, or PE-Core vision models, Whisper transcription, and Gemini-powered frame/action captioning.

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
- **bridge** -- AI search service: SigLIP2/OpenCLIP/PE-Core vision encoding, Whisper transcription, Gemini captioning, temporal clip analysis, pgvector similarity search
- **web-ui** -- React SPA: map view, video list, AI search (visual, caption, transcript, clip, action), review queue, admin dashboard

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
docker compose exec db psql -U user -d opentestimony \
  -f /dev/stdin < api-server/migrations/008_add_clip_embeddings.sql
```

Or use the Makefile shorthand:

```bash
make migrate
```

> **Note:** All migrations are idempotent and safe to re-run.

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

1. **Visual indexing** -- extracts frames at a configurable interval (default 2s), encodes each frame with the vision model (SigLIP2/OpenCLIP/PE-Core), stores embeddings in pgvector
2. **Transcript indexing** -- transcribes audio with Whisper, encodes segments with Qwen3-Embedding-8B, stores 4096-dim embeddings in pgvector
3. **Caption indexing** -- generates natural-language descriptions of each frame via Gemini API (or local Qwen3-VL), encodes captions with Qwen3-Embedding-8B
4. **Clip indexing** -- extracts overlapping temporal windows (16 frames @ 4fps, 50% overlap), mean-pools frame embeddings per window for motion/action search
5. **Action captioning** (optional) -- sends multi-frame sequences to Gemini for temporal action descriptions ("person pushing another person"), encodes action text for semantic search

Search modes available in the web UI's AI Search tab:
- **Visual (Text)** -- describe what you're looking for ("person holding a sign")
- **Visual (Image)** -- upload a reference image to find similar frames
- **Transcript (Semantic)** -- find segments by meaning, not exact words
- **Transcript (Exact)** -- case-insensitive substring search on transcribed text
- **Caption (Semantic)** -- search AI-generated frame descriptions by meaning
- **Caption (Exact)** -- keyword search on frame description text
- **Clip (Visual)** -- search temporal video windows by visual similarity
- **Action** -- search for specific actions/motions across time ("use of force", "chokehold")

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

Three vision model families are supported. Update the bridge environment in `docker-compose.yml`:

**HuggingFace SigLIP2** (code default):
```yaml
- VISION_MODEL_FAMILY=hf_siglip
- VISION_MODEL_NAME=google/siglip2-so400m-patch16-naflex
- VISION_EMBEDDING_DIM=1152
```

**OpenCLIP ViT-bigG-14**:
```yaml
- VISION_MODEL_FAMILY=open_clip
- VISION_MODEL_NAME=ViT-bigG-14
- VISION_MODEL_PRETRAINED=laion2b_s39b_b160k
- VISION_EMBEDDING_DIM=1280
```

**PE-Core** (currently set in docker-compose.yml):
```yaml
- VISION_MODEL_FAMILY=pe_core
- VISION_MODEL_NAME=PE-Core-L14-336
- VISION_EMBEDDING_DIM=1024
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

To re-index only the visual embeddings (e.g., after switching vision models):

```bash
curl -X POST http://localhost:18080/ai-search/indexing/reindex-visual/<video-id> \
  -H "Cookie: <your-jwt-cookie>"

# Or re-index visual for all videos:
curl -X POST http://localhost:18080/ai-search/indexing/reindex-visual-all \
  -H "Cookie: <your-jwt-cookie>"
```

## Queue Management

The web UI includes a review queue for triaging newly uploaded videos:

- **Queue panel** -- staff/admin review uploads with status filters (pending / reviewed / flagged)
- **Inline video player** -- watch videos and edit annotations (category, location, notes) without leaving the queue
- **Keyboard shortcuts** -- arrow keys to navigate, number keys to set review status
- **Auto-advance** -- moves to next pending video after marking one as reviewed
- **Queue stats** -- `GET /queue/stats` returns counts by status

## Access Logging

Every HTTP request to the API is logged to `/app/logs/access.jsonl` with timestamp, client IP, method, path, query, status code, duration, and user agent.

A scan script is included to analyze access logs for non-LAN IP addresses:

```bash
python3 scripts/scan-access-log.py
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
| `BRIDGE_URL` | api | `http://bridge:8003` | Bridge service URL for indexing webhook |
| `GEOCODE_COUNTRY_CODES` | api | `us` | Restrict geocode autocomplete (ISO 3166-1 codes) |
| `VISION_MODEL_FAMILY` | bridge | `hf_siglip` | `hf_siglip`, `open_clip`, or `pe_core` |
| `VISION_MODEL_NAME` | bridge | `google/siglip2-so400m-patch16-naflex` | Model name within family |
| `VISION_MODEL_PRETRAINED` | bridge | `webli` | OpenCLIP pretrained weights (OpenCLIP only) |
| `VISION_EMBEDDING_DIM` | bridge | `1152` | Must match model output dim |
| `TRANSCRIPT_MODEL_NAME` | bridge | `Qwen/Qwen3-Embedding-8B` | Text embedding model |
| `TRANSCRIPT_EMBEDDING_DIM` | bridge | `4096` | Text embedding dimension |
| `WHISPER_MODEL` | bridge | `large-v3` | Whisper model size |
| `CAPTION_PROVIDER` | bridge | `gemini` | `gemini` for Gemini API, `local` for Qwen3-VL |
| `CAPTION_ENABLED` | bridge | `true` | Enable frame captioning during indexing |
| `CAPTION_MODEL_NAME` | bridge | `gemini-3-flash-preview` | Gemini model for captioning |
| `GEMINI_API_KEY` | bridge | _(empty)_ | Gemini API key (required if caption provider is gemini) |
| `CLIP_ENABLED` | bridge | `true` | Enable temporal clip indexing |
| `CLIP_WINDOW_FRAMES` | bridge | `16` | Frames per clip window |
| `CLIP_WINDOW_STRIDE` | bridge | `8` | Frames to slide between windows (overlap = window - stride) |
| `CLIP_FPS` | bridge | `4.0` | FPS for clip frame extraction |
| `CLIP_ACTION_CAPTIONING` | bridge | `false` | Enable Gemini action captioning on clips (expensive) |
| `DEVICE` | bridge | `cpu` | `cpu` or `cuda` |
| `USE_FP16` | bridge | `false` | Use half-precision inference |
| `FRAME_INTERVAL_SEC` | bridge | `2.0` | Seconds between extracted frames |
| `BATCH_SIZE` | bridge | `16` | Batch size for vision model encoding |
| `WORKER_POLL_INTERVAL` | bridge | `10` | Seconds between worker polling for new jobs |

## Project Structure

```
open-testimony-app/
  api-server/           FastAPI backend (upload, auth, audit, devices, queue, tags)
    migrations/         SQL migrations (001-008)
    tests/              API integration tests
  bridge/               AI search bridge service
    indexing/           Frame extraction, encoding, Whisper transcription, captioning
      pipeline.py       Main indexing pipeline (frames, transcripts, clips)
      worker.py         Background async job worker
      captioning.py     Frame description generation (Gemini / local)
      action_captioning.py  Temporal action detection via Gemini
    search/             Search endpoints (8 modes)
      router.py         FastAPI search router
      visual.py         Vision model frame search
      transcript.py     Transcript search
      caption.py        Caption search (semantic + exact)
      clip.py           Temporal clip + action search
    tests/              Bridge unit tests
  mobile-app/           Flutter app (iOS + Android)
    lib/                Dart source
    ios/                Xcode project (Secure Enclave ECDSA)
    android/            Android project (StrongBox ECDSA)
  nginx/                Reverse proxy config + certs
  web-ui/               React SPA (map, list, AI search, queue, admin)
    src/components/     24 React components
  scripts/              Utility scripts (backup, reindex, access log scan)
  tests/                End-to-end API tests (13 test files)
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
