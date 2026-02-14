# Open Testimony — Implemented Features

## Core Platform (v1.0)

### Mobile App (Flutter)
- **Live video recording** with camera preview and recording indicator
- **GPS location capture** — continuous location streaming during recording, best-accuracy selection
- **Cryptographic signing** — HMAC-SHA256 signing of video hash + metadata at recording time
- **Local-first storage** — videos saved to SQLite immediately, upload is async
- **Automatic upload** — videos uploaded to server after recording with retry on failure
- **Device registration** — devices self-register with public key on first upload
- **Settings screen** — server URL configuration, device info display, crypto version display

### API Server (FastAPI)
- **Device registration** (`POST /register-device`) — stores device public keys
- **Video upload** (`POST /upload`) — receives video + signed metadata, verifies hash integrity, stores in MinIO
- **Signature verification** — validates HMAC signatures against registered device keys
- **Video listing** (`GET /videos`) — paginated list with device and verification filters
- **Video detail** (`GET /videos/{id}`) — full metadata including hash, location, tags
- **Presigned URLs** (`GET /videos/{id}/url`) — temporary MinIO URLs for video playback
- **MinIO object storage** — videos stored in S3-compatible storage with device-based paths
- **PostgreSQL metadata** — all video metadata, device info, verification status persisted

### Web UI (React + Tailwind)
- **Map view** — Leaflet map with marker clustering showing video locations
- **List view** — sidebar with video cards showing device, timestamp, status
- **Video playback** — HTML5 player with presigned URL fetching
- **View toggle** — switch between map and list views
- **Dark theme** — consistent dark UI with Tailwind CSS

### Infrastructure
- **Docker Compose** stack: Nginx reverse proxy, FastAPI API, PostgreSQL, MinIO, React web UI
- **Nginx routing** — `/api/` to FastAPI, `/video-stream/` to MinIO, `/` to web UI

---

## Feature 1: Upload from Device Gallery (v2.0)

Allows importing existing photos and videos from the device's media gallery.

### Mobile Changes
- **MediaImportService** (`media_import_service.dart`) — multi-file picker via `image_picker`, EXIF extraction via `exif` package, media type detection (photo/video by extension), SHA-256 hashing
- **Gallery screen** — FAB import button, processes each file (hash + EXIF), saves to SQLite with `source='upload'`, attempts upload
- **Source badges** in gallery — "LIVE" (blue) for recorded, "IMPORTED" (purple) for gallery imports
- **Media type icons** — camera icon for photos, video icon for videos

### Server Changes
- **Upload endpoint** — accepts `media_type` (photo/video), `source` (live/upload), `exif_metadata` (JSON)
- **Separate storage paths** — `photos/` vs `videos/` in MinIO
- **Verification status** — imported media marked as `signed-upload` (signed by device but not captured live)
- **Content-type handling** — correct MIME types for photos vs videos

### Platform Permissions
- iOS: `NSPhotoLibraryUsageDescription` in Info.plist
- Android: `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO` in AndroidManifest.xml

---

## Feature 2: Metadata & Annotations (v2.0)

Allows adding descriptive metadata to uploaded videos, editable after upload.

### Mobile Changes
- **VideoDetailScreen** (`video_detail_screen.dart`) — new screen showing full video metadata with editable fields
- **Editable fields**: category dropdown (interview/incident), location description text field, freeform notes textarea
- **Local persistence** — annotations saved to SQLite via `updateAnnotations()`
- **Server sync** — annotations pushed to server via `PUT /videos/{id}/annotations` if video has a server ID
- **Gallery navigation** — tap any video card to open detail screen

### Server Changes
- **Annotation endpoint** (`PUT /videos/{id}/annotations`) — accepts category, location_description, notes from owning device
- **Owner validation** — only the recording device can update annotations (via device_id check)
- **Video model** — added `category`, `location_description`, `notes`, `annotations_updated_at`, `annotations_updated_by` columns
- **Video list/detail responses** — include annotation fields

### Database Migration (`001_add_annotations.sql`)
- Idempotent `ALTER TABLE` adding annotation columns to videos and `crypto_version` to devices

---

## Feature 3: Hardware-Backed ECDSA Signing (v2.0)

Upgrades from software HMAC-SHA256 to hardware-backed ECDSA P-256 for court-grade chain of trust.

### Mobile Changes
- **HardwareCryptoService** (`hardware_crypto_service.dart`) — platform channel interface (`com.opentestimony/crypto`) with fallback to HMAC if hardware unavailable
- **Progressive upgrade** — devices that start with HMAC automatically upgrade to ECDSA when hardware becomes available
- **Key management** — keys stored in Flutter Secure Storage, hardware keys in platform secure enclave
- **Settings display** — shows actual crypto version (Hardware ECDSA P-256 vs Software HMAC-SHA256)

### iOS Native (`CryptoPlugin.swift`)
- **Secure Enclave** — `SecKeyCreateRandomKey` with `kSecAttrTokenIDSecureEnclave`, P-256 curve
- **ECDSA signing** — `SecKeyCreateSignature` with `.ecdsaSignatureMessageX962SHA256`
- **Public key export** — PEM format for server registration

### Android Native (`CryptoPlugin.kt`)
- **Android KeyStore / StrongBox** — `KeyPairGenerator` with `ECGenParameterSpec("secp256r1")`, `setIsStrongBoxBacked(true)` with TEE fallback
- **ECDSA signing** — `Signature.getInstance("SHA256withECDSA")`
- **Public key export** — PEM format via KeyStore

### Server Changes
- **Device model** — `crypto_version` field tracks HMAC vs ECDSA per device
- **Signature verification** — server already had ECDSA verification code; real PEM keys now pass through correctly
- **Crypto upgrade** — re-registration with new crypto_version updates device record

---

## Feature 4: Blockchain-Like Audit Log (v2.0)

Immutable hash-chained log proving uploads and changes occurred at specific times without tampering.

### Server Changes
- **AuditLog model** — `sequence_number`, `event_type`, `video_id`, `device_id`, `event_data` (JSON), `entry_hash` (SHA-256), `previous_hash` (chain link), `created_at`
- **AuditService** (`audit_service.py`) — `log_event()` appends to chain with `SELECT FOR UPDATE` locking to prevent race conditions; `verify_chain()` walks entire chain verifying hash links
- **Hash chain** — each entry's hash = SHA-256(sequence + type + data + previous_hash + timestamp); genesis entry uses `"0" * 64`
- **Event types**: `device_register`, `upload`, `annotation_update`

### API Endpoints
- `GET /audit-log` — query with filters (event_type, video_id, pagination)
- `GET /audit-log/verify` — verify entire chain integrity, returns `{valid: true/false, errors: []}`
- `GET /videos/{id}/audit` — audit trail for a specific video

### Mobile Changes
- **VideoDetailScreen** — optional audit trail section showing chain entries when video has a server ID
- **UploadService** — `getVideoAuditTrail(serverId)` method to fetch audit data

### Database Migration (`002_add_audit_log.sql`)
- Idempotent `CREATE TABLE` with indexes on sequence_number, event_type, video_id

---

## Feature 5: Web UI User Management & Enhanced Display (v2.0)

Role-based web UI with user authentication, enhanced video display, and staff/admin editing capabilities.

### Web UI — Authentication
- **JWT auth with httpOnly cookies** — `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- **Username-based login** — no email required, staff privacy preserved
- **Admin seed on startup** — first admin created from `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars when no users exist
- **Login page** — dark-themed login form with error display

### Web UI — User Management (Admin)
- **Create users** (`POST /auth/users`) — admin creates staff or admin accounts
- **List users** (`GET /auth/users`) — admin views all users with roles, status, last login
- **Update users** (`PUT /auth/users/{id}`) — admin toggles roles (admin/staff), activates/deactivates accounts
- **Reset passwords** (`PUT /auth/users/{id}/password`) — admin resets user passwords
- **Admin panel** — dedicated user management page with create form, user table, inline actions

### Web UI — Enhanced Video Display
- **Verification badges** — all statuses handled: verified (green), verified-mvp (green), signed-upload (blue), error-mvp (yellow), error (orange), failed (red), pending (yellow)
- **Source badges** — LIVE (green) and IMPORTED (purple) pills
- **Media type indicators** — camera/video icons with Photo/Video labels
- **Category pills** — interview, incident, documentation, other
- **Video detail panel** — full metadata view: timestamp, device_id, location, file hash, source, media type, category, notes, EXIF metadata, verification status, annotations history
- **Component architecture** — App.js refactored to component files under `src/components/`

### Web UI — Staff/Admin Editing
- **Web annotation editing** (`PUT /videos/{id}/annotations/web`) — staff and admin can edit category, location description, notes, incident tags on any video
- **Admin soft delete** (`DELETE /videos/{id}`) — admin sets `deleted_at` timestamp, video filtered from all listings
- **All changes logged to audit chain** — new event types `web_annotation_update`, `video_deleted`, `user_created`, `user_updated`, `password_reset` with `user_id` tracking
- **Audit chain backward compatible** — `user_id` stored on `AuditLog` row and in `event_data` but NOT in hash formula, preserving existing chain integrity

### Database Migration (`003_add_users.sql`)
- `users` table: id, username (unique), password_hash, display_name, role, is_active, created_at, last_login_at
- `audit_log.user_id` column for user attribution
- `videos.deleted_at`, `videos.deleted_by` columns for soft delete

---

## Testing Infrastructure (v2.0)

### Pytest API Test Suite (`tests/`)
Integration tests running against the live Docker stack:
- **test_api_health.py** (2) — root and health endpoints
- **test_device_registration.py** (4) — register, duplicate, crypto upgrade, validation
- **test_upload.py** (4) — video upload, photo+EXIF, unregistered device, hash mismatch
- **test_videos.py** (6) — list, new fields, device filter, pagination, detail, 404
- **test_annotations.py** (6) — update, categories, clear, wrong device, invalid, 404
- **test_audit_log.py** (7) — list, fields, filter, chain verify, video trail, pagination
- **test_auth.py** (12) — login, logout, /auth/me, user CRUD, role enforcement, password reset, admin seed
- **test_web_annotations.py** (9) — web annotation editing, soft delete, audit trail, chain integrity

### Makefile
- `make test` — runs API tests + Flutter analyze
- `make test-api` — pytest integration tests
- `make test-flutter` — Flutter static analysis
- `make up/down/rebuild/migrate` — Docker infrastructure commands

---

## Mobile App Enhancements (v2.1)

### ECDSA Signature Verification Fix
- **Signed payload passthrough** — phone sends the exact JSON string that was signed as `signed_payload` in upload metadata, so the server verifies against identical bytes
- **SPKI public key encoding** — iOS `SecKeyCopyExternalRepresentation` returns raw EC point (04 || x || y); now wrapped in SubjectPublicKeyInfo ASN.1 header for Python `cryptography` compatibility
- **Single-hash verification** — server no longer pre-hashes payload before passing to `ECDSA(SHA256).verify()`, which hashes internally

### GPS & Timestamp Extraction for Imported Media
- **Video GPS extraction** — iOS platform channel (`extractVideoLocation`) reads GPS from QuickTime/ISO 6709 metadata in video containers via `AVURLAsset`
- **Photo GPS extraction** — EXIF GPS data (DMS to decimal degrees) already extracted for photos
- **Device GPS fallback** — if no metadata GPS found, falls back to phone's current location
- **Original timestamps** — imported media uses creation date from file metadata (EXIF DateTimeOriginal for photos, QuickTime creation_date for videos), with file modification time as fallback

### Upload Resilience & Progress
- **Retry with exponential backoff** — up to 3 attempts with 2s/4s/6s delays on network/server errors
- **No retry on client errors** — 4xx errors (except 403) are not retried
- **403 re-registration** — automatic device re-registration and retry on auth failure
- **Upload progress UI** — blue banner in gallery showing "Uploading X of Y (N done)" with per-file progress bar
- **Summary snackbar** — final count of successful/failed uploads

### Other Mobile Changes
- **Clear all local videos** — settings screen button with confirmation dialog to delete all locally stored media
- **App icon label** — changed from "Open Testimony" to "Testimony" (iOS `CFBundleDisplayName`)
- **Firebase Crashlytics** — crash reporting without analytics tracking (`IS_ANALYTICS_ENABLED=false`)

### Android Support
- **Android project regenerated** for Flutter 3.38+ compatibility (AGP 8.11.1, Kotlin 2.2.20, Gradle 8.14)
- **Firebase Crashlytics on Android** — `google-services.json` + Gradle plugins configured
- **Android KeyStore ECDSA** — `CryptoPlugin.kt` uses StrongBox (Android 9+) with TEE fallback for hardware-backed P-256 signing
- **Android emulator setup** — SDK command-line tools, API 34 system image with Play Store, Pixel 7 AVD
- **Java 17 configured** for Gradle compatibility (`flutter config --jdk-dir`)

### Web UI Fix
- **Map view video playback** — replaced small floating card with full side panel containing video player and detail view
- **MinIO URL fix** — `MINIO_EXTERNAL_ENDPOINT` now defaults to `localhost:18080/video-stream` (env-var overridable) instead of hardcoded ngrok domain

---

## AI-Powered Video Search (v3.0)

Integrates VideoIndexer's AI models into Open Testimony, making uploaded videos searchable by visual content and spoken words.

### Architecture
- **Bridge service** — standalone FastAPI on port 8003, loads OpenCLIP ViT-bigG-14 (1280-dim) + Qwen3-Embedding-8B (4096-dim) + Whisper large-v3 models in-process
- **pgvector** — PostgreSQL extension for vector similarity search; embeddings stored as rows alongside metadata, no separate index files
- **Webhook pipeline** — OT API fires `POST /hooks/video-uploaded` after upload; bridge background worker picks up pending jobs

### Database (Migration `005_add_pgvector.sql`)
- `frame_embeddings` — one row per extracted video frame (video_id, frame_num, timestamp_ms, embedding vector(1280))
- `transcript_embeddings` — one row per spoken segment (video_id, segment_text, start_ms, end_ms, embedding vector(4096))
- `video_index_status` — per-video indexing job tracking (status, frame_count, segment_count, error_message)
- HNSW index on frame embeddings for fast approximate nearest-neighbor search

### Indexing Pipeline (`bridge/indexing/`)
- Downloads video from MinIO to temp path
- Extracts frames at configurable interval, skips dark frames (brightness < 15)
- Encodes frames with OpenCLIP ViT-bigG-14, batch INSERT into `frame_embeddings`
- Generates 320px JPEG thumbnails at `/data/thumbnails/{video_id}/{timestamp_ms}.jpg`
- Transcribes audio with Whisper large-v3, encodes segments with Qwen3-Embedding-8B, INSERT into `transcript_embeddings`
- Background asyncio worker polls for pending jobs every 10 seconds

### Search Endpoints (`bridge/search/`)
- `GET /search/visual?q=...` — text-to-video: encode text with OpenCLIP, pgvector cosine similarity on frame_embeddings
- `POST /search/visual` — image-to-video: encode uploaded image, same search
- `GET /search/transcript?q=...` — semantic: encode text with Qwen, cosine similarity on transcript_embeddings
- `GET /search/transcript/exact?q=...` — exact text: case-insensitive ILIKE on segment_text

### Admin Endpoints
- `GET /indexing/status` — overall stats (pending/processing/completed/failed)
- `GET /indexing/status/{video_id}` — per-video indexing detail
- `POST /indexing/reindex/{video_id}` — re-index single video (deletes old embeddings first)
- `POST /indexing/reindex-all` — re-index all videos
- `GET /thumbnails/{video_id}/{ts}.jpg` — serve thumbnails with nearest-frame fallback

### Web UI
- **AI Search tab** — new view mode in header, four search modes: Visual (Text), Visual (Image), Transcript (Semantic), Transcript (Exact)
- **Result cards** — horizontal layout with 160x96px thumbnail, score bar (green/yellow/red), timestamp, transcript text preview, play overlay on hover
- **Inline video player** — clicking a result opens a split-pane player (left) + results (right); auto-seeks to matched timestamp; shows transcript text below player for transcript results
- **Indexing stats** — footer showing indexed/processing/pending counts

### Infrastructure
- **Docker Compose** — bridge service added (service #6); PostgreSQL image changed to `pgvector/pgvector:pg16`; `bridge_temp` volume for temp video downloads
- **Nginx** — `/ai-search/*` proxied to bridge with deferred DNS resolution (starts even if bridge is down)
- **Auth** — bridge validates same JWT cookies as OT API (shared secret + algorithm)

---

## Mobile App Server Selector (v3.0)

### Server URL Dropdown
- **Preset server list** — dropdown with "Open Testimony (Main)" and "Other..." options in Settings screen
- **Custom URL entry** — selecting "Other..." reveals a text field for entering a custom server URL (e.g., `http://192.168.1.100:18080/api`)
- **Persistent storage** — selected server URL saved to FlutterSecureStorage, restored on app startup
- **Extensible** — new regional servers added by appending to `serverPresets` list in `upload_service.dart`
- **No-typo design** — preset dropdown prevents accidental URL mistakes; custom entry only shown when explicitly chosen

---

## Tag Management & Bulk Operations (v3.1)

### Tagging System
- **Persistent tags** (`tags` table) — shared vocabulary of tags managed via API
- `POST /tags` — staff/admin create new tags
- `GET /tags` — list all tags; `GET /tags/counts` — tag frequency counts
- `DELETE /tags` — admin delete unused tags
- `GET /categories/counts` — category frequency counts

### Web UI — Quick Tag Menu
- **QuickTagMenu** component — popover for fast tag assignment on one or multiple videos
- **Bulk select mode** — select multiple videos in list or AI search results, then "Tag Selected" to apply tags/category in batch
- **Category chips** — quick-set category (interview, incident, documentation, other)
- **Tag toggles** — check/uncheck existing tags; inline create new tags

### Database Migration (`006_add_tags_table.sql`)
- `tags` table: name (primary key), created_at

---

## SigLIP2 Vision Model & Smart Indexing (v3.1)

### Vision Model Upgrade
- **HuggingFace SigLIP2** (`hf_siglip`) — new default vision model family: `google/siglip2-so400m-patch16-naflex` with native aspect ratio (NAFlex), 1152-dim embeddings
- **Three model families** — `hf_siglip`, `open_clip`, `pe_core` selectable via `VISION_MODEL_FAMILY` env var
- **Concurrent search during indexing** — model locks allow search requests to proceed while indexing is in progress

### Smart Index Fixer
- Automatic detection and repair of corrupted or incomplete indexing jobs on bridge startup

### Database Migration (`007_upgrade_frame_embedding_dim.sql`)
- Widens `frame_embeddings.embedding` column to support larger model dimensions

---

## Frame Captioning & Caption Search (v3.1)

### Captioning Pipeline (`bridge/indexing/captioning.py`)
- **Gemini API provider** — sends individual frames to Gemini (default: `gemini-3-flash-preview`) for detailed natural-language descriptions
- **Local provider** — alternative Qwen3-VL for offline/air-gapped deployments
- **Configurable prompt** — caption prompt focuses on people, actions, objects, and physical interactions
- **Batched inference** — configurable batch size and max tokens per caption

### Caption Search
- `GET /search/caption?q=...` — semantic search on caption embeddings (Qwen3-Embedding-8B encoded)
- `GET /search/caption/exact?q=...` — case-insensitive keyword search on caption text
- **Caption embeddings table** — video_id, frame_num, timestamp_ms, caption_text, embedding (4096-dim)

---

## Video Clip Understanding (v3.2)

Temporal analysis for detecting actions and motion that span multiple frames.

### Clip Indexing (`bridge/indexing/pipeline.py`)
- **Overlapping temporal windows** — 16 frames @ 4fps with 8-frame stride (50% overlap), configurable via `CLIP_WINDOW_FRAMES`, `CLIP_WINDOW_STRIDE`, `CLIP_FPS`
- **Mean-pooled clip embeddings** — vision model encodes each frame in window; mean of frame embeddings becomes clip embedding
- **Clip embeddings table** — video_id, start_ms, end_ms, start_frame, end_frame, num_frames, embedding (vision_dim)

### Action Captioning (`bridge/indexing/action_captioning.py`)
- **Multi-frame Gemini analysis** — sampled frames from each clip window sent to Gemini with action-focused prompt
- **Action descriptions** — "person pushing another person", "aggressive gesture", "chokehold"
- **Action embeddings table** — same structure as clip + action_text field, text encoded with Qwen3-Embedding-8B
- **Optional** — controlled by `CLIP_ACTION_CAPTIONING` env var (disabled by default to save API cost)

### Clip & Action Search
- `GET /search/clip/visual?q=...` — visual similarity search on mean-pooled clip embeddings
- `GET /search/action?q=...` — semantic search on action description embeddings
- `GET /search/action/exact?q=...` — keyword search on action_text (e.g. "chokehold", "use of force")

### Database Migration (`008_add_clip_embeddings.sql`)
- `clip_embeddings` table with HNSW index (cosine_ops)
- `action_embeddings` table with HNSW index + GIN trigram index on action_text

---

## Queue Management UI (v3.2)

### Web UI — Queue Panel (`QueuePanel.js`)
- **Review queue** — staff/admin triage uploaded videos by status: pending, reviewed, flagged
- **Queue stats** — `GET /queue/stats` returns counts per status; displayed as summary badges
- **Per-video review** — inline video player, annotation editor (category, location, notes), audit log viewer
- **Review actions** — Mark Reviewed, Flag, Mark Pending buttons
- **Keyboard shortcuts** — arrow keys to navigate between videos, number keys to set review status
- **Auto-advance** — after marking a video, automatically moves to next pending video
- **Address autocomplete** — geocoding widget in location field, restricted by `GEOCODE_COUNTRY_CODES`

### API Endpoints
- `GET /queue` — list videos by review_status with pagination
- `GET /queue/stats` — count of pending/reviewed/flagged videos
- `PUT /videos/{id}/review` — update review_status (staff/admin only)
- `GET /geocode/search` — address autocomplete proxy (country-filtered)

---

## Access Logging & IP Tracking (v3.2)

### Request Logging
- **Access log** — every HTTP request logged to `/app/logs/access.jsonl`
- **Fields**: timestamp, client IP, method, path, query parameters, status code, duration (ms), user agent
- **Volume-mounted** — `api_logs` Docker volume persists logs across restarts

### Analysis Script (`scripts/scan-access-log.py`)
- Scans access logs for non-LAN IP addresses
- Identifies external access attempts
- Useful for security monitoring

---

## Search UX Improvements (v3.2)

### Search Term Highlighting
- **Highlighted matches** — search terms highlighted in yellow in transcript and caption result text
- **Bolded matches** — matching portions visually emphasized in result cards

### Result Grouping
- **Group by video** — search results grouped by video_id with best thumbnail, match count badge, score bar
- **Expandable groups** — click group header to see individual matches with timestamps
- **Click-to-seek** — clicking a match opens inline player and jumps to matched timestamp

### Visual Mode Default
- AI Search defaults to Visual (Text) mode for immediate text-based searching
