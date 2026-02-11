"""Integration tests for the bulk upload endpoint (runs against live Docker stack)."""
import os
import tempfile


def test_bulk_upload_requires_auth(api, base_url):
    """Bulk upload without auth should return 401."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(512))
    try:
        with open(path, "rb") as f:
            r = api.post(
                f"{base_url}/bulk-upload",
                files=[("files", ("test.mp4", f, "video/mp4"))],
            )
        assert r.status_code == 401
    finally:
        os.remove(path)


def test_bulk_upload_requires_admin(staff_session, base_url):
    """Staff users cannot use bulk upload."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(512))
    try:
        with open(path, "rb") as f:
            r = staff_session.post(
                f"{base_url}/bulk-upload",
                files=[("files", ("test.mp4", f, "video/mp4"))],
            )
        assert r.status_code == 403
    finally:
        os.remove(path)


def test_bulk_upload_single_video(admin_session, base_url):
    """Admin can bulk-upload a single video file."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(1024))
    try:
        with open(path, "rb") as f:
            r = admin_session.post(
                f"{base_url}/bulk-upload",
                files=[("files", ("test_video.mp4", f, "video/mp4"))],
            )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        assert data["results"][0]["verification_status"] == "unverified"
        assert data["results"][0]["media_type"] == "video"
    finally:
        os.remove(path)


def test_bulk_upload_single_photo(admin_session, base_url):
    """Admin can bulk-upload a single photo file."""
    fd, path = tempfile.mkstemp(suffix=".jpg")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(512))
    try:
        with open(path, "rb") as f:
            r = admin_session.post(
                f"{base_url}/bulk-upload",
                files=[("files", ("test_photo.jpg", f, "image/jpeg"))],
            )
        assert r.status_code == 200
        data = r.json()
        assert data["succeeded"] == 1
        assert data["results"][0]["verification_status"] == "unverified"
        assert data["results"][0]["media_type"] == "photo"
    finally:
        os.remove(path)


def test_bulk_upload_multiple_files(admin_session, base_url):
    """Admin can upload multiple files at once."""
    paths = []
    try:
        for i in range(3):
            fd, path = tempfile.mkstemp(suffix=".mp4")
            with os.fdopen(fd, "wb") as f:
                f.write(os.urandom(512 + i))
            paths.append(path)

        files = []
        open_handles = []
        for i, p in enumerate(paths):
            fh = open(p, "rb")
            open_handles.append(fh)
            files.append(("files", (f"video_{i}.mp4", fh, "video/mp4")))

        r = admin_session.post(f"{base_url}/bulk-upload", files=files)

        for fh in open_handles:
            fh.close()

        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["succeeded"] == 3
        assert data["failed"] == 0
    finally:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)


def test_bulk_upload_appears_in_video_list(admin_session, base_url):
    """Bulk-uploaded files should appear in the video listing."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(1024))
    try:
        with open(path, "rb") as f:
            r = admin_session.post(
                f"{base_url}/bulk-upload",
                files=[("files", ("listed.mp4", f, "video/mp4"))],
            )
        assert r.status_code == 200
        video_id = r.json()["results"][0]["video_id"]

        # Fetch the video detail
        r2 = admin_session.get(f"{base_url}/videos/{video_id}")
        assert r2.status_code == 200
        detail = r2.json()
        assert detail["verification_status"] == "unverified"
        assert detail["source"] == "bulk-upload"
    finally:
        os.remove(path)


def test_bulk_upload_creates_audit_entry(admin_session, base_url):
    """Bulk upload should create an audit log entry."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(512))
    try:
        with open(path, "rb") as f:
            r = admin_session.post(
                f"{base_url}/bulk-upload",
                files=[("files", ("audited.mp4", f, "video/mp4"))],
            )
        assert r.status_code == 200
        video_id = r.json()["results"][0]["video_id"]

        # Check audit log for the video
        r2 = admin_session.get(f"{base_url}/videos/{video_id}/audit")
        assert r2.status_code == 200
        entries = r2.json()["entries"]
        bulk_entries = [e for e in entries if e["event_type"] == "bulk_upload"]
        assert len(bulk_entries) >= 1
        assert bulk_entries[0]["event_data"]["verification_status"] == "unverified"
    finally:
        os.remove(path)
