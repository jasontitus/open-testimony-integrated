"""SQLAlchemy models for the AI Search Bridge Service (pgvector tables)."""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
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
    frame_count = Column(Integer, nullable=True)
    segment_count = Column(Integer, nullable=True)
    caption_count = Column(Integer, nullable=True)
    clip_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at = Column(DateTime(timezone=True), nullable=True)
