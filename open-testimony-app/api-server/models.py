"""SQLAlchemy models for the Open Testimony database"""
from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from database import Base


class Device(Base):
    """Registered devices with their public keys"""
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(255), unique=True, nullable=False, index=True)
    public_key_pem = Column(Text, nullable=False)
    device_info = Column(String(500), nullable=True)
    registered_at = Column(DateTime, nullable=False)
    last_upload_at = Column(DateTime, nullable=True)
    crypto_version = Column(String(20), default="hmac")


class Video(Base):
    """Uploaded videos with verification metadata"""
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(255), nullable=False, index=True)
    object_name = Column(String(500), nullable=False)  # MinIO object path
    file_hash = Column(String(64), nullable=False)  # SHA-256 hex

    # Temporal and spatial metadata
    timestamp = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Categorization
    incident_tags = Column(ARRAY(String), nullable=True)
    source = Column(String(50), nullable=True)  # "live" or "upload"

    # Media type and EXIF (Feature 1)
    media_type = Column(String(20), default="video")
    exif_metadata = Column(JSON, nullable=True)

    # Verification
    verification_status = Column(String(20), nullable=False, index=True)

    # Full metadata storage
    metadata_json = Column(JSON, nullable=False)

    # Annotations (Feature 2)
    category = Column(String(50), nullable=True)  # "interview" or "incident"
    location_description = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    annotations_updated_at = Column(DateTime, nullable=True)
    annotations_updated_by = Column(String(255), nullable=True)

    # System timestamps
    uploaded_at = Column(DateTime, nullable=False, index=True)

    # Soft delete (web admin)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(UUID(as_uuid=True), nullable=True)


class AuditLog(Base):
    """Immutable hash-chained audit log (Feature 4)"""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_number = Column(Integer, unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), nullable=True)
    device_id = Column(String(255), nullable=True)
    event_data = Column(JSON, nullable=False)
    entry_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)


class User(Base):
    """Web UI users with role-based access"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="staff")  # "admin" or "staff"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
