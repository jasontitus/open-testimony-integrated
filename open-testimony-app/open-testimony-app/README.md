# Open Testimony - Secure Video Integrity System

A high-integrity, cross-platform mobile application and self-hosted backend for recording and uploading videos with cryptographic verification. The system ensures video authenticity using hardware-backed ECDSA signatures to verify time, location, and file integrity.

## 🏗️ Architecture

### Components

- **Mobile App**: Flutter app for iOS (15.0+) and Android (API 23+)
- **Backend API**: FastAPI server with cryptographic verification
- **Object Storage**: MinIO (S3-compatible) for video files
- **Database**: PostgreSQL for metadata and device registry
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

Edit `lib/services/upload_service.dart` and update the `baseUrl`:

```dart
static const String baseUrl = 'http://YOUR_SERVER_IP/api';
```

Replace `YOUR_SERVER_IP` with your server's IP address or domain.

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
    verification_status VARCHAR(20) NOT NULL,
    metadata_json JSON NOT NULL,
    uploaded_at TIMESTAMP NOT NULL
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

# Run tests
pytest
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

- [ ] Implement Restic automated backups
- [ ] Add video playback in mobile app
- [ ] Add video sharing functionality
- [ ] Implement user authentication
- [ ] Add web dashboard for viewing videos
- [ ] Support for multiple incident tags
- [ ] Add video compression options
- [ ] Implement batch upload for offline recordings
- [ ] Add network quality detection
- [ ] Support for photo capture
- [ ] Add dark mode to mobile app

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## 📞 Support

For issues and questions, please open an issue on GitHub.

---

**Built with security and integrity in mind** 🔒
