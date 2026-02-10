# Changelog

All notable changes to this project will be documented in this file.

## [0.3.1] - 2026-01-31

### Security
- **Secure video URLs**: Video playback and streaming no longer expose filesystem paths in the browser or in URLs.
  - Player and stream URLs use signed tokens instead of file paths, so users cannot guess or tamper with URLs to access files outside the indexed video set.
  - Only videos that appear in the index (frame or transcript metadata) can be streamed; tokens are HMAC-signed and validated server-side.
  - Optional: set `VIDEO_TOKEN_SECRET` in the environment for stable tokens across server restarts; otherwise a random secret is used per run and old links stop working after restart.

### Changed
- **Stream URL format**: Stream endpoint is now `GET /stream_video/{start_ms}?t={token}` (token in query) so nginx and other proxies do not mishandle long path segments or treat the request as a static file.
- **Player URL format**: Player page uses `video_token`, `video_start_milliseconds`, and optional `filename` (display only) query parameters.

### Documentation
- **README**: Added "Deployment behind nginx" section with example proxy config so `/stream_video/` and the app are correctly forwarded to the FastAPI backend.

## [0.3.0] - 2026-01-27

### Added
- **Video Tagging System**: Comprehensive tagging functionality for organizing and categorizing videos
  - Add tags to videos directly from search results
  - Tags are persisted in `video_tags.json` and automatically loaded on server startup
  - Tag dropdown with existing tags for quick selection
  - Tags displayed in all search results (visual and transcript searches)
- **Assets Support**: Added `/assets` endpoint for serving logo and other static assets
- **Enhanced UI**: Improved styling with better dark mode support and modern design

### Changed
- **Rebranding**: Project rebranded from "Video Indexer" to "Open Testimony" with incident-focused branding
  - Updated app name in `Info.plist` to "Open Testimony"
  - Updated server description to "Open Testimony - Video Search Server"
  - Updated UI titles and branding throughout templates
- **UI Improvements**: Enhanced search interface with better visual hierarchy and styling
  - Improved tag display and management interface
  - Better dark mode color scheme and transitions

## [0.2.1] - 2026-01-17

### Fixed
- Fixed an `UnboundLocalError` in `video_search_server_transcode.py` where `temp_upload_dir` was being incorrectly redefined as a local variable during file-based visual searches.

## [0.2.0] - 2026-01-16

### Added
- **Filename Indexing**: Video filenames are now automatically indexed into the text search index. This allows searching for specific videos by name using both exact text matching and semantic search.
- **OpenCLIP Support**: Integrated `open_clip_torch` as an alternative visual indexing model family.
  - Supports LAION/WebLI pretrained models (e.g., `ViT-H-14`).
  - Added embedding normalization for OpenCLIP models.
- **Fast Code Sync**: Added a `sync` stage to `build_and_sign.sh` allowing developers to push python source changes to the built `.app` bundle without a full rebuild or re-signing.
- **Brightness Filtering**: Implemented a brightness check during frame extraction and indexing to automatically skip dark or black frames (e.g., transitions, fade-ins/outs).
- **Advanced UI Options**:
  - Added visual model family and name selection in `launch_app.py`.
  - Added a toggle for audio transcription to allow faster image-only indexing.
  - Added real-time server output piping to the launcher log for easier debugging.
- **Search Debugging**: Added detailed search result logging in `video_search_server_transcode.py` including thumbnail status and brightness stats.

### Changed
- Updated `frame_indexer.py` and `video_search_server_transcode.py` to handle multiple model families (`pe` and `open_clip`).
- Refined the `build_and_sign.sh` script to be more modular and support the new `sync` stage.
- Improved index configuration management to store and validate model family and normalization settings.

### Fixed
- Improved server process handling in the launcher to ensure output is captured on all platforms.
- Fixed a metadata format issue in search results where `timestamp_str` was missing.
