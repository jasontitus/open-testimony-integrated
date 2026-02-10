# SPEC.md: Open Testimony

## 1. Project Overview

A high-integrity, cross-platform mobile application and self-hosted backend for recording and uploading videos. The system ensures the authenticity of videos using hardware-backed cryptographic signatures (ECDSA) to verify time, location, and file integrity.

---

## 2. Mobile Application (Flutter)

### 2.1 Core Framework

* **Platform:** Flutter 3.x+ (using Impeller for high-performance video rendering).
* **Target:** iOS (Minimum 15.0) and Android (Minimum API 23).

### 2.2 Key Libraries

* **Camera:** `camerawesome` — chosen for granular control over the video stream and raw file output.
* **signing:** `biometric_signature` or `flutter_secure_storage` with hardware-backing.
* **Location:** `geolocator` — used to fetch GPS coordinates at the moment of file closure.
* **Networking:** `dio` — for multipart chunked uploads to the self-hosted server.

### 2.3 Cryptographic Workflow

1. **Key Generation:** On first launch, the app generates a **P-256 Elliptic Curve** key pair. The private key is stored in the **Secure Enclave (iOS)** or **StrongBox (Android)**.
2. **Hashing:** Once a video file is finalized, the app calculates a `SHA-256` hash of the entire file.
3. **Metadata Packaging:** A JSON payload is constructed containing the file hash, GPS coordinates, timestamp, and device ID.
4. **Signing:** The hardware module signs the `SHA-256` hash of this JSON payload.

---

## 3. Backend Architecture (Self-Hosted)

### 3.1 Server Infrastructure

* **Host OS:** Ubuntu 24.04 LTS (hardened).
* **Disk Encryption:** **LUKS (dm-crypt)** for the entire data partition.
* **Containerization:** Docker & Docker Compose for isolation and reproducibility.

### 3.2 Service Stack

| Service | Technology | Role |
| --- | --- | --- |
| **Reverse Proxy** | Nginx | Handles TLS termination and rate limiting. |
| **API Server** | FastAPI (Python) | Signature verification, metadata processing, and user auth. |
| **Object Store** | MinIO | S3-compatible storage for the raw video files. |
| **Metadata DB** | PostgreSQL | Stores video records, user public keys, and incident tags. |

---

## 4. Data & Verification Schema

### 4.1 Verification Logic

The server must verify the following before a video is marked "Verified" in the database:

1. **Public Key Check:** Does the `device_id` match a registered public key?
2. **Signature Check:** Does the provided signature match the hash of the metadata + video file?
3. **Integrity Check:** Does the `file_hash` in the metadata match the actual uploaded file?

### 4.2 Metadata JSON Structure

```json
{
  "version": "1.0",
  "auth": {
    "device_id": "string",
    "public_key_pem": "string"
  },
  "payload": {
    "video_hash": "sha256_hex_string",
    "timestamp": "iso8601_string",
    "location": {
      "lat": "float",
      "lon": "float"
    },
    "incident_tags": ["list", "of", "strings"],
    "source": "live | upload"
  },
  "signature": "ecdsa_base64_string"
}

```

---

## 5. Security & Offsite Backup

### 5.1 Disk Security

* **LUKS Configuration:** The `/var/lib/docker` directory must reside on a LUKS-encrypted volume.
* **SSH:** Key-based authentication only; password login disabled.

### 5.2 Offsite Backup (Restic)

* **Encryption:** All backups are encrypted locally using **AES-256** before transmission.
* **Automation:** A nightly cron job performs:
1. `pg_dump` of the Postgres database.
2. `restic backup` of the MinIO data and DB dumps.
3. `restic prune` to manage retention (7-day daily, 4-week weekly).


* **Destination:** A secondary physical server (over SFTP) or an encrypted S3 bucket.

---

## 6. Implementation Milestones

1. **Phase 1 (Backend):** Set up Ubuntu server with LUKS, Docker, and MinIO. Configure Nginx with SSL.
2. **Phase 2 (Mobile Basic):** Build Flutter app with `camerawesome` and a simple local gallery.
3. **Phase 3 (Mobile Secure):** Implement Secure Enclave key generation and file hashing.
4. **Phase 4 (Integration):** Implement the `POST /upload` endpoint on the server with signature verification.
5. **Phase 5 (Backup):** Configure Restic to an offsite location and test disaster recovery.
