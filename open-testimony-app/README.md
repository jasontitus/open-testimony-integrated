# Open Testimony - Secure Video Integrity System

A high-integrity, cross-platform mobile application and self-hosted backend for recording and uploading videos with cryptographic verification. The system ensures video authenticity using hardware-backed ECDSA signatures to verify time, location, and file integrity.

## 🏗️ Architecture

### Components

- **Mobile App**: Flutter app for iOS (15.0+) and Android (API 23+)
- **Web UI**: React dashboard for browsing, tagging, and managing testimony
- **Backend API**: FastAPI server with cryptographic verification
- **AI Search Bridge**: FastAPI service for AI-powered video search (SigLIP2/OpenCLIP/PE-Core visual search, Whisper transcript search, Gemini frame captioning, temporal clip analysis)
- **Object Storage**: MinIO (S3-compatible) for video files
- **Database**: PostgreSQL with pgvector for metadata, device registry, and vector embeddings
- **Reverse Proxy**: Nginx for TLS termination and routing

### Security Features

- **P-256 ECDSA** cryptographic signatures
- **Hardware-backed key storage** (Secure Enclave on iOS, StrongBox on Android)
- **SHA-256** file hashing for integrity verification
- **GPS coordinates** captured at recording time
- **Timestamped** video metadata
- **Server-side signature verification**

## 📋 Prerequisites

### For Backend

- Docker & Docker Compose
- Ubuntu 24.04 LTS (recommended) or any Linux distribution
- SSL certificate (Let's Encrypt recommended)
- Domain name or public IP address

### For Mobile Development

- Flutter 3.x+ SDK
- For iOS: Xcode 14+, macOS
- For Android: Android Studio, Android SDK

## 🚀 Quick Start

### 1. Backend Setup

#### Step 1: Clone and Configure

```bash
cd open-testimony-app
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Update these values for production
POSTGRES_PASSWORD=your_secure_password
MINIO_ROOT_PASSWORD=your_secure_minio_password
```

#### Step 2: Update Nginx Configuration

Edit `nginx/conf/default.conf` and replace `your-domain.com` with your actual domain.

For development/testing without SSL, you can use the HTTP-only configuration:

```nginx
server {
    listen 80;
    server_name localhost;
    
    client_max_body_size 500M;
    
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Step 3: Start Backend Services

```bash
# Build and start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify services are running
docker-compose ps
```

The API will be available at:
- HTTP: `http://your-server-ip/api/`
- HTTPS: `https://your-domain.com/api/` (after SSL setup)

#### Step 4: Test the API

```bash
# Health check
curl http://localhost/api/health

# Expected response:
# {"status":"healthy","timestamp":"...","database":"connected","storage":"connected"}
```

### 2. Mobile App Setup

#### Step 1: Install Flutter Dependencies

```bash
cd mobile-app
flutter pub get
```

#### Step 2: Configure Server URL

The app includes a **server selector dropdown** in Settings. Pick a preset server or select "Other..." to enter a custom URL (e.g., `http://192.168.1.100:18080/api`). No need to edit source code to switch servers.

#### Step 3: Run on Device

**For Android:**

```bash
# Connect Android device via USB or use emulator
flutter run
```

**For iOS:**

```bash
# Open Xcode and configure signing
open ios/Runner.xcworkspace

# Run from Xcode or command line
flutter run
```

#### Step 4: Register Device

1. Open the app and go to **Settings** tab
2. Verify your **Device ID** and **Public Key** are displayed
3. Confirm the **Server URL** is correct
4. Tap **Register Device**
5. Wait for "Device registered successfully" message

### 3. Record and Upload Video

1. Go to **Record** tab
2. Grant camera, microphone, and location permissions
3. Tap the record button to start recording
4. Tap again to stop
5. Video will automatically upload to the server
6. Check **Gallery** tab to see upload status

## 📱 Mobile App Features

### Record Screen
- **Video Recording**: High-quality video capture using camerawesome
- **Location Capture**: GPS coordinates recorded at start of recording
- **Real-time Indicators**: Recording status displayed on screen

### Gallery Screen
- **Local Videos**: View all recorded videos
- **Upload Status**: See pending, uploading, uploaded, or failed status
- **Retry Uploads**: Manually retry failed uploads
- **Delete Videos**: Remove local videos

### Settings Screen
- **Device Info**: View Device ID and Public Key
- **Server Config**: Configure backend server URL
- **Device Registration**: Register device with backend
- **About**: App version and security info

## Web UI Features

### Map View
- **Interactive Map**: View all uploaded media on a Leaflet map with marker clustering
- **Detail Panel**: Click any marker to view full video with metadata

### List View
- **Filterable List**: Search by text, filter by tags, category, media type, and source
- **Quick Tag**: Click the tag icon on any video row to add/remove tags instantly without opening the detail panel
- **Bulk Tagging**: Toggle "Select" mode to check multiple videos, then "Tag Selected" to apply tags to all at once

### AI Search
- **Visual Search (Text)**: Describe what you're looking for and find matching video frames using vision model embeddings
- **Visual Search (Image)**: Upload a reference image to find visually similar frames
- **Transcript Search (Semantic)**: Search by meaning across all transcribed audio
- **Transcript Search (Exact)**: Find exact word matches in transcripts
- **Caption Search (Semantic)**: Search AI-generated frame descriptions by meaning
- **Caption Search (Exact)**: Keyword search on frame description text
- **Clip Search (Visual)**: Search temporal video windows by visual similarity
- **Action Search**: Search for specific actions/motions across time ("use of force", "chokehold")
- **Grouped Results**: Results are clustered by video — each group shows the best thumbnail, match count badge, score, category, and tags. Click the chevron to expand individual time-stamped matches
- **Search Term Highlighting**: Matching terms highlighted in result text
- **Video-Level Annotation**: Click a group header to open the inline player with a full annotation panel (category, tags, notes, location) — annotate the whole video without picking a specific time slice
- **Inline Playback**: Expand a group and click an individual match to jump to its exact timestamp
- **Bulk Selection**: Toggle "Select" mode to check entire video groups, then tag them all at once via the sticky bottom bar

### Queue Management
- **Review Queue**: Staff/admin triage uploaded videos with status filters (pending/reviewed/flagged)
- **Inline Review**: Video player, annotation editor, and audit log viewer in one panel
- **Keyboard Shortcuts**: Arrow keys to navigate, number keys to set review status
- **Auto-advance**: Moves to next pending video after marking one as reviewed
- **Queue Stats**: Counts by review status displayed as summary badges

### Quick Annotate System
A fast, click-based annotation workflow available in AI Search, List View, and the inline player:
- **QuickTagMenu**: Popover (or inline panel) showing category chips and tag pill toggles
- **Instant Save**: Clicking a tag or category immediately saves via the API (no "Save" button needed)
- **Optimistic Updates**: Tags update in the UI instantly, with automatic revert on API failure
- **Filter & Create**: Narrow long tag lists by typing, or create new tags inline
- **Bulk Mode**: When multiple videos are selected, the menu shows which tags are applied to all, some, or none
- **Notes & Location**: The inline annotation panel in AI Search also supports free-text notes and location descriptions (saved via a Save button)
- **Role-Based**: Only visible to staff and admin users

### Video Detail Panel
- **Video/Photo Playback**: Full media player with seeking support
- **Annotations**: Staff can edit category, location description, notes, and tags
- **Audit Log**: View the full change history for each video
- **Verification Status**: Cryptographic verification badges

## 🔒 How Cryptographic Verification Works

### On Mobile Device

1. **Key Generation** (first launch):
   - Generate P-256 elliptic curve key pair
   - Store private key in hardware-backed secure storage
   - Private key never leaves the device

2. **Video Recording**:
   - Record video to local file
   - Capture GPS coordinates at recording start
   - Calculate SHA-256 hash of video file

3. **Metadata Signing**:
   - Create JSON payload with file hash, timestamp, location
   - Sign the payload hash using device's private key
   - Package metadata + signature for upload

4. **Upload**:
   - Send video file + signed metadata to server
   - Server verifies signature using registered public key

### On Backend Server

1. **Device Registration**:
   - Store device public key in database
   - Link public key to device ID

2. **Upload Verification**:
   - Extract metadata and signature
   - Verify device is registered
   - Calculate video file hash
   - Compare with metadata hash
   - Verify ECDSA signature using public key
   - Mark video as "verified" if all checks pass

3. **Storage**:
   - Store video in MinIO (S3-compatible storage)
   - Store metadata in PostgreSQL
   - Track verification status

## 🗄️ Database Schema

### Devices Table

```sql
CREATE TABLE devices (
    id UUID PRIMARY KEY,
    device_id VARCHAR(255) UNIQUE NOT NULL,
    public_key_pem TEXT NOT NULL,
    device_info VARCHAR(500),
    registered_at TIMESTAMP NOT NULL,
    last_upload_at TIMESTAMP
);
```

### Videos Table

```sql
CREATE TABLE videos (
    id UUID PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    object_name VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    incident_tags TEXT[],
    source VARCHAR(50),
    media_type VARCHAR(20) DEFAULT 'video',
    exif_metadata JSON,
    verification_status VARCHAR(20) NOT NULL,
    metadata_json JSON NOT NULL,
    uploaded_at TIMESTAMP NOT NULL,
    category VARCHAR(50),
    location_description TEXT,
    notes TEXT,
    annotations_updated_at TIMESTAMP,
    annotations_updated_by VARCHAR(255),
    review_status VARCHAR(20) DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER,
    deleted_at TIMESTAMP,
    deleted_by INTEGER
);
```

## 🔧 API Endpoints

### Health Check
```
GET /health
```

### Register Device
```
POST /register-device
Content-Type: multipart/form-data

device_id: string
public_key_pem: string (PEM format)
device_info: string (optional)
```

### Upload Video
```
POST /upload
Content-Type: multipart/form-data

video: file (video file)
metadata: JSON string {
  "version": "1.0",
  "auth": {
    "device_id": "string",
    "public_key_pem": "string"
  },
  "payload": {
    "video_hash": "sha256_hex",
    "timestamp": "ISO8601",
    "location": {"lat": float, "lon": float},
    "incident_tags": ["string"],
    "source": "live|upload"
  },
  "signature": "base64_ecdsa_signature"
}
```

### List Videos
```
GET /videos?device_id=xxx&verified_only=true&limit=50&offset=0
```

### Get Video Details
```
GET /videos/{video_id}
```

## 🛠️ Development

### Backend Development

```bash
# Install Python dependencies
cd api-server
pip install -r requirements.txt

# Run locally (outside Docker)
uvicorn main:app --reload
```

### Running Tests

The project has four test suites:

**API Server Unit Tests** (run inside Docker — needs database):
```bash
docker compose exec api pip install pytest "httpx<0.28"
docker compose exec api python -m pytest tests/ -v
```

**Bridge Service Unit Tests** (run inside Docker — needs database + pgvector):
```bash
docker compose exec bridge pip install pytest "httpx<0.28"
docker compose exec bridge python -m pytest tests/ -v
```

**Integration Tests** (run on host — hits the live API at localhost:18080):
```bash
pip install pytest requests
python -m pytest tests/ -v
```

**Frontend Component Tests** (run on host):
```bash
cd web-ui
npm install
npx react-scripts test --watchAll=false --verbose
```

### Mobile Development

```bash
cd mobile-app

# Run in debug mode
flutter run

# Build release APK (Android)
flutter build apk --release

# Build iOS app
flutter build ios --release

# Run tests
flutter test

# Check for issues
flutter analyze
```

## 🔐 Production Deployment

### Backend Hardening

1. **Enable LUKS encryption** for data partition
2. **Configure SSL/TLS** with Let's Encrypt
3. **Set strong passwords** in `.env`
4. **Enable firewall** (UFW):
   ```bash
   ufw allow 22/tcp
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```
5. **Disable password SSH** (use keys only)
6. **Set up automated backups** with Restic

### Mobile App Production

1. **Update server URL** to production HTTPS endpoint
2. **Configure code signing** for iOS (Apple Developer account required)
3. **Configure keystore** for Android (for Play Store)
4. **Test on physical devices**
5. **Submit to App Store / Play Store**

## 📊 Monitoring & Maintenance

### Check Service Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f db
docker-compose logs -f minio

# Restart services
docker-compose restart api

# Stop all services
docker-compose down

# Start services
docker-compose up -d
```

### Database Backup

```bash
# Backup PostgreSQL
docker-compose exec db pg_dump -U user opentestimony > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T db psql -U user opentestimony < backup_20240101.sql
```

### MinIO Backup

```bash
# Access MinIO console
# Navigate to http://your-server-ip:9001
# Login with MINIO_ROOT_USER and MINIO_ROOT_PASSWORD
```

## 🚧 Roadmap / Future Enhancements

- [x] Add web dashboard for viewing videos
- [x] Implement user authentication (JWT-based, role-based access control)
- [x] Support for multiple incident tags
- [x] Support for photo capture
- [x] AI-powered video search (visual + transcript)
- [x] Quick Annotate workflow for fast tagging from search results and list view
- [x] Bulk tagging for multiple videos at once
- [x] Grouped search results by video with inline annotation panel
- [x] AI frame captioning (Gemini + local) and caption search
- [x] Temporal clip understanding with overlapping windows
- [x] Action detection and action search
- [x] Queue management UI for reviewing/triaging uploads
- [x] Access logging with IP tracking
- [x] SigLIP2 vision model support (native aspect ratio)
- [x] Address autocomplete / geocoding
- [ ] Implement Restic automated backups
- [ ] Add video playback in mobile app
- [ ] Add video sharing functionality
- [ ] Add video compression options
- [ ] Implement batch upload for offline recordings
- [ ] Add network quality detection
- [ ] Add dark mode to mobile app

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## 📞 Support

For issues and questions, please open an issue on GitHub.

---

**Built with security and integrity in mind** 🔒
