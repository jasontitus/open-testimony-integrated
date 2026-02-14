"""SQLAlchemy models for the AI Search Bridge Service (pgvector tables)."""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

from config import settings

Base = declarative_base()


class FrameEmbedding(Base):
    __tablename__ = "frame_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    frame_num = Column(Integer, nullable=False)
    timestamp_ms = Column(Integer, nullable=False)
    embedding = Column(Vector(settings.VISION_EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class TranscriptEmbedding(Base):
    __tablename__ = "transcript_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    segment_text = Column(Text, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    embedding = Column(Vector(settings.TRANSCRIPT_EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class CaptionEmbedding(Base):
    __tablename__ = "caption_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    frame_num = Column(Integer, nullable=False)
    timestamp_ms = Column(Integer, nullable=False)
    caption_text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.TRANSCRIPT_EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class ClipEmbedding(Base):
    """Vision embedding for a temporal clip window (mean-pooled across frames)."""
    __tablename__ = "clip_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    start_frame = Column(Integer, nullable=False)
    end_frame = Column(Integer, nullable=False)
    num_frames = Column(Integer, nullable=False)
    embedding = Column(Vector(settings.VISION_EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class ActionEmbedding(Base):
    """Text embedding of a temporal action caption for a clip window."""
    __tablename__ = "action_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    start_frame = Column(Integer, nullable=False)
    end_frame = Column(Integer, nullable=False)
    num_frames = Column(Integer, nullable=False)
    action_text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.TRANSCRIPT_EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class SearchQuery(Base):
    """Log of every search query for analytics (no PII stored)."""
    __tablename__ = "search_queries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    search_mode = Column(String(50), nullable=False)  # visual, transcript, combined, etc.
    result_count = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class FaceDetection(Base):
    """Individual face detected in a video frame, with embedding for clustering."""
    __tablename__ = "face_detections"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    frame_num = Column(Integer, nullable=False)
    timestamp_ms = Column(Integer, nullable=False)
    # Bounding box in the original frame (x1, y1, x2, y2)
    bbox_x1 = Column(Integer, nullable=False)
    bbox_y1 = Column(Integer, nullable=False)
    bbox_x2 = Column(Integer, nullable=False)
    bbox_y2 = Column(Integer, nullable=False)
    # Detection confidence from SCRFD
    detection_score = Column(Float, nullable=False)
    # ArcFace embedding (512-dim)
    embedding = Column(Vector(settings.FACE_EMBEDDING_DIM))
    # Cluster assignment (null = unassigned / noise)
    cluster_id = Column(Integer, nullable=True, index=True)
    # Thumbnail filename (relative to FACE_THUMBNAIL_DIR/video_id/)
    thumbnail_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class FaceCluster(Base):
    """A cluster of face detections representing a single person."""
    __tablename__ = "face_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Representative face detection id (best quality face in the cluster)
    representative_face_id = Column(BigInteger, nullable=True)
    # Optional user-assigned label
    label = Column(String(200), nullable=True)
    # Number of faces in this cluster
    face_count = Column(Integer, nullable=False, default=0)
    # Number of distinct videos this person appears in
    video_count = Column(Integer, nullable=False, default=0)
    # Mean embedding for incremental assignment
    centroid = Column(Vector(settings.FACE_EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class VideoIndexStatus(Base):
    __tablename__ = "video_index_status"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    video_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    object_name = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    visual_indexed = Column(Boolean, default=False)
    transcript_indexed = Column(Boolean, default=False)
    caption_indexed = Column(Boolean, default=False)
    clip_indexed = Column(Boolean, default=False)
    face_indexed = Column(Boolean, default=False)
    frame_count = Column(Integer, nullable=True)
    segment_count = Column(Integer, nullable=True)
    caption_count = Column(Integer, nullable=True)
    clip_count = Column(Integer, nullable=True)
    face_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at = Column(DateTime(timezone=True), nullable=True)
