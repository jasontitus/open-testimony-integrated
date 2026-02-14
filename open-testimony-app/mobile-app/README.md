# Open Testimony Mobile App

A Flutter application for capturing, signing, and uploading video and photo evidence with hardware-backed cryptographic integrity. Videos are stamped with GPS coordinates, timestamps, and ECDSA signatures tied to the device's Secure Enclave (iOS) or StrongBox (Android), making recordings tamper-evident and verifiable.

## Features

- **Secure video/photo capture** with real-time GPS tracking during recording
- **Hardware-backed cryptographic signing** (ECDSA P-256 via Secure Enclave / StrongBox) with automatic HMAC-SHA256 fallback for older devices
- **Gallery import** with EXIF metadata extraction (GPS, timestamps, camera info)
- **Offline-first storage** using local SQLite — record without connectivity, upload later
- **Resilient uploads** with automatic retry, exponential backoff, and device re-registration
- **Annotation editing** — add categories, tags, location descriptions, and notes to any recording
- **Audit trail viewing** for uploaded media, showing the full chain of events on the server

## Architecture

### Screens

| Screen | Purpose |
|---|---|
| **Home** | Bottom navigation hub; initializes crypto and auto-registers the device on first launch |
| **Camera** | Full-screen camera preview with a record button; streams GPS continuously and signs metadata on stop |
| **Gallery** | Lists all local recordings (newest first) with upload status; supports bulk import from device gallery |
| **Video Detail** | Edit annotations (category, tags, location description, notes) and view the server audit trail |
| **Settings** | Shows device ID and public key, configure server URL, register device, clear local data |

### Services

All services are singletons managed via `Provider`:

| Service | Responsibility |
|---|---|
| `HardwareCryptoService` | Key generation, device identity, and payload signing. Tries hardware ECDSA first, falls back to HMAC, and auto-upgrades when hardware becomes available. |
| `VideoService` | SQLite CRUD for `VideoRecord` models — save, query, update status, manage annotations. |
| `UploadService` | HTTP client (Dio) for all API calls — device registration, media upload with multipart form data, annotation sync, video listing, and audit trail retrieval. |
| `MediaImportService` | Gallery file picker with EXIF/video metadata extraction, GPS parsing, hash computation, and media type detection. |

### Data Flow

**Recording:**
1. Camera screen starts recording, GPS streams in background
2. On stop: file saved to disk, SHA-256 hash computed, `VideoRecord` created in SQLite
3. Metadata payload (device ID, timestamp, GPS, hash) is signed via `HardwareCryptoService`
4. `UploadService` sends the file + signed metadata to the server
5. Upload status updates: `pending` → `uploading` → `uploaded` / `failed`

**Import:**
1. User picks files from gallery via `MediaImportService`
2. EXIF data extracted (GPS, timestamp, camera info) with fallback to device GPS
3. Each file is hashed, saved to SQLite, signed, and uploaded sequentially

### Cryptography

The app uses a platform channel (`com.opentestimony/crypto`) to access native crypto:

- **iOS:** Secure Enclave ECDSA P-256 via `Security.framework` + `CryptoKit`
- **Android:** StrongBox or TEE-backed ECDSA P-256 via Android Keystore
- **Fallback:** Software HMAC-SHA256 via `flutter_secure_storage` when hardware is unavailable

The signed payload sent with each upload:
```json
{
  "version": "1.0",
  "auth": {
    "device_id": "<uuid>",
    "public_key_pem": "-----BEGIN PUBLIC KEY-----..."
  },
  "payload": {
    "video_hash": "<sha256>",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "location": { "lat": 37.7749, "lon": -122.4194 },
    "incident_tags": ["tag1"],
    "source": "live",
    "media_type": "video"
  },
  "signature": "<base64>",
  "signed_payload": "<json string of payload>"
}
```

## Project Structure

```
lib/
├── main.dart                          # Entry point, Provider setup, Material 3 theme
├── screens/
│   ├── home_screen.dart               # Bottom nav, crypto init, device registration
│   ├── camera_screen.dart             # Recording with GPS streaming
│   ├── gallery_screen.dart            # Video list, bulk import, upload status
│   ├── settings_screen.dart           # Device info, server config, data management
│   └── video_detail_screen.dart       # Annotation editor, audit trail viewer
├── services/
│   ├── hardware_crypto_service.dart   # ECDSA / HMAC signing with hardware fallback
│   ├── video_service.dart             # SQLite database operations
│   ├── upload_service.dart            # API client with retry logic
│   └── media_import_service.dart      # Gallery import, EXIF extraction
└── firebase_options.dart              # Firebase Crashlytics config (no analytics)

ios/Runner/CryptoPlugin.swift          # Secure Enclave ECDSA + video metadata extraction
android/.../CryptoPlugin.kt           # StrongBox / TEE ECDSA via Android Keystore
```

## Prerequisites

- Flutter SDK >= 3.0.0
- For iOS: Xcode with command-line tools (`xcode-select --install`)
- For Android: Android Studio with an API 23+ SDK
- Verify your setup with `flutter doctor`

## Getting Started

```bash
cd mobile-app
flutter pub get
flutter run
```

A physical device is recommended for full testing (camera, GPS, and hardware crypto all require real hardware). See [RUNNING.md](RUNNING.md) for detailed setup instructions covering emulators, simulators, and physical devices.

## Server Configuration

The app ships with a default server preset. To change the server:

- **At runtime:** Open Settings in the app, pick a preset from the dropdown, or choose "Other..." and enter a custom URL.
- **In code:** Edit the `serverPresets` list in `lib/services/upload_service.dart`.

When testing against a local backend, use your machine's LAN IP (e.g., `http://192.168.1.100:18080/api`), not `localhost`.

## Permissions

| Permission | Platform | Purpose |
|---|---|---|
| Camera | iOS, Android | Video/photo capture |
| Microphone | iOS, Android | Audio recording |
| Location (fine) | iOS, Android | GPS coordinates for recordings |
| Photo Library | iOS, Android | Gallery import |
| Internet | Android | Server uploads |

The app requests permissions at the point of use and handles denial gracefully.

## Database

Local SQLite database with the following schema (version 2):

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | UUID |
| `file_path` | TEXT | Path to local media file |
| `file_hash` | TEXT | SHA-256 hex digest |
| `timestamp` | TEXT | ISO 8601 capture time |
| `latitude` / `longitude` | REAL | GPS coordinates |
| `tags` | TEXT | Comma-separated tags |
| `upload_status` | TEXT | `pending`, `uploading`, `uploaded`, or `failed` |
| `source` | TEXT | `live` or `upload` |
| `media_type` | TEXT | `video` or `photo` |
| `category` | TEXT | Interview, Incident, Documentation, Other |
| `location_description` | TEXT | Human-readable location |
| `notes` | TEXT | Free-form notes |
| `server_id` | TEXT | ID returned by server after upload |

## API Endpoints

The mobile app communicates with the following backend endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/register-device` | Register device ID and public key |
| POST | `/upload` | Upload media file with signed metadata |
| GET | `/videos` | List videos (filterable by device) |
| GET | `/videos/{id}` | Fetch single video details |
| PUT | `/videos/{id}/annotations` | Update annotations |
| GET | `/videos/{id}/audit` | Retrieve audit trail |
| GET | `/tags` | Fetch tag suggestions for autocomplete |

## Version

Current: **2.1.0+5** — Supports iOS 15.0+ and Android API 23+.
