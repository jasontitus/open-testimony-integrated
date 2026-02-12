"""
Open Testimony API Server
FastAPI backend for video upload, signature verification, and metadata storage.
"""
import asyncio
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature
import base64
from minio import Minio
import httpx

from sqlalchemy import func as sa_func, or_

from database import engine, Base, get_db
from models import Video, Device, AuditLog, User, Tag
from minio_client import get_minio_client, ensure_bucket_exists
from config import settings
import audit_service
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_optional_user, require_admin, require_staff,
)

# Default tags loaded at startup
_default_tags: list[str] = []

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Open Testimony API",
    description="Secure Video Integrity System API",
    version="2.0.0"
)

# CORS middleware - configure appropriately for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize MinIO bucket and seed admin user on startup"""
    minio_client = get_minio_client()
    ensure_bucket_exists(minio_client, settings.MINIO_BUCKET)

    # Seed admin user if configured and no users exist
    if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD:
        from database import SessionLocal
        db = SessionLocal()
        try:
            user_count = db.query(User).count()
            if user_count == 0:
                admin = User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    display_name=settings.ADMIN_DISPLAY_NAME or settings.ADMIN_USERNAME,
                    role="admin",
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                db.add(admin)
                db.commit()
                logger.info(f"Seeded admin user: {settings.ADMIN_USERNAME}")
        finally:
            db.close()

    # Load default tags from config file and seed the tags table
    global _default_tags
    tags_path = os.path.join(os.path.dirname(__file__), settings.DEFAULT_TAGS_FILE)
    if os.path.exists(tags_path):
        with open(tags_path) as f:
            _default_tags = json.load(f)
        logger.info(f"Loaded {len(_default_tags)} default tags")
    else:
        logger.warning(f"Default tags file not found: {tags_path}")

    from database import SessionLocal
    db_seed = SessionLocal()
    try:
        existing = {t.name for t in db_seed.query(Tag).all()}
        added = 0
        for tag_name in _default_tags:
            if tag_name not in existing:
                db_seed.add(Tag(name=tag_name, created_at=datetime.utcnow()))
                added += 1
        if added:
            db_seed.commit()
            logger.info(f"Seeded {added} default tags into tags table")
    finally:
        db_seed.close()

    # Migrate: add review_status, reviewed_at, reviewed_by columns if missing
    from sqlalchemy import inspect as sa_inspect, text
    db_migrate = SessionLocal()
    try:
        insp = sa_inspect(engine)
        cols = {c["name"] for c in insp.get_columns("videos")}
        with engine.begin() as conn:
            if "review_status" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN review_status VARCHAR(20) DEFAULT 'pending'"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_videos_review_status ON videos (review_status)"))
                logger.info("Added review_status column to videos table")
            if "reviewed_at" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN reviewed_at TIMESTAMP"))
                logger.info("Added reviewed_at column to videos table")
            if "reviewed_by" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN reviewed_by VARCHAR(255)"))
                logger.info("Added reviewed_by column to videos table")
    finally:
        db_migrate.close()

    logger.info("Open Testimony API Server started successfully")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Open Testimony API",
        "version": "2.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "storage": "connected"
    }


@app.get("/tags")
async def get_tags(db: Session = Depends(get_db)):
    """Return all available tags: tags table merged with any tags found on videos."""
    # Tags from the persistent tags table
    table_tags = [t.name for t in db.query(Tag).order_by(Tag.created_at).all()]

    # Tags found on videos (catches any that slipped past the table)
    rows = (
        db.query(sa_func.unnest(Video.incident_tags))
        .filter(Video.deleted_at == None)
        .distinct()
        .all()
    )
    video_tags = [row[0] for row in rows if row[0]]

    # Merge and deduplicate, preserving tags table order first
    all_tags = list(dict.fromkeys(table_tags + video_tags))

    return {
        "default_tags": _default_tags,
        "all_tags": all_tags,
    }


@app.get("/tags/counts")
async def get_tag_counts(db: Session = Depends(get_db)):
    """Return tags with their usage counts, sorted by count descending."""
    rows = (
        db.query(
            sa_func.unnest(Video.incident_tags).label("tag"),
            sa_func.count().label("cnt"),
        )
        .filter(Video.deleted_at == None)
        .group_by("tag")
        .order_by(sa_func.count().desc())
        .all()
    )
    return {
        "tags": [{"tag": row.tag, "count": row.cnt} for row in rows if row.tag]
    }


class CreateTagRequest(BaseModel):
    tag: str


@app.post("/tags")
async def create_tag(
    body: CreateTagRequest,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff/admin creates a new tag that persists in the database."""
    tag = body.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")

    existing = db.query(Tag).filter(Tag.name == tag).first()
    if existing:
        return {"status": "exists", "tag": tag}

    db.add(Tag(name=tag, created_at=datetime.utcnow()))
    db.commit()
    return {"status": "created", "tag": tag}


@app.get("/categories/counts")
async def get_category_counts(db: Session = Depends(get_db)):
    """Return categories with their usage counts, sorted by count descending."""
    rows = (
        db.query(
            Video.category,
            sa_func.count().label("cnt"),
        )
        .filter(Video.deleted_at == None, Video.category != None)
        .group_by(Video.category)
        .order_by(sa_func.count().desc())
        .all()
    )
    return {
        "categories": [{"category": row.category, "count": row.cnt} for row in rows]
    }


@app.post("/register-device")
async def register_device(
    device_id: str = Form(...),
    public_key_pem: str = Form(...),
    device_info: Optional[str] = Form(None),
    crypto_version: Optional[str] = Form("hmac"),
    db: Session = Depends(get_db)
):
    """
    Register a new device with its public key.
    The device_id should be unique per device.
    """
    try:
        # Check if device already exists
        existing_device = db.query(Device).filter(Device.device_id == device_id).first()
        if existing_device:
            # Update crypto_version if upgrading from HMAC to ECDSA
            if crypto_version and existing_device.crypto_version != crypto_version:
                existing_device.crypto_version = crypto_version
                existing_device.public_key_pem = public_key_pem
                db.commit()
                logger.info(f"Device {device_id} upgraded crypto to {crypto_version}")

                audit_service.log_event(
                    db, "device_register",
                    {"device_id": device_id, "action": "crypto_upgrade", "crypto_version": crypto_version},
                    device_id=device_id,
                )
                db.commit()

                return {
                    "status": "success",
                    "device_id": device_id,
                    "message": f"Device crypto upgraded to {crypto_version}"
                }

            logger.info(f"Device already registered: {device_id}")
            return {
                "status": "success",
                "device_id": device_id,
                "message": "Device already registered"
            }

        # Validate public key format
        if 'DEVICE:' in public_key_pem or public_key_pem.startswith('-----BEGIN PUBLIC KEY-----\nREVW'):
            logger.info(f"Registering device with MVP key format: {device_id}")
        else:
            try:
                serialization.load_pem_public_key(public_key_pem.encode())
                logger.info(f"Registering device with ECDSA key format: {device_id}")
            except Exception as e:
                logger.warning(f"Key validation warning for {device_id}: {str(e)}")
                pass

        # Create new device
        device = Device(
            device_id=device_id,
            public_key_pem=public_key_pem,
            device_info=device_info,
            registered_at=datetime.utcnow(),
            crypto_version=crypto_version or "hmac",
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        audit_service.log_event(
            db, "device_register",
            {"device_id": device_id, "crypto_version": crypto_version or "hmac"},
            device_id=device_id,
        )
        db.commit()

        logger.info(f"Registered new device: {device_id}")

        return {
            "status": "success",
            "device_id": device_id,
            "message": "Device registered successfully"
        }
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/upload")
async def upload_video(
    video: UploadFile = File(...),
    metadata: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload a video/photo with cryptographic verification.

    The metadata JSON should contain:
    - version
    - auth: {device_id, public_key_pem}
    - payload: {video_hash, timestamp, location, incident_tags, source, media_type?, exif_metadata?}
    - signature
    """
    try:
        # Parse metadata
        metadata_dict = json.loads(metadata)

        # Extract components
        device_id = metadata_dict["auth"]["device_id"]
        public_key_pem = metadata_dict["auth"]["public_key_pem"]
        payload = metadata_dict["payload"]
        signature_b64 = metadata_dict["signature"]

        # Step 1: Verify device is registered
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            logger.error(f"Upload rejected: Device not registered - {device_id}")
            raise HTTPException(status_code=403, detail=f"Device not registered: {device_id}")

        # Step 2: Verify public key matches registered key
        stored_key = device.public_key_pem.replace('\\n', '\n').strip()
        provided_key = public_key_pem.replace('\\n', '\n').strip()

        if stored_key != provided_key:
            logger.warning(f"Public key mismatch for device {device_id}")
            raise HTTPException(status_code=403, detail="Public key mismatch")

        # Step 3: Stream file to temp file while computing SHA-256 hash.
        # This caps memory at CHUNK_SIZE regardless of file size.
        CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
        sha256 = hashlib.sha256()
        file_size = 0

        tmp = tempfile.SpooledTemporaryFile(max_size=CHUNK_SIZE)
        try:
            while True:
                chunk = await video.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
                tmp.write(chunk)
                file_size += len(chunk)

            calculated_hash = sha256.hexdigest()

            # Step 4: Verify file hash matches metadata
            if calculated_hash != payload["video_hash"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"File hash mismatch. Expected: {payload['video_hash']}, Got: {calculated_hash}"
                )

            # Step 5: Verify signature
            # Use the exact JSON string that the phone signed (passed as signed_payload),
            # falling back to sorted-keys re-serialization for backward compatibility
            payload_json = metadata_dict.get("signed_payload") or json.dumps(payload, sort_keys=True)
            source = payload.get("source", "unknown")

            try:
                if 'DEVICE:' in public_key_pem or public_key_pem.startswith('-----BEGIN PUBLIC KEY-----\\nREVW'):
                    verification_status = "verified-mvp"
                    logger.info(f"MVP signature accepted for device: {device_id}")
                else:
                    public_key = serialization.load_pem_public_key(public_key_pem.encode())
                    signature_bytes = base64.b64decode(signature_b64)
                    # Verify against raw payload bytes — ECDSA(SHA256) hashes internally
                    public_key.verify(
                        signature_bytes,
                        payload_json.encode(),
                        ec.ECDSA(hashes.SHA256())
                    )
                    # For imported media, mark differently than live capture
                    if source == "upload":
                        verification_status = "signed-upload"
                    else:
                        verification_status = "verified"
                    logger.info(f"ECDSA signature verified for device: {device_id}")
            except InvalidSignature:
                verification_status = "failed"
                logger.warning(f"Signature verification failed for device: {device_id}")
            except Exception as e:
                verification_status = "error-mvp"
                logger.error(f"Signature verification error: {str(e)}")

            # For MVP imported media, mark as signed-upload
            if source == "upload" and verification_status == "verified-mvp":
                verification_status = "signed-upload"

            # Step 6: Store in MinIO (stream from temp file)
            media_type = payload.get("media_type", "video")
            minio_client = get_minio_client()

            # Use different paths for photos vs videos
            folder = "photos" if media_type == "photo" else "videos"
            object_name = f"{folder}/{device_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{video.filename}"

            content_type = video.content_type or ("image/jpeg" if media_type == "photo" else "video/mp4")

            tmp.seek(0)
            await asyncio.to_thread(
                minio_client.put_object,
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
                data=tmp,
                length=file_size,
                content_type=content_type,
            )
        finally:
            tmp.close()

        logger.info(f"Media uploaded to MinIO: {object_name}")

        # Step 7: Store metadata in PostgreSQL
        video_record = Video(
            device_id=device_id,
            object_name=object_name,
            file_hash=calculated_hash,
            timestamp=datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
            latitude=payload["location"]["lat"],
            longitude=payload["location"]["lon"],
            incident_tags=payload.get("incident_tags", []),
            source=source,
            media_type=media_type,
            exif_metadata=payload.get("exif_metadata"),
            verification_status=verification_status,
            metadata_json=metadata_dict,
            uploaded_at=datetime.utcnow()
        )
        db.add(video_record)
        db.commit()
        db.refresh(video_record)

        # Step 8: Audit log
        audit_service.log_event(
            db, "upload",
            {
                "file_hash": calculated_hash,
                "source": source,
                "media_type": media_type,
                "verification_status": verification_status,
            },
            video_id=str(video_record.id),
            device_id=device_id,
        )
        db.commit()

        logger.info(f"Video record created with ID: {video_record.id}")

        # Step 9: Notify bridge service for AI indexing (fire-and-forget)
        if media_type == "video":
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{os.environ.get('BRIDGE_URL', 'http://bridge:8003')}/hooks/video-uploaded",
                        json={
                            "video_id": str(video_record.id),
                            "object_name": object_name,
                        },
                    )
                logger.info(f"Bridge notified for video {video_record.id}")
            except Exception as e:
                logger.warning(f"Bridge notification failed (non-fatal): {e}")

        return {
            "status": "success",
            "video_id": str(video_record.id),
            "verification_status": verification_status,
            "message": "Media uploaded and processed successfully"
        }

    except json.JSONDecodeError as e:
        logger.error(f"Upload error - Invalid JSON: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {str(e)}")
    except KeyError as e:
        logger.error(f"Upload error - Missing field: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error - Unexpected: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def _extract_exif(file_bytes: bytes) -> dict:
    """Extract EXIF metadata from an image file, returning a dict with
    GPS coordinates (lat/lon) and datetime if available."""
    result = {"lat": None, "lon": None, "datetime": None, "raw": None}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        img = Image.open(BytesIO(file_bytes))
        exif_data = img.getexif()
        if not exif_data:
            return result

        raw = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            # Skip binary / non-serialisable values
            if isinstance(value, bytes):
                continue
            raw[tag_name] = str(value)

        result["raw"] = raw

        # DateTime
        dt_str = exif_data.get(306)  # tag 306 = DateTime
        if dt_str:
            result["datetime"] = dt_str

        # GPS info (IFD pointer tag 34853)
        gps_ifd = exif_data.get_ifd(34853)
        if gps_ifd:
            def _dms_to_dd(dms, ref):
                """Convert (degrees, minutes, seconds) + ref to decimal degrees."""
                degrees = float(dms[0])
                minutes = float(dms[1])
                seconds = float(dms[2])
                dd = degrees + minutes / 60 + seconds / 3600
                if ref in ("S", "W"):
                    dd = -dd
                return dd

            lat_data = gps_ifd.get(2)   # GPSLatitude
            lat_ref = gps_ifd.get(1)    # GPSLatitudeRef
            lon_data = gps_ifd.get(4)   # GPSLongitude
            lon_ref = gps_ifd.get(3)    # GPSLongitudeRef

            if lat_data and lat_ref:
                result["lat"] = _dms_to_dd(lat_data, lat_ref)
            if lon_data and lon_ref:
                result["lon"] = _dms_to_dd(lon_data, lon_ref)

    except Exception as e:
        logger.warning(f"EXIF extraction failed (non-fatal): {e}")
    return result


def _detect_media_type(filename: str, content_type: str) -> str:
    """Determine if a file is a video or photo based on name/content-type."""
    ext = os.path.splitext(filename or "")[1].lower()
    photo_exts = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tiff", ".bmp", ".gif"}
    if ext in photo_exts or (content_type and content_type.startswith("image/")):
        return "photo"
    return "video"


@app.post("/bulk-upload")
async def bulk_upload(
    files: list[UploadFile] = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin bulk-uploads multiple videos/photos.

    All files are stored as 'unverified' with source='bulk-upload'.
    EXIF data is extracted when available for GPS location and timestamps.
    Each file is queued for AI indexing.
    """
    results = []
    minio_client = get_minio_client()

    for upload_file in files:
        try:
            # Read file contents and compute hash
            CHUNK_SIZE = 8 * 1024 * 1024
            sha256 = hashlib.sha256()
            file_size = 0
            file_bytes = bytearray()

            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
                file_bytes.extend(chunk)
                file_size += len(chunk)

            if file_size == 0:
                results.append({
                    "filename": upload_file.filename,
                    "status": "error",
                    "detail": "Empty file",
                })
                continue

            file_hash = sha256.hexdigest()
            media_type = _detect_media_type(upload_file.filename, upload_file.content_type)

            # Extract EXIF from images (and attempt on video files too)
            exif = _extract_exif(bytes(file_bytes))

            # Determine location from EXIF (None if unavailable)
            latitude = exif["lat"]
            longitude = exif["lon"]

            # Determine timestamp from EXIF or use current time
            if exif["datetime"]:
                try:
                    # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                    timestamp = datetime.strptime(exif["datetime"], "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()

            # Store in MinIO
            folder = "photos" if media_type == "photo" else "videos"
            object_name = f"{folder}/bulk/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{upload_file.filename}"
            content_type = upload_file.content_type or (
                "image/jpeg" if media_type == "photo" else "video/mp4"
            )

            file_stream = BytesIO(bytes(file_bytes))
            await asyncio.to_thread(
                minio_client.put_object,
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type,
            )

            # Build exif_metadata field for the record
            exif_metadata = exif["raw"] if exif["raw"] else None

            # Create database record — always 'unverified'
            video_record = Video(
                device_id="bulk-upload",
                object_name=object_name,
                file_hash=file_hash,
                timestamp=timestamp,
                latitude=latitude,
                longitude=longitude,
                incident_tags=[],
                source="bulk-upload",
                media_type=media_type,
                exif_metadata=exif_metadata,
                verification_status="unverified",
                metadata_json={
                    "source": "bulk-upload",
                    "uploaded_by": admin.username,
                    "original_filename": upload_file.filename,
                    "exif_location": {"lat": latitude, "lon": longitude}
                        if (exif["lat"] is not None)
                        else None,
                },
                uploaded_at=datetime.utcnow(),
            )
            db.add(video_record)
            db.commit()
            db.refresh(video_record)

            # Audit log
            audit_service.log_event(
                db, "bulk_upload",
                {
                    "file_hash": file_hash,
                    "media_type": media_type,
                    "original_filename": upload_file.filename,
                    "verification_status": "unverified",
                    "has_exif_location": exif["lat"] is not None,
                },
                video_id=str(video_record.id),
                user_id=str(admin.id),
            )
            db.commit()

            # Notify bridge for AI indexing (videos and photos)
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{os.environ.get('BRIDGE_URL', 'http://bridge:8003')}/hooks/video-uploaded",
                        json={
                            "video_id": str(video_record.id),
                            "object_name": object_name,
                        },
                    )
                logger.info(f"Bridge notified for bulk-uploaded {media_type} {video_record.id}")
            except Exception as e:
                logger.warning(f"Bridge notification failed (non-fatal): {e}")

            results.append({
                "filename": upload_file.filename,
                "status": "success",
                "video_id": str(video_record.id),
                "media_type": media_type,
                "verification_status": "unverified",
                "has_exif": exif["raw"] is not None,
                "location": {"lat": latitude, "lon": longitude},
            })

            logger.info(
                f"Bulk upload: {upload_file.filename} -> {video_record.id} "
                f"({media_type}, exif={'yes' if exif['raw'] else 'no'})"
            )

        except Exception as e:
            logger.error(f"Bulk upload error for {upload_file.filename}: {e}", exc_info=True)
            results.append({
                "filename": upload_file.filename,
                "status": "error",
                "detail": str(e),
            })

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")

    return {
        "status": "success" if failed == 0 else "partial" if succeeded > 0 else "error",
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@app.get("/videos")
async def list_videos(
    device_id: Optional[str] = None,
    verified_only: bool = False,
    tags: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    media_type: Optional[str] = None,
    source: Optional[str] = None,
    sort: Optional[str] = "newest",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List uploaded videos with optional filtering."""
    query = db.query(Video).filter(Video.deleted_at == None)

    if device_id:
        query = query.filter(Video.device_id == device_id)

    if verified_only:
        query = query.filter(Video.verification_status == "verified")

    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                query = query.filter(Video.incident_tags.any(tag))

    if category:
        query = query.filter(Video.category == category)

    if media_type:
        query = query.filter(Video.media_type == media_type)

    if source:
        query = query.filter(Video.source == source)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Video.notes.ilike(term),
                Video.location_description.ilike(term),
                Video.device_id.ilike(term),
            )
        )

    total = query.count()

    if sort == "oldest":
        query = query.order_by(Video.uploaded_at.asc())
    else:
        query = query.order_by(Video.uploaded_at.desc())

    query = query.offset(offset).limit(limit)

    videos = query.all()

    return {
        "total": total,
        "count": len(videos),
        "videos": [
            {
                "id": str(v.id),
                "device_id": v.device_id,
                "timestamp": v.timestamp.isoformat(),
                "location": {"lat": v.latitude, "lon": v.longitude} if v.latitude is not None else None,
                "incident_tags": v.incident_tags,
                "source": v.source,
                "media_type": v.media_type,
                "category": v.category,
                "verification_status": v.verification_status,
                "review_status": v.review_status or "pending",
                "uploaded_at": v.uploaded_at.isoformat()
            }
            for v in videos
        ]
    }


@app.get("/videos/{video_id}")
async def get_video_details(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific video."""
    video = db.query(Video).filter(Video.id == video_id, Video.deleted_at == None).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "id": str(video.id),
        "device_id": video.device_id,
        "object_name": video.object_name,
        "file_hash": video.file_hash,
        "timestamp": video.timestamp.isoformat(),
        "location": {"lat": video.latitude, "lon": video.longitude} if video.latitude is not None else None,
        "incident_tags": video.incident_tags,
        "source": video.source,
        "media_type": video.media_type,
        "exif_metadata": video.exif_metadata,
        "verification_status": video.verification_status,
        "category": video.category,
        "location_description": video.location_description,
        "notes": video.notes,
        "annotations_updated_at": video.annotations_updated_at.isoformat() if video.annotations_updated_at else None,
        "review_status": video.review_status or "pending",
        "reviewed_at": video.reviewed_at.isoformat() if video.reviewed_at else None,
        "reviewed_by": video.reviewed_by,
        "uploaded_at": video.uploaded_at.isoformat(),
        "metadata": video.metadata_json
    }


class AnnotationUpdate(BaseModel):
    device_id: str
    category: Optional[str] = None
    location_description: Optional[str] = None
    notes: Optional[str] = None
    incident_tags: Optional[list] = None


@app.put("/videos/{video_id}/annotations")
async def update_annotations(
    video_id: str,
    body: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """Update annotations on a video. Only the owning device can update."""
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.device_id != body.device_id:
        raise HTTPException(status_code=403, detail="Only the recording device can update annotations")

    # Validate category
    if body.category is not None and body.category not in ("interview", "incident", "documentation", "other", ""):
        raise HTTPException(status_code=400, detail="Invalid category")

    old_values = {
        "category": video.category,
        "location_description": video.location_description,
        "notes": video.notes,
        "incident_tags": video.incident_tags,
    }

    video.category = body.category if body.category != "" else None
    video.location_description = body.location_description
    video.notes = body.notes
    if body.incident_tags is not None:
        video.incident_tags = body.incident_tags
    video.annotations_updated_at = datetime.utcnow()
    video.annotations_updated_by = body.device_id
    db.commit()

    audit_service.log_event(
        db, "annotation_update",
        {
            "old": old_values,
            "new": {
                "category": video.category,
                "location_description": video.location_description,
                "notes": video.notes,
                "incident_tags": video.incident_tags,
            },
        },
        video_id=video_id,
        device_id=body.device_id,
    )
    db.commit()

    return {
        "status": "success",
        "message": "Annotations updated",
        "video_id": video_id,
    }


@app.get("/videos/{video_id}/url")
async def get_video_url(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Generate a temporary presigned URL for video playback."""
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        minio_client = get_minio_client()

        url = minio_client.get_presigned_url(
            "GET",
            settings.MINIO_BUCKET,
            video.object_name,
            expires=timedelta(hours=1)
        )

        base = f"{settings.MINIO_EXTERNAL_SCHEME}://{settings.MINIO_EXTERNAL_ENDPOINT}/"
        external_url = url.replace(f"http://{settings.MINIO_ENDPOINT}/", base)
        return {"url": external_url}
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not generate video URL")


# --- Audit Log Endpoints (Feature 4) ---

@app.get("/audit-log")
async def get_audit_log(
    event_type: Optional[str] = None,
    video_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Query the audit log with optional filters."""
    query = db.query(AuditLog)

    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if video_id:
        query = query.filter(AuditLog.video_id == video_id)

    query = query.order_by(AuditLog.sequence_number.desc())
    total = query.count()
    entries = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "entries": [
            {
                "id": str(e.id),
                "sequence_number": e.sequence_number,
                "event_type": e.event_type,
                "video_id": str(e.video_id) if e.video_id else None,
                "device_id": e.device_id,
                "event_data": e.event_data,
                "entry_hash": e.entry_hash,
                "previous_hash": e.previous_hash,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }


@app.get("/audit-log/verify")
async def verify_audit_log(db: Session = Depends(get_db)):
    """Verify the integrity of the entire audit chain."""
    result = audit_service.verify_chain(db)
    return result


@app.get("/export/integrity-report")
async def export_integrity_report(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a full integrity report with chain verification and file fingerprints."""
    chain_verification = audit_service.verify_chain(db)

    videos = (
        db.query(Video)
        .filter(Video.deleted_at == None)
        .order_by(Video.uploaded_at.asc())
        .all()
    )

    files = [
        {
            "id": str(v.id),
            "file_hash": v.file_hash,
            "device_id": v.device_id,
            "object_name": v.object_name,
            "media_type": v.media_type,
            "source": v.source,
            "verification_status": v.verification_status,
            "uploaded_at": v.uploaded_at.isoformat(),
            "timestamp": v.timestamp.isoformat(),
        }
        for v in videos
    ]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "chain_verification": chain_verification,
        "files": files,
        "total_files": len(files),
    }


@app.get("/videos/{video_id}/audit")
async def get_video_audit_trail(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get the audit trail for a specific video."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.video_id == video_id)
        .order_by(AuditLog.sequence_number.asc())
        .all()
    )

    return {
        "video_id": video_id,
        "entries": [
            {
                "id": str(e.id),
                "sequence_number": e.sequence_number,
                "event_type": e.event_type,
                "event_data": e.event_data,
                "entry_hash": e.entry_hash,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }


# --- Auth Endpoints ---

class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    role: str = "staff"


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    password: str


class WebAnnotationUpdate(BaseModel):
    category: Optional[str] = None
    location_description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    incident_tags: Optional[list] = None


@app.post("/auth/login")
async def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Login with username and password, sets httpOnly cookie."""
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    token = create_access_token({"sub": user.username})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,
    )

    user.last_login_at = datetime.utcnow()
    db.commit()

    return {
        "status": "success",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        },
    }


@app.post("/auth/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie("access_token")
    return {"status": "success"}


@app.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }


@app.post("/auth/users")
async def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin creates a new user."""
    if body.role not in ("admin", "staff"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'staff'")

    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=body.role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit_service.log_event(
        db, "user_created",
        {"username": user.username, "role": user.role},
        user_id=str(admin.id),
    )
    db.commit()

    return {
        "status": "success",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        },
    }


@app.get("/auth/users")
async def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin lists all users."""
    users = db.query(User).order_by(User.created_at.asc()).all()
    return {
        "users": [
            {
                "id": str(u.id),
                "username": u.username,
                "display_name": u.display_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]
    }


@app.put("/auth/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin updates a user's role, display_name, or active status."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role is not None:
        if body.role not in ("admin", "staff"):
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'staff'")
        user.role = body.role
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()

    audit_service.log_event(
        db, "user_updated",
        {"target_user": user.username, "changes": body.model_dump(exclude_none=True)},
        user_id=str(admin.id),
    )
    db.commit()

    return {
        "status": "success",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
        },
    }


@app.put("/auth/users/{user_id}/password")
async def reset_user_password(
    user_id: str,
    body: ResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin resets a user's password."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(body.password)
    db.commit()

    audit_service.log_event(
        db, "password_reset",
        {"target_user": user.username},
        user_id=str(admin.id),
    )
    db.commit()

    return {"status": "success", "message": f"Password reset for {user.username}"}


# --- Web Staff/Admin Endpoints ---

@app.put("/videos/{video_id}/annotations/web")
async def update_annotations_web(
    video_id: str,
    body: WebAnnotationUpdate,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff/admin edits annotations on any video via the web UI."""
    video = db.query(Video).filter(Video.id == video_id, Video.deleted_at == None).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if body.category is not None and body.category not in ("interview", "incident", "documentation", "other", ""):
        raise HTTPException(status_code=400, detail="Invalid category")

    old_values = {
        "category": video.category,
        "location_description": video.location_description,
        "latitude": video.latitude,
        "longitude": video.longitude,
        "notes": video.notes,
        "incident_tags": video.incident_tags,
    }

    if body.category is not None:
        video.category = body.category if body.category != "" else None
    if body.location_description is not None:
        video.location_description = body.location_description if body.location_description != "" else None
    if body.latitude is not None:
        video.latitude = body.latitude
    if body.longitude is not None:
        video.longitude = body.longitude
    if body.notes is not None:
        video.notes = body.notes if body.notes != "" else None
    if body.incident_tags is not None:
        video.incident_tags = body.incident_tags

    video.annotations_updated_at = datetime.utcnow()
    video.annotations_updated_by = user.username
    db.commit()

    audit_service.log_event(
        db, "web_annotation_update",
        {
            "old": old_values,
            "new": {
                "category": video.category,
                "location_description": video.location_description,
                "latitude": video.latitude,
                "longitude": video.longitude,
                "notes": video.notes,
                "incident_tags": video.incident_tags,
            },
            "updated_by": user.username,
        },
        video_id=video_id,
        user_id=str(user.id),
    )
    db.commit()

    return {"status": "success", "message": "Annotations updated", "video_id": video_id}


# --- Queue Management Endpoints ---

@app.get("/queue")
async def get_queue(
    review_status: Optional[str] = "pending",
    tags: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    media_type: Optional[str] = None,
    source: Optional[str] = None,
    sort: Optional[str] = "oldest",
    limit: int = 50,
    offset: int = 0,
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Get queue items for review with filtering and sorting."""
    query = db.query(Video).filter(Video.deleted_at == None)

    if review_status:
        query = query.filter(Video.review_status == review_status)

    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                query = query.filter(Video.incident_tags.any(tag))

    if category:
        query = query.filter(Video.category == category)

    if media_type:
        query = query.filter(Video.media_type == media_type)

    if source:
        query = query.filter(Video.source == source)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Video.notes.ilike(term),
                Video.location_description.ilike(term),
                Video.device_id.ilike(term),
            )
        )

    total = query.count()

    if sort == "newest":
        query = query.order_by(Video.uploaded_at.desc())
    elif sort == "oldest":
        query = query.order_by(Video.uploaded_at.asc())
    elif sort == "tag":
        # Sort by number of tags (least tagged first, so uncategorized items come first)
        query = query.order_by(
            sa_func.coalesce(sa_func.array_length(Video.incident_tags, 1), 0).asc(),
            Video.uploaded_at.asc(),
        )
    else:
        query = query.order_by(Video.uploaded_at.asc())

    query = query.offset(offset).limit(limit)
    videos = query.all()

    return {
        "total": total,
        "count": len(videos),
        "videos": [
            {
                "id": str(v.id),
                "device_id": v.device_id,
                "timestamp": v.timestamp.isoformat(),
                "location": {"lat": v.latitude, "lon": v.longitude} if v.latitude is not None else None,
                "incident_tags": v.incident_tags or [],
                "source": v.source,
                "media_type": v.media_type,
                "category": v.category,
                "location_description": v.location_description,
                "notes": v.notes,
                "verification_status": v.verification_status,
                "review_status": v.review_status or "pending",
                "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None,
                "reviewed_by": v.reviewed_by,
                "uploaded_at": v.uploaded_at.isoformat(),
            }
            for v in videos
        ],
    }


@app.get("/queue/stats")
async def get_queue_stats(
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Get queue statistics: counts by review status."""
    rows = (
        db.query(
            Video.review_status,
            sa_func.count().label("cnt"),
        )
        .filter(Video.deleted_at == None)
        .group_by(Video.review_status)
        .all()
    )

    stats = {"pending": 0, "reviewed": 0, "flagged": 0}
    for row in rows:
        status = row.review_status or "pending"
        if status in stats:
            stats[status] += row.cnt
        else:
            stats["pending"] += row.cnt

    stats["total"] = sum(stats.values())

    return stats


class ReviewUpdate(BaseModel):
    review_status: str  # "reviewed" or "flagged" or "pending"


@app.put("/videos/{video_id}/review")
async def update_review_status(
    video_id: str,
    body: ReviewUpdate,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Mark a video as reviewed, flagged, or reset to pending. Tracked in audit log."""
    if body.review_status not in ("pending", "reviewed", "flagged"):
        raise HTTPException(status_code=400, detail="review_status must be 'pending', 'reviewed', or 'flagged'")

    video = db.query(Video).filter(Video.id == video_id, Video.deleted_at == None).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    old_status = video.review_status or "pending"

    video.review_status = body.review_status
    if body.review_status in ("reviewed", "flagged"):
        video.reviewed_at = datetime.utcnow()
        video.reviewed_by = user.username
    else:
        video.reviewed_at = None
        video.reviewed_by = None

    db.commit()

    audit_service.log_event(
        db, "queue_review",
        {
            "old_status": old_status,
            "new_status": body.review_status,
            "reviewed_by": user.username,
        },
        video_id=video_id,
        user_id=str(user.id),
    )
    db.commit()

    return {
        "status": "success",
        "video_id": video_id,
        "review_status": body.review_status,
        "reviewed_by": user.username,
    }


class DeleteTagRequest(BaseModel):
    tag: str


@app.delete("/tags")
async def delete_tag(
    body: DeleteTagRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin removes a tag from all videos (e.g. to fix typos)."""
    tag = body.tag.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")

    # Find all videos that have this tag
    videos = (
        db.query(Video)
        .filter(Video.deleted_at == None, Video.incident_tags.any(tag))
        .all()
    )

    count = 0
    for v in videos:
        if tag in v.incident_tags:
            v.incident_tags = [t for t in v.incident_tags if t != tag]
            count += 1

    # Also remove from the tags table
    db.query(Tag).filter(Tag.name == tag).delete()
    db.commit()

    audit_service.log_event(
        db, "tag_deleted",
        {"tag": tag, "videos_affected": count, "deleted_by": admin.username},
        user_id=str(admin.id),
    )
    db.commit()

    return {"status": "success", "tag": tag, "videos_affected": count}


# --- Geocode Proxy (for address autocomplete) ---

@app.get("/geocode/search")
async def geocode_search(
    q: str,
    _user: User = Depends(require_staff),
):
    """Proxy address lookup to OpenStreetMap Nominatim for location autocomplete."""
    if not q or len(q.strip()) < 3:
        return {"results": []}

    async with httpx.AsyncClient(timeout=5.0) as client:
        params = {
            "q": q.strip(),
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 6,
        }
        country_codes = os.environ.get("GEOCODE_COUNTRY_CODES", "")
        if country_codes:
            params["countrycodes"] = country_codes
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={
                "User-Agent": "OpenTestimony/1.0",
                "Accept-Language": "en",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = [
        {
            "display_name": item["display_name"],
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "type": item.get("type", ""),
            "importance": item.get("importance", 0),
        }
        for item in data
    ]
    return {"results": results}


@app.delete("/videos/{video_id}")
async def delete_video(
    video_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin soft-deletes a video."""
    video = db.query(Video).filter(Video.id == video_id, Video.deleted_at == None).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video.deleted_at = datetime.utcnow()
    video.deleted_by = admin.id
    db.commit()

    audit_service.log_event(
        db, "video_deleted",
        {"video_id": video_id, "deleted_by": admin.username},
        video_id=video_id,
        user_id=str(admin.id),
    )
    db.commit()

    return {"status": "success", "message": "Video deleted", "video_id": video_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
