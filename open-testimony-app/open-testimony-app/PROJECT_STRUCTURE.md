# Project Structure

```
open-testimony-app/
├── README.md                    # Main documentation
├── QUICKSTART.md               # Quick start guide
├── SPEC.md                     # Original specification
├── docker-compose.yml          # Docker orchestration
├── .env.example               # Environment template
├── .gitignore                 # Git ignore rules
│
├── api-server/                # Backend API (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # Main FastAPI application
│   ├── config.py             # Configuration settings
│   ├── database.py           # Database connection
│   ├── models.py             # SQLAlchemy models
│   └── minio_client.py       # MinIO storage client
│
├── nginx/                     # Reverse proxy
│   └── conf/
│       └── default.conf      # Nginx configuration
│
└── mobile-app/               # Flutter mobile application
    ├── pubspec.yaml          # Flutter dependencies
    │
    ├── lib/
    │   ├── main.dart         # App entry point
    │   │
    │   ├── screens/          # UI screens
    │   │   ├── home_screen.dart      # Main navigation
    │   │   ├── camera_screen.dart    # Video recording
    │   │   ├── gallery_screen.dart   # Local videos
    │   │   └── settings_screen.dart  # Configuration
    │   │
    │   └── services/         # Business logic
    │       ├── crypto_service.dart   # ECDSA signing
    │       ├── video_service.dart    # Video storage
    │       └── upload_service.dart   # Backend API
    │
    ├── android/              # Android configuration
    │   └── app/
    │       ├── build.gradle
    │       └── src/main/AndroidManifest.xml
    │
    └── ios/                  # iOS configuration
        └── Runner/
            └── Info.plist

```

## Key Files

### Backend

- **main.py**: Core API with endpoints for device registration, video upload, and verification
- **models.py**: Database schema (devices and videos tables)
- **config.py**: Environment-based configuration
- **minio_client.py**: S3-compatible object storage interface

### Mobile App

- **crypto_service.dart**: P-256 ECDSA key generation and signing
- **video_service.dart**: Local video database and file management
- **upload_service.dart**: HTTP client for backend API
- **camera_screen.dart**: Video recording with camerawesome
- **gallery_screen.dart**: Local video library with upload retry
- **settings_screen.dart**: Device registration and configuration

### Infrastructure

- **docker-compose.yml**: Orchestrates Nginx, FastAPI, PostgreSQL, and MinIO
- **nginx/conf/default.conf**: Reverse proxy with TLS termination
- **.env.example**: Configuration template for secrets

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **PostgreSQL**: Relational database for metadata
- **MinIO**: S3-compatible object storage
- **Nginx**: Reverse proxy and TLS termination
- **Docker**: Containerization

### Mobile
- **Flutter**: Cross-platform mobile framework
- **camerawesome**: High-performance camera plugin
- **pointycastle**: Cryptography library
- **sqflite**: Local SQLite database
- **geolocator**: GPS location services
- **dio**: HTTP client

### Security
- **P-256 ECDSA**: Elliptic curve signatures
- **SHA-256**: File integrity hashing
- **Secure Enclave** (iOS): Hardware key storage
- **StrongBox** (Android): Hardware key storage
