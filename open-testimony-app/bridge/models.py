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

Base = declarative_base()


class FrameEmbedding(Base):
    __tablename__ = "frame_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    frame_num = Column(Integer, nullable=False)
    timestamp_ms = Column(Integer, nullable=False)
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))


class TranscriptEmbedding(Base):
    __tablename__ = "transcript_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    segment_text = Column(Text, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    embedding = Column(Vector(4096))
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
    frame_count = Column(Integer, nullable=True)
    segment_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at = Column(DateTime(timezone=True), nullable=True)
