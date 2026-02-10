# Open Testimony: Incident Video Search & Indexing

Open Testimony is a powerful video search and indexing tool focused on searching incident videos and organizing them with tags. It combines multiple state-of-the-art AI models for comprehensive video content search:

- **Visual Search**: Meta's Perception Model (Core) and OpenCLIP for understanding visual content and cross-modal search
- **Transcript Search**: Qwen3-Embedding-8B for high-quality semantic search over spoken content (transcribed using whisper and its large v3 model)

## Demo

Watch a quick demo of Open Testimony in action:

<video src="https://github.com/user-attachments/assets/8efd2c6c-dd3b-415f-bd5e-193adcdc5b7e" controls="controls" style="max-width: 730px;">
</video>

## Features

### Visual Content Search
- Text-to-video search using Meta's Perception Model or OpenCLIP
- Image-to-video search for finding similar visual content
- Frame extraction and intelligent indexing
- Cross-modal understanding between text and visual content
- Instant visual results with thumbnails

### Transcript Search
- Semantic search using Qwen3-Embedding-8B embeddings
- Exact text matching for precise queries
- Filename search: Find videos by their file names
- Multi-language transcript support
- Automatic video transcription (optional)
- Time-aligned transcript results

### User Interface & Tagging
- **Open Testimony** branding with incident-focused UI
- **Tagging System**: Comprehensive video tagging for organizing evidence
  - Add tags directly from search results
  - Persistent tag storage (automatically saved and loaded)
  - Tag dropdown with existing tags for quick selection
  - Tags visible in all search results for easy identification
- Modern, responsive UI with dark mode support
- Instant search results with visual previews
- Video playback starting at matched frames/segments
- M3U playlist generation for search results

### Technical Features
- FAISS vector similarity search
- FP16 support for efficient memory usage
- Automatic video transcoding when needed
- Intelligent frame filtering (skips dark/black frames)
- Configurable model parameters
- Multi-threaded processing

### Security (video URLs)
- **No path exposure**: Player and stream URLs use signed tokens, not filesystem paths. Only indexed videos can be played; path traversal or guessing URLs to read other files is not possible.
- **Token format**: Tokens are HMAC-signed and validated server-side. Set `VIDEO_TOKEN_SECRET` in the environment for stable links across restarts.
- **Stream URL**: `GET /stream_video/{start_ms}?t={token}` — token in query so reverse proxies (e.g. nginx) do not treat the request as a static file.

Quickest way to try it out is to download the OpenTestimony-mac.zip file from the Releases page and run that.  You might need to hop through security hoops to launch it despite the fact that I signed and notarized it, but hopefully that isn't too much of a pain.

You will pick the directory tree of videos you want to index and then click 'Start' and it will run for a while indexing.  If you have less than 64GB or RAM, I would check the 'fp16' box.  The accuracy should be about the same and use less RAM.  When indexing is done, you can hit the local webserver at http://127.0.0.1:8002 and search away!

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/VideoIndexer-project.git
cd VideoIndexer-project
```

2. Create and activate conda environment:
```bash
conda env create -f environment.yml
conda activate video-indexer
```

3. Install additional dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Process videos to extract frames and build the visual search index:
```bash
cd src
# Extract frames (add --fp16 to reduce memory usage)
python frame_extractor.py /path/to/your/videos --output-dir video_index_output

# Build visual search index (add --fp16 for reduced memory)
python frame_indexer.py --input-dir video_index_output

# Optional: use OpenCLIP (LAION/WebLI) for visual indexing
python frame_indexer.py --input-dir video_index_output \
  --model-family open_clip \
  --model-name ViT-H-14 \
  --openclip-pretrained laion2b_s32b_b79k
```

2. Generate and index transcripts:
```bash
# Generate transcripts (add --fp16 for reduced memory)
python transcript_extractor_pywhisper.py /path/to/your/videos --output-dir video_index_output

# Build transcript search index (add --fp16 for reduced memory)
python transcript_indexer.py --input-dir video_index_output
```

3. Start the search server:
```bash
cd src
# Add --fp16 flag to reduce memory usage during search
python video_search_server_transcode.py --fp16
```

4. Open http://localhost:8002 in your browser

### Memory Usage Tips

- The `--fp16` flag can be used with most components to reduce memory usage by about 50%
- For large video collections, using FP16 is recommended
- Memory usage is highest during initial indexing and reduces for search operations
- If you encounter memory issues:
  1. Use the `--fp16` flag
  2. Process videos in smaller batches
  3. Close other memory-intensive applications

## Building macOS App

### Prerequisites

1. Copy the credentials template and fill in your Apple Developer details:
```bash
cp store_credentials_template.sh store_credentials.sh
chmod +x store_credentials.sh
# Edit store_credentials.sh with your details
./store_credentials.sh
```

2. Build the app:
```bash
# Full build (slow)
./build_and_sign.sh build

# Quick code sync (for developers)
./build_and_sign.sh sync

    # Sign the app
    ./build_and_sign.sh sign
    ```

    The built app will be in `./build/OpenTestimony.app`

## Configuration

### Model Configuration
- `index_config.json`: Configure visual search model and embedding settings
- Visual models:
  - Meta Perception (default): `--model-family pe` with `PE-Core-*` models
  - OpenCLIP (LAION/WebLI): `--model-family open_clip` with `--model-name` and `--openclip-pretrained`
- `transcript_index_config.json`: Configure transcript search settings
- Command line arguments for frame extraction and indexing (see --help)

### Performance Tuning
- Use `--fp16` flag for reduced memory usage
- Adjust frame extraction rate for storage/accuracy tradeoff
- Configure FAISS index type for speed/accuracy tradeoff
- Set maximum result thresholds for faster searches

### Deployment behind nginx (or ngrok → nginx)

If the app is behind nginx (e.g. `opentestimony.ngrok.app` → nginx → FastAPI), **nginx must proxy all app paths to the backend**. A 404 from nginx means the request never reached the app.

Ensure nginx forwards the app and the stream endpoint. Example:

```nginx
location / {
    proxy_pass http://127.0.0.1:8002;   # or your FastAPI upstream
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;   # recommended for /stream_video
}
```

If you use a more specific `location`, include one that covers the app and streaming:

```nginx
location /stream_video/ {
    proxy_pass http://127.0.0.1:8002;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_buffering off;
}
location / {
    proxy_pass http://127.0.0.1:8002;
    # ... other headers
}
```

Then reload nginx (`sudo nginx -s reload` or equivalent). To confirm the app itself works, test locally:  
`curl -I "http://127.0.0.1:8002/stream_video/57000?t=YOUR_TOKEN"` (use a real token from a search result).

## License

This project is licensed under the Apache License - see the LICENSE file for details.

## Acknowledgments

- [Meta's Perception Model (Core)](https://github.com/facebookresearch/perception_models) for visual understanding
- [OpenCLIP](https://github.com/mlfoundations/open_clip) for additional visual model support
- [Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B) for semantic text understanding
- [FAISS](https://github.com/facebookresearch/faiss) for efficient similarity search
- [FFmpeg](https://ffmpeg.org/) for video processing 
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) for multi-lingual transcription
