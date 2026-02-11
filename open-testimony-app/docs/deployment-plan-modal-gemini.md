# Deployment Plan: Modal + Gemini API Captioning

## Current Architecture (Local)

```
┌─ Docker Compose ──────────────────────────────────┐
│ nginx → web-ui (React)                            │
│       → api (FastAPI)                             │
│       → bridge (SigLIP + Qwen3-VL + Qwen3-Embed  │
│                 + Whisper, all on one process)     │
│ db (pgvector/pg16)                                │
│ minio (object storage)                            │
└───────────────────────────────────────────────────┘
```

**Problem:** The bridge loads ~36GB of models. Running a GPU instance 24/7
for burst-only video uploads is wasteful.

---

## Proposed Architecture: Split Bridge + API Captioning

### Key Insight

The bridge does two very different things:
1. **Search serving** — encodes a text query (~100-500ms), hits pgvector. Needs
   SigLIP (~1.5GB) and Qwen3-Embedding (~16GB) in memory, but no GPU required.
2. **Video indexing** — extracts frames, generates embeddings, captions, and
   transcriptions. GPU-intensive, but only runs when videos are uploaded.

By replacing local Qwen3-VL captioning with a Gemini API call, we eliminate
16GB of VRAM and the slowest pipeline step.

### Target Architecture

```
┌─ Cloud Run / VM (always-on, CPU, ~$30/mo) ───────┐
│ nginx / LB                                        │
│ ├─ web-ui (static files on CDN)                   │
│ ├─ api-server (FastAPI)                           │
│ └─ search-service (SigLIP + Qwen3-Embedding)      │
│                                                    │
│ Cloud SQL (pgvector/pg16)        ~$50/mo           │
│ Cloud Storage (replaces MinIO)   ~$1/mo            │
└──────────────────┬────────────────────────────────┘
                   │ webhook: POST /index
                   ▼
┌─ Modal (on-demand GPU, scale-to-zero) ────────────┐
│ Index Worker (L4 GPU, 24GB VRAM)                   │
│ ├─ SigLIP SO400M-14     (~1.5 GB)                 │
│ ├─ Qwen3-Embedding-8B   (~16 GB)                  │
│ ├─ Whisper large-v3      (~3 GB, loaded per-job)  │
│ └─ Gemini API calls      (no VRAM needed)          │
│                                                    │
│ Idle 5 min → scales to zero → $0/hr               │
└────────────────────────────────────────────────────┘
                   │
                   ▼ caption requests
┌─ Gemini 2.0 Flash API ───────────────────────────┐
│ ~$0.00016 per frame caption                        │
│ ~$0.009 per 56-frame video                         │
└───────────────────────────────────────────────────┘
```

---

## Cost Comparison

### Per-video indexing cost (56 frames, 2-min audio)

| Component | Local Qwen3-VL (A100) | Gemini API (L4) |
|-----------|----------------------|-----------------|
| GPU time | ~8 min @ $2.10/hr = $0.28 | ~2 min @ $0.80/hr = $0.027 |
| Captioning | included in GPU | 56 frames × $0.00016 = $0.009 |
| **Total per video** | **~$0.28** | **~$0.04** |
| **Speedup** | baseline | ~4x faster (no caption generation wait) |

### Monthly estimates (50 videos/month)

| Component | Cost |
|-----------|------|
| Cloud Run (search + API) | $15-30 |
| Cloud SQL (pgvector) | $50 |
| Cloud Storage | $1 |
| Modal GPU (50 videos × 2 min) | $1.35 |
| Gemini API (50 × 56 frames) | $0.45 |
| **Total** | **~$70-85/mo** |

vs. always-on GPU: **$450-2,200/mo**

---

## Configurable Caption Provider

Instead of hardcoding Gemini, make the caption provider configurable:

```python
# bridge/config.py
CAPTION_PROVIDER: str = "gemini"  # "gemini" | "openai" | "anthropic" | "local"
CAPTION_API_KEY: str = ""
CAPTION_MODEL_NAME: str = "gemini-2.0-flash"  # or "gpt-4o", "claude-sonnet-4-5-20250929", "Qwen/Qwen3-VL-8B-Instruct"
CAPTION_ENDPOINT: str = ""  # optional custom endpoint
CAPTION_MAX_TOKENS: int = 256
```

### Provider implementations

All providers receive a PIL image + prompt, return caption text:

```python
# Gemini (google-genai SDK)
def caption_frame_gemini(image: Image, prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, image],
    )
    return response.text

# OpenAI-compatible (works with GPT-4o, local vLLM, etc.)
def caption_frame_openai(image: Image, prompt: str) -> str:
    import openai, base64, io
    buf = io.BytesIO(); image.save(buf, format="JPEG"); b64 = base64.b64encode(buf.getvalue()).decode()
    response = openai.chat.completions.create(
        model=settings.CAPTION_MODEL_NAME,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        max_tokens=settings.CAPTION_MAX_TOKENS,
    )
    return response.choices[0].message.content

# Anthropic Claude
def caption_frame_anthropic(image: Image, prompt: str) -> str:
    import anthropic, base64, io
    buf = io.BytesIO(); image.save(buf, format="JPEG"); b64 = base64.b64encode(buf.getvalue()).decode()
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=settings.CAPTION_MODEL_NAME,
        max_tokens=settings.CAPTION_MAX_TOKENS,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return response.content[0].text

# Local Qwen3-VL (current implementation, for local dev)
def caption_frame_local(image: Image, prompt: str) -> str:
    from main import caption_model, caption_processor
    # existing implementation...
```

---

## Modal App Structure

```
bridge/
├── modal_indexer.py          # Modal app definition
├── indexing/
│   ├── pipeline.py           # index_video() — unchanged core logic
│   ├── captioning.py         # NEW: configurable caption provider
│   └── worker.py             # local polling worker (unchanged, for local dev)
├── search/                   # stays on search-service, NOT on Modal
│   ├── router.py
│   ├── visual.py
│   ├── caption.py
│   └── transcript.py
├── config.py
├── models.py
└── main.py                   # local bridge (search + indexing combined)
```

### modal_indexer.py (sketch)

```python
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("indexing", "models", "config", "minio_utils")
)

app = modal.App("open-testimony-indexer", image=image)

@app.cls(
    gpu="L4",
    secrets=[
        modal.Secret.from_name("db-credentials"),
        modal.Secret.from_name("minio-credentials"),
        modal.Secret.from_name("caption-api-key"),
    ],
    scaledown_window=300,  # 5 min idle
    min_containers=0,      # scale to zero
)
class VideoIndexer:
    @modal.enter()
    def setup(self):
        # Load SigLIP, Qwen3-Embedding, set up DB + MinIO connections
        # Whisper loaded per-video to save idle VRAM
        ...

    @modal.method()
    def index_video(self, video_id: str, object_name: str):
        # Download from MinIO, extract frames, embed, caption via API,
        # transcribe, store in pgvector
        ...

# HTTP trigger endpoint
@app.function()
@modal.fastapi_endpoint(method="POST")
def trigger_index(req: IndexRequest):
    indexer = VideoIndexer()
    call = indexer.index_video.spawn(
        video_id=req.video_id,
        object_name=req.object_name,
    )
    return {"job_id": call.object_id}
```

---

## Migration Path

### Phase 1: Add configurable caption provider (local dev)
- Add `CAPTION_PROVIDER` setting to config.py
- Create `bridge/indexing/captioning.py` with provider dispatch
- Add Gemini + OpenAI implementations alongside existing local Qwen3-VL
- Test locally: `CAPTION_PROVIDER=gemini` should caption via API,
  `CAPTION_PROVIDER=local` uses Qwen3-VL as before
- This immediately reduces local VRAM needs if using API captioning

### Phase 2: Create Modal indexer app
- Write `modal_indexer.py` wrapping existing `index_video()` logic
- Set up Modal secrets for DB, MinIO, caption API key
- Test with `modal serve` (ephemeral deployment)
- Deploy with `modal deploy`

### Phase 3: Split search service from bridge
- Extract search endpoints into standalone FastAPI service
- Loads only SigLIP + Qwen3-Embedding (no Whisper, no caption model)
- Can run on CPU (Cloud Run) or cheap VM
- API server webhook calls Modal instead of local bridge

### Phase 4: Cloud deployment
- Migrate PostgreSQL to Cloud SQL with pgvector
- Migrate MinIO to Cloud Storage (or keep MinIO on a small VM)
- Deploy search service + API + web-ui to Cloud Run
- Modal handles all GPU work on-demand

---

## Networking Requirements

Modal containers run in Modal's cloud and need to reach:
1. **PostgreSQL** — must be publicly accessible (Cloud SQL with authorized
   networks, or Supabase/Neon)
2. **MinIO/Cloud Storage** — must be publicly accessible (Cloud Storage is
   public by default with signed URLs; self-hosted MinIO needs a public IP
   or tunnel)

For local development with Modal:
- Use ngrok or Cloudflare Tunnel to expose local PostgreSQL and MinIO
- Or use `CAPTION_PROVIDER=gemini` locally without Modal (just API calls)

---

## GPU Memory Budget

### With API captioning (L4 — 24GB VRAM)

| Model | VRAM (FP16) |
|-------|-------------|
| SigLIP SO400M-14 | ~1.5 GB |
| Qwen3-Embedding-8B | ~16 GB |
| Whisper large-v3 | ~3 GB (loaded per-video) |
| **Total** | **~20.5 GB** ✅ fits L4 |

### With local Qwen3-VL (A100 — 40/80GB VRAM)

| Model | VRAM (FP16) |
|-------|-------------|
| SigLIP SO400M-14 | ~1.5 GB |
| Qwen3-VL-8B | ~16 GB |
| Qwen3-Embedding-8B | ~16 GB |
| Whisper large-v3 | ~3 GB |
| **Total** | **~36.5 GB** — needs A100 |
