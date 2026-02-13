"""Face detection, embedding, and clustering using InsightFace (SCRFD + ArcFace) and HDBSCAN.

This module provides:
  - detect_and_embed_faces(): Run face detection + embedding on extracted frames
  - run_full_clustering(): Full HDBSCAN re-cluster over all face embeddings
  - assign_faces_incremental(): Assign new faces to nearest existing cluster
"""
import logging
import os
from datetime import datetime

import numpy as np
from PIL import Image
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from models import FaceCluster, FaceDetection

logger = logging.getLogger(__name__)

# Cached InsightFace app instance (loaded once)
_face_app = None


def _get_face_app():
    """Return a cached InsightFace FaceAnalysis app (loaded once, reused)."""
    global _face_app
    if _face_app is not None:
        return _face_app

    from insightface.app import FaceAnalysis

    logger.info(f"Loading InsightFace model: {settings.FACE_MODEL_NAME}")
    app = FaceAnalysis(
        name=settings.FACE_MODEL_NAME,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    # det_size controls the internal detection resolution
    # 640x640 is the standard; smaller = faster but misses small faces
    app.prepare(ctx_id=0 if settings.DEVICE == "cuda" else -1, det_size=(640, 640))
    _face_app = app
    logger.info("InsightFace model loaded successfully")
    return app


def detect_and_embed_faces(
    video_id,
    all_frames,
    db: Session,
):
    """Detect faces in extracted frames, generate embeddings, save face thumbnails.

    Args:
        video_id: UUID of the video being indexed.
        all_frames: List of (frame_num, timestamp_ms, pil_image) tuples
                    (same format as extract_frames output).
        db: SQLAlchemy session.

    Returns:
        Number of faces detected and stored.
    """
    app = _get_face_app()
    face_count = 0
    thumb_dir = os.path.join(settings.FACE_THUMBNAIL_DIR, str(video_id))
    os.makedirs(thumb_dir, exist_ok=True)

    for frame_num, timestamp_ms, pil_img in all_frames:
        # InsightFace expects BGR numpy array
        img_rgb = np.array(pil_img)
        img_bgr = img_rgb[:, :, ::-1]

        faces = app.get(img_bgr)

        for i, face in enumerate(faces):
            # Filter by detection confidence
            if face.det_score < settings.FACE_DETECTION_THRESHOLD:
                continue

            # Get bounding box (cast to Python int — numpy.int64 breaks psycopg2)
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

            # Clamp to image bounds
            h, w = int(img_rgb.shape[0]), int(img_rgb.shape[1])
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            # Skip tiny faces
            face_w = x2 - x1
            face_h = y2 - y1
            if face_w < settings.FACE_MIN_SIZE or face_h < settings.FACE_MIN_SIZE:
                continue

            # Get face embedding (512-dim, already normalized by InsightFace)
            embedding = face.normed_embedding
            if embedding is None:
                continue

            # Save cropped face thumbnail
            thumb_name = f"{timestamp_ms}_{i}.jpg"
            thumb_path = os.path.join(thumb_dir, thumb_name)
            try:
                face_crop = pil_img.crop((x1, y1, x2, y2))
                face_crop = face_crop.resize((112, 112), Image.LANCZOS)
                face_crop.save(thumb_path, "JPEG", quality=80)
            except Exception as e:
                logger.warning(f"Failed to save face thumbnail: {e}")
                thumb_name = None

            db.add(FaceDetection(
                video_id=video_id,
                frame_num=frame_num,
                timestamp_ms=timestamp_ms,
                bbox_x1=x1, bbox_y1=y1,
                bbox_x2=x2, bbox_y2=y2,
                detection_score=float(face.det_score),
                embedding=embedding.tolist(),
                thumbnail_path=thumb_name,
            ))
            face_count += 1

        # Flush every 50 frames to keep memory bounded
        if frame_num % 50 == 0 and face_count > 0:
            db.flush()

    if face_count > 0:
        db.flush()

    logger.info(f"Detected {face_count} faces in {len(all_frames)} frames for {video_id}")
    return face_count


def assign_faces_incremental(video_id, db: Session):
    """Assign newly detected faces to existing clusters based on centroid distance.

    For each unassigned face in the given video, compute cosine similarity
    to all existing cluster centroids. If the best match exceeds the threshold,
    assign it. Otherwise leave it unassigned (will be picked up on next full re-cluster).

    Returns the number of faces assigned.
    """
    # Get unassigned faces for this video
    unassigned = (
        db.query(FaceDetection)
        .filter(
            FaceDetection.video_id == video_id,
            FaceDetection.cluster_id.is_(None),
            FaceDetection.embedding.isnot(None),
        )
        .all()
    )

    if not unassigned:
        return 0

    # Get all existing clusters with centroids
    clusters = db.query(FaceCluster).filter(FaceCluster.centroid.isnot(None)).all()

    if not clusters:
        logger.info(f"No existing clusters — skipping incremental assignment for {video_id}")
        return 0

    # Build centroid matrix
    cluster_ids = [c.id for c in clusters]
    centroid_matrix = np.array([c.centroid for c in clusters])  # (K, 512)
    # Normalize centroids
    norms = np.linalg.norm(centroid_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    centroid_matrix = centroid_matrix / norms

    assigned_count = 0
    threshold = settings.FACE_SIMILARITY_THRESHOLD

    for face in unassigned:
        face_emb = np.array(face.embedding)
        norm = np.linalg.norm(face_emb)
        if norm == 0:
            continue
        face_emb = face_emb / norm

        # Cosine similarity = dot product of normalized vectors
        similarities = centroid_matrix @ face_emb  # (K,)
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])

        # Convert cosine similarity to cosine distance for comparison
        # Higher similarity = lower distance. Threshold is a distance threshold.
        # similarity > (1 - threshold) means close enough to assign.
        if best_sim > (1.0 - threshold):
            face.cluster_id = cluster_ids[best_idx]
            assigned_count += 1

    if assigned_count > 0:
        db.flush()
        # Update cluster counts
        _update_cluster_counts(db)

    logger.info(f"Incremental assignment: {assigned_count}/{len(unassigned)} faces assigned for {video_id}")
    return assigned_count


def run_full_clustering(db: Session):
    """Run HDBSCAN clustering over ALL face embeddings in the database.

    1. Load all face embeddings
    2. Run HDBSCAN
    3. Update face_detections.cluster_id
    4. Rebuild face_clusters table with new cluster info

    Returns (num_clusters, num_noise) tuple.
    """
    from sklearn.cluster import HDBSCAN

    logger.info("Starting full face re-clustering...")

    # Load all face embeddings
    faces = (
        db.query(FaceDetection.id, FaceDetection.embedding)
        .filter(FaceDetection.embedding.isnot(None))
        .all()
    )

    if len(faces) < settings.FACE_CLUSTER_MIN_SIZE:
        logger.info(f"Only {len(faces)} faces — need at least {settings.FACE_CLUSTER_MIN_SIZE} for clustering")
        return (0, len(faces))

    face_ids = [f.id for f in faces]
    embeddings = np.array([f.embedding for f in faces])

    # Normalize embeddings for cosine distance
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms

    logger.info(f"Clustering {len(embeddings)} face embeddings...")

    clusterer = HDBSCAN(
        min_cluster_size=settings.FACE_CLUSTER_MIN_SIZE,
        metric="euclidean",
        # Using euclidean on L2-normalized vectors approximates cosine distance
        cluster_selection_method="eom",  # Excess of Mass — good for varying density
    )
    labels = clusterer.fit_predict(embeddings)

    num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    num_noise = int(np.sum(labels == -1))
    logger.info(f"HDBSCAN found {num_clusters} clusters, {num_noise} noise points")

    # Clear existing cluster assignments and clusters
    db.query(FaceDetection).update({FaceDetection.cluster_id: None})
    db.query(FaceCluster).delete()
    db.flush()

    # Assign cluster labels to face detections
    for i, face_id in enumerate(face_ids):
        label = int(labels[i])
        if label == -1:
            continue
        db.query(FaceDetection).filter(FaceDetection.id == face_id).update(
            {FaceDetection.cluster_id: label}
        )

    db.flush()

    # Create FaceCluster entries with centroids and representative faces
    for cluster_id in range(num_clusters):
        mask = labels == cluster_id
        cluster_embeddings = embeddings[mask]
        cluster_face_ids = [face_ids[i] for i in range(len(face_ids)) if labels[i] == cluster_id]

        # Compute centroid
        centroid = np.mean(cluster_embeddings, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        # Find representative face (closest to centroid = highest quality representative)
        similarities = cluster_embeddings @ centroid
        best_idx = int(np.argmax(similarities))
        representative_id = cluster_face_ids[best_idx]

        # Count distinct videos
        video_count = (
            db.query(func.count(func.distinct(FaceDetection.video_id)))
            .filter(FaceDetection.cluster_id == cluster_id)
            .scalar()
        )

        db.add(FaceCluster(
            id=cluster_id,
            representative_face_id=representative_id,
            face_count=len(cluster_face_ids),
            video_count=video_count,
            centroid=centroid.tolist(),
        ))

    db.flush()
    db.commit()
    logger.info(f"Full re-clustering complete: {num_clusters} clusters, {num_noise} noise")
    return (num_clusters, num_noise)


def _update_cluster_counts(db: Session):
    """Recalculate face_count and video_count for all clusters."""
    clusters = db.query(FaceCluster).all()
    for cluster in clusters:
        cluster.face_count = (
            db.query(func.count(FaceDetection.id))
            .filter(FaceDetection.cluster_id == cluster.id)
            .scalar()
        )
        cluster.video_count = (
            db.query(func.count(func.distinct(FaceDetection.video_id)))
            .filter(FaceDetection.cluster_id == cluster.id)
            .scalar()
        )
        cluster.updated_at = datetime.utcnow()
    db.flush()
