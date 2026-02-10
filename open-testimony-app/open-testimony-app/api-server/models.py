"""SQLAlchemy models for the Open Testimony database"""
from sqlalchemy import Column, String, DateTime, Float, JSON, Text
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
    
    # Verification
    verification_status = Column(String(20), nullable=False, index=True)  # verified, failed, error
    
    # Full metadata storage
    metadata_json = Column(JSON, nullable=False)
    
    # System timestamps
    uploaded_at = Column(DateTime, nullable=False, index=True)
