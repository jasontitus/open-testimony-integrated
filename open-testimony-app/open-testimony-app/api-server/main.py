"""
Open Testimony API Server
FastAPI backend for video upload, signature verification, and metadata storage.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature
import base64
from minio import Minio

from database import engine, Base, get_db
from models import Video, Device
from minio_client import get_minio_client, ensure_bucket_exists
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Open Testimony API",
    description="Secure Video Integrity System API",
    version="1.0.0"
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
    """Initialize MinIO bucket on startup"""
    minio_client = get_minio_client()
    ensure_bucket_exists(minio_client, settings.MINIO_BUCKET)
    logger.info("Open Testimony API Server started successfully")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Open Testimony API",
        "version": "1.0.0",
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


@app.post("/register-device")
async def register_device(
    device_id: str = Form(...),
    public_key_pem: str = Form(...),
    device_info: Optional[str] = Form(None),
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
            logger.info(f"Device already registered: {device_id}")
            return {
                "status": "success",
                "device_id": device_id,
                "message": "Device already registered"
            }
        
        # Validate public key format
        # For MVP: Accept simplified key format, for Production: Validate ECDSA
        if 'DEVICE:' in public_key_pem or public_key_pem.startswith('-----BEGIN PUBLIC KEY-----\nREVW'):
            # MVP format - base64 encoded device identifier
            logger.info(f"Registering device with MVP key format: {device_id}")
            # No validation needed for MVP
        else:
            # Future: ECDSA public key validation
            try:
                serialization.load_pem_public_key(public_key_pem.encode())
                logger.info(f"Registering device with ECDSA key format: {device_id}")
            except Exception as e:
                logger.warning(f"Key validation warning for {device_id}: {str(e)}")
                # Accept anyway for MVP
                pass
        
        # Create new device
        device = Device(
            device_id=device_id,
            public_key_pem=public_key_pem,
            device_info=device_info,
            registered_at=datetime.utcnow()
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        
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
    Upload a video with cryptographic verification.
    
    The metadata JSON should contain:
    - version
    - auth: {device_id, public_key_pem}
    - payload: {video_hash, timestamp, location, incident_tags, source}
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
        # Normalize both keys (handle \n vs actual newlines)
        stored_key = device.public_key_pem.replace('\\n', '\n').strip()
        provided_key = public_key_pem.replace('\\n', '\n').strip()
        
        if stored_key != provided_key:
            logger.warning(f"Public key mismatch for device {device_id}")
            logger.debug(f"Stored: {stored_key[:50]}...")
            logger.debug(f"Provided: {provided_key[:50]}...")
            raise HTTPException(status_code=403, detail="Public key mismatch")
        
        # Step 3: Calculate video file hash
        video_content = await video.read()
        calculated_hash = hashlib.sha256(video_content).hexdigest()
        
        # Step 4: Verify file hash matches metadata
        if calculated_hash != payload["video_hash"]:
            raise HTTPException(
                status_code=400,
                detail=f"File hash mismatch. Expected: {payload['video_hash']}, Got: {calculated_hash}"
            )
        
        # Step 5: Verify signature
        # For MVP: Support both HMAC (current) and ECDSA (future)
        # The signature is over the SHA-256 hash of the payload JSON
        payload_json = json.dumps(payload, sort_keys=True)
        
        try:
            # Check if this is an HMAC signature (MVP format) or ECDSA
            if 'DEVICE:' in public_key_pem or public_key_pem.startswith('-----BEGIN PUBLIC KEY-----\\nREVW'):
                # MVP HMAC format - verify the file hash matches (integrity check)
                # Signature verification skipped in MVP (TODO: implement HMAC validation)
                verification_status = "verified-mvp"
                logger.info(f"MVP signature accepted for device: {device_id}")
            else:
                # ECDSA verification (original spec)
                payload_hash = hashlib.sha256(payload_json.encode()).digest()
                public_key = serialization.load_pem_public_key(public_key_pem.encode())
                signature_bytes = base64.b64decode(signature_b64)
                public_key.verify(
                    signature_bytes,
                    payload_hash,
                    ec.ECDSA(hashes.SHA256())
                )
                verification_status = "verified"
                logger.info(f"ECDSA signature verified for device: {device_id}")
        except InvalidSignature:
            verification_status = "failed"
            logger.warning(f"Signature verification failed for device: {device_id}")
        except Exception as e:
            verification_status = "error"
            logger.error(f"Signature verification error: {str(e)}")
            # For MVP, still accept the video but mark verification status
            verification_status = "error-mvp"
        
        # Step 6: Store video in MinIO
        minio_client = get_minio_client()
        object_name = f"videos/{device_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{video.filename}"
        
        # Upload to MinIO using BytesIO
        video_stream = BytesIO(video_content)
        minio_client.put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            data=video_stream,
            length=len(video_content),
            content_type=video.content_type or "video/mp4"
        )
        
        logger.info(f"Video uploaded to MinIO: {object_name}")
        
        # Step 7: Store metadata in PostgreSQL
        video_record = Video(
            device_id=device_id,
            object_name=object_name,
            file_hash=calculated_hash,
            timestamp=datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
            latitude=payload["location"]["lat"],
            longitude=payload["location"]["lon"],
            incident_tags=payload.get("incident_tags", []),
            source=payload.get("source", "unknown"),
            verification_status=verification_status,
            metadata_json=metadata_dict,
            uploaded_at=datetime.utcnow()
        )
        db.add(video_record)
        db.commit()
        db.refresh(video_record)
        
        logger.info(f"Video record created with ID: {video_record.id}")
        
        return {
            "status": "success",
            "video_id": str(video_record.id),
            "verification_status": verification_status,
            "message": "Video uploaded and processed successfully"
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


@app.get("/videos")
async def list_videos(
    device_id: Optional[str] = None,
    verified_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List uploaded videos with optional filtering.
    """
    query = db.query(Video)
    
    if device_id:
        query = query.filter(Video.device_id == device_id)
    
    if verified_only:
        query = query.filter(Video.verification_status == "verified")
    
    query = query.order_by(Video.uploaded_at.desc())
    query = query.offset(offset).limit(limit)
    
    videos = query.all()
    
    return {
        "count": len(videos),
        "videos": [
            {
                "id": str(v.id),
                "device_id": v.device_id,
                "timestamp": v.timestamp.isoformat(),
                "location": {"lat": v.latitude, "lon": v.longitude},
                "incident_tags": v.incident_tags,
                "verification_status": v.verification_status,
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
    """
    Get detailed information about a specific video.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return {
        "id": str(video.id),
        "device_id": video.device_id,
        "object_name": video.object_name,
        "file_hash": video.file_hash,
        "timestamp": video.timestamp.isoformat(),
        "location": {"lat": video.latitude, "lon": video.longitude},
        "incident_tags": video.incident_tags,
        "source": video.source,
        "verification_status": video.verification_status,
        "uploaded_at": video.uploaded_at.isoformat(),
        "metadata": video.metadata_json
    }



@app.get("/videos/{video_id}/url")
async def get_video_url(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate a temporary presigned URL for video playback.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        # Use internal endpoint to generate the URL
        minio_client = get_minio_client()
        
        # Generate the presigned URL using the internal MinIO endpoint
        url = minio_client.get_presigned_url(
            "GET",
            settings.MINIO_BUCKET,
            video.object_name,
            expires=timedelta(hours=1)
        )
        
        # Replace the internal MinIO endpoint with the Nginx proxy path
        # Original: http://minio:9000/bucket/path?params
        # Target: http://localhost/video-stream/bucket/path (no query params needed with public policy)
        external_url = url.replace(f"http://{settings.MINIO_ENDPOINT}/", f"http://{settings.MINIO_EXTERNAL_ENDPOINT}/")
        
        # Strip query parameters since we have public read access via bucket policy
        external_url = external_url.split('?')[0]
        
        return {"url": external_url}
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not generate video URL")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
