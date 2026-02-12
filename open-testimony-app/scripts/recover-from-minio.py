#!/usr/bin/env python3
"""Recover video metadata rows from MinIO files after an accidental DB wipe.

Scans MinIO for all video/photo objects and recreates the corresponding
rows in the videos table with as much metadata as can be inferred from
file paths and names.

Usage:
    python3 scripts/recover-from-minio.py          # dry run
    python3 scripts/recover-from-minio.py --apply   # actually insert rows
"""
import argparse
import hashlib
import os
import sys
import uuid
from datetime import datetime

try:
    import psycopg2
except ImportError:
    print("ERROR: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

try:
    from minio import Minio
except ImportError:
    print("ERROR: pip install minio", file=sys.stderr)
    sys.exit(1)


def get_minio():
    return Minio(
        os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.environ.get("MINIO_ACCESS_KEY", "admin"),
        secret_key=os.environ.get("MINIO_SECRET_KEY", "supersecret"),
        secure=False,
    )


def get_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "opentestimony"),
        user=os.environ.get("DB_USER", "admin"),
        password=os.environ.get("DB_PASSWORD", "admin"),
    )


def parse_timestamp_from_name(name):
    """Try to extract a timestamp from filenames like 20260211_065543_..."""
    try:
        parts = os.path.basename(name).split("_")
        date_str = parts[0]
        time_str = parts[1]
        return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
    except (IndexError, ValueError):
        return datetime.utcnow()


def detect_media_type(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
        return "photo"
    return "video"


def main():
    p = argparse.ArgumentParser(description="Recover video rows from MinIO")
    p.add_argument("--apply", action="store_true", help="Actually insert rows (default: dry run)")
    args = p.parse_args()

    mc = get_minio()
    bucket = os.environ.get("MINIO_BUCKET", "opentestimony-videos")

    objects = list(mc.list_objects(bucket, prefix="videos/", recursive=True))
    objects += list(mc.list_objects(bucket, prefix="photos/", recursive=True))

    print(f"Found {len(objects)} objects in MinIO")

    conn = get_db()
    cur = conn.cursor()

    # Check what already exists
    cur.execute("SELECT object_name FROM videos")
    existing = {row[0] for row in cur.fetchall()}

    inserted = 0
    skipped = 0

    for obj in objects:
        object_name = obj.object_name
        if object_name in existing:
            skipped += 1
            continue

        # Parse path: videos/bulk/filename.mp4 or videos/<device_id>/filename.mp4
        parts = object_name.split("/")
        if len(parts) < 3:
            print(f"  SKIP (unexpected path): {object_name}")
            continue

        prefix = parts[0]      # "videos" or "photos"
        subfolder = parts[1]   # "bulk" or device_id
        filename = "/".join(parts[2:])

        timestamp = parse_timestamp_from_name(filename)
        media_type = detect_media_type(filename)
        source = "upload" if subfolder == "bulk" else "live"
        device_id = "bulk-upload" if subfolder == "bulk" else subfolder

        video_id = str(uuid.uuid4())

        print(f"  {'INSERT' if args.apply else 'WOULD INSERT'}: {object_name}")
        print(f"    id={video_id}, device={device_id}, ts={timestamp}, type={media_type}, source={source}")

        if args.apply:
            cur.execute("""
                INSERT INTO videos (
                    id, device_id, object_name, file_hash, timestamp,
                    latitude, longitude, verification_status, metadata_json,
                    uploaded_at, source, media_type, review_status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                video_id, device_id, object_name, "recovered-" + "0" * 55, timestamp,
                0.0, 0.0, "unverified", "{}",
                timestamp, source, media_type, "pending",
            ))
            inserted += 1

    if args.apply:
        conn.commit()
        print(f"\nRecovery complete: {inserted} inserted, {skipped} already existed")
    else:
        print(f"\nDry run: {len(objects) - skipped} would be inserted, {skipped} already exist")
        print("Run with --apply to actually insert rows")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
