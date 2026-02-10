# 1. Import libraries
import os
import sys

# Ensure the script's directory is in the Python path for 'core' module
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import torch
import faiss
import numpy as np
import uvicorn
import mimetypes # For image proxy content type
import urllib.parse # For decoding URL parameters
import json # Added json (needed for ffprobe parsing)
import cv2 # Added OpenCV
import argparse # Added for command-line arguments
import asyncio # Added for subprocess handling in transcoding
import re # Might need later for more complex parsing if not using JSON
from typing import Optional, Union  # For Python 3.9 compatibility
from typing import Optional, Union  # For Python 3.9 compatibility
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, Response, RedirectResponse # Added FileResponse/StreamingResponse/Response
from fastapi.staticfiles import StaticFiles # Added for serving thumbnails
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from PIL import Image
import core.vision_encoder.pe as pe
import core.vision_encoder.transforms as transforms
import time
import io # For streaming response
import hashlib # Added for hashing paths
import hmac as hmac_module
import base64
import secrets
from contextlib import asynccontextmanager # For lifespan
import subprocess # For running external scripts
import traceback # Added for printing tracebacks
import torch.nn.functional as F

try:
    import open_clip
    OPEN_CLIP_AVAILABLE = True
except ImportError:
    OPEN_CLIP_AVAILABLE = False

# --- Helper function to check video codecs using ffprobe ---
async def check_codecs(file_path: str) -> Optional[dict]:
    """
    Uses ffprobe to check video and audio codecs.
    Returns a dictionary {'video': video_codec, 'audio': audio_codec} or None on error.
    Example video_codec: 'h264', 'hevc', 'vp9'
    Example audio_codec: 'aac', 'mp3', 'opus'
    """
    ffprobe_cmd = [
        "ffprobe",
        "-v", "quiet", # Less verbose output
        "-print_format", "json", # Output as JSON
        "-show_streams", # Get stream info
        file_path
    ]
    print(f"Running ffprobe check: {' '.join(ffprobe_cmd)}")
    try:
        process = await asyncio.create_subprocess_exec(
            *ffprobe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"ffprobe error (return code {process.returncode}): {stderr.decode()}")
            return None # Indicate error

        try:
            data = json.loads(stdout)
            codecs = {'video': None, 'audio': None}
            if 'streams' in data:
                for stream in data['streams']:
                    codec_type = stream.get('codec_type')
                    codec_name = stream.get('codec_name')
                    if codec_type == 'video' and codecs['video'] is None: # Take first video stream
                        codecs['video'] = codec_name
                    elif codec_type == 'audio' and codecs['audio'] is None: # Take first audio stream
                        codecs['audio'] = codec_name
                print(f"Detected codecs: {codecs}")
                return codecs
            else:
                print("ffprobe output missing 'streams' key.")
                return None # Indicate error or unexpected format
        except json.JSONDecodeError as e:
            print(f"Failed to parse ffprobe JSON output: {e}")
            print(f"ffprobe stdout was:\n{stdout.decode()}")
            return None # Indicate error
        except Exception as e:
             print(f"Unexpected error parsing ffprobe output: {type(e).__name__}: {e}")
             return None

    except FileNotFoundError:
        print("Error: 'ffprobe' command not found in PATH. Cannot check codecs.")
        return None # Indicate error
    except Exception as e:
        print(f"Error running ffprobe: {type(e).__name__}: {e}")
        return None # Indicate error

# --- NEW Helper function to get video duration using ffprobe ---
async def get_video_duration(file_path: str) -> Optional[float]:
    """
    Uses ffprobe to get the duration of the video file in seconds.
    Returns the duration as a float, or None on error.
    """
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error", # Only show errors
        "-show_entries", "format=duration", # Get duration from format section
        "-of", "default=noprint_wrappers=1:nokey=1", # Print only the value
        file_path
    ]
    print(f"Running ffprobe duration check: {' '.join(ffprobe_cmd)}")
    try:
        process = await asyncio.create_subprocess_exec(
            *ffprobe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"ffprobe duration error (return code {process.returncode}): {stderr.decode()}")
            return None

        try:
            duration_str = stdout.decode().strip()
            if duration_str == 'N/A': # Handle cases where duration isn't available
                 print(f"ffprobe reported duration as N/A for {file_path}")
                 return None
            duration = float(duration_str)
            print(f"Detected duration: {duration:.3f} seconds")
            return duration
        except ValueError as e:
            print(f"Failed to parse ffprobe duration output '{duration_str}': {e}")
            return None
        except Exception as e:
             print(f"Unexpected error parsing ffprobe duration output: {type(e).__name__}: {e}")
             return None

    except FileNotFoundError:
        print("Error: 'ffprobe' command not found in PATH. Cannot get duration.")
        return None
    except Exception as e:
        print(f"Error running ffprobe for duration: {type(e).__name__}: {e}")
        return None
# --- End Duration Helper ---

# --- Server Argument Parsing --- #
def parse_server_args():
    parser = argparse.ArgumentParser(description="Open Testimony - Video Search Server")
    # Allow overriding index_suffix via environment variable first
    default_suffix_from_env = os.environ.get("VIDEO_INDEXER_SUFFIX")
    
    # If env var is set, use it as the default for argparse, otherwise use ""
    argparse_default_suffix = default_suffix_from_env if default_suffix_from_env is not None else ""

    parser.add_argument("--index-suffix", type=str, default=argparse_default_suffix,
                        help="Suffix for index/metadata files (e.g., _10000). Can also be set by VIDEO_INDEXER_SUFFIX env var.")
    # Add host/port args if needed
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host IP to bind the server to.")
    parser.add_argument("--port", type=int, default=8002, help="Port to bind the server to.")
    parser.add_argument("--fp16", action="store_true",
                        help="Use fp16 precision for model inference to reduce memory usage (default: fp32).")
    return parser.parse_args()

server_args = parse_server_args() # Parse args early
# --- End Server Argument Parsing --- #

# --- Remove global model/index/metadata loading variables ---
# model = None
# index = None
# frame_metadata = []
# preprocess = None
# index_config = {}

# --- Helper function to load/reload all critical resources ---
def _load_all_resources(app_state: object, server_args_obj: object) -> bool:
    print("Attempting to load/reload all resources...")
    # Reset states
    app_state.is_initialized = False
    app_state.index_config = None
    app_state.model = None
    app_state.preprocess = None
    app_state.index = None
    app_state.frame_metadata = None
    # New transcript-related state
    app_state.transcript_index = None
    app_state.transcript_metadata = None
    app_state.transcript_model = None
    app_state.transcript_config = None
    app_state.allowed_video_paths = set()
    # Device and MAX_RESULT_DISTANCE are assumed to be set once in lifespan and don't need reset here,
    # unless we want to re-evaluate them too. For now, focus on index-dependent resources.

    # Use proper Application Support paths for macOS app
    try:
        from app_paths import get_video_index_dir
        index_dir = get_video_index_dir()
    except ImportError:
        index_dir = "video_index_output"
    config_file = os.path.join(index_dir, "index_config.json")
    index_suffix = server_args_obj.index_suffix
    index_file = os.path.join(index_dir, f"video_index{index_suffix}.faiss")
    metadata_file = os.path.join(index_dir, f"video_frame_metadata{index_suffix}.json")

    if not os.path.exists(config_file):
        print(f"Warning: Index configuration file '{config_file}' not found. Cannot initialize resources.")
        return False
    
    try:
        print(f"Loading index configuration from {config_file}...")
        with open(config_file, "r") as f:
            loaded_config = json.load(f)
        print(f"Loaded index configuration: {loaded_config}")
        required_keys = ["model_name", "embedding_dim"]
        if not all(key in loaded_config for key in required_keys):
             print(f"Error: Index config {config_file} missing required keys: {required_keys}. Resources not loaded.")
             return False
        app_state.index_config = loaded_config

        model_name = app_state.index_config["model_name"]
        model_family = app_state.index_config.get("model_family", "pe")
        openclip_pretrained = app_state.index_config.get("openclip_pretrained", "laion2b_s32b_b79k")
        app_state.model_family = model_family
        app_state.normalize_embeddings = app_state.index_config.get(
            "normalize_embeddings",
            model_family == "open_clip"
        )
        print(f"Loading model {model_name} specified in config (family: {model_family})...")
        try:
            # Ensure app_state.device is available (should be set in lifespan)
            if not app_state.device:
                 print("Error: Device not set in app_state. Cannot load model.")
                 return False

            if model_family == "open_clip":
                if not OPEN_CLIP_AVAILABLE:
                    print("Error: open_clip_torch is not installed. Install with: pip install open_clip_torch")
                    return False
                local_model, _, preprocess = open_clip.create_model_and_transforms(
                    model_name, pretrained=openclip_pretrained
                )
                local_model = local_model.to(app_state.device)
                app_state.preprocess = preprocess
                app_state.text_tokenizer = open_clip.get_tokenizer(model_name)
            else:
                local_model = pe.CLIP.from_config(model_name, pretrained=True)
                local_model = local_model.to(app_state.device)
                app_state.preprocess = transforms.get_image_transform(local_model.image_size)
                app_state.text_tokenizer = transforms.get_text_tokenizer(local_model.context_length)
            
            # Convert to fp16 if requested
            if app_state.use_fp16:
                if app_state.device.type == "cpu":
                    print("Warning: fp16 requested but using CPU device. fp16 is not well supported on CPU, continuing with fp32.")
                    app_state.use_fp16 = False  # Disable fp16 for CPU
                else:
                    print("Converting model to fp16 precision...")
                    local_model = local_model.half()
            
            app_state.model = local_model.eval()
            print(f"Model {model_name} loaded.")

            print(f"Attempting to load index: {index_file}")
            print(f"Attempting to load metadata: {metadata_file}")

            if not os.path.exists(index_file) or not os.path.exists(metadata_file):
                print(f"Warning: Index ({index_file}) or metadata ({metadata_file}) files not found. Model loaded, but server not fully initialized.")
                return False # Not fully initialized
            
            try:
                print(f"Loading index from {index_file}...")
                local_index = faiss.read_index(index_file)
                expected_embedding_dim = app_state.index_config["embedding_dim"]
                if local_index.d != expected_embedding_dim:
                    print(f"Error: Index dimension ({local_index.d}) does not match config ({expected_embedding_dim}). Index not loaded.")
                    return False
                app_state.index = local_index

                try:
                    print(f"Loading frame metadata from {metadata_file}...")
                    with open(metadata_file, "r") as f:
                        loaded_data = json.load(f)
                    if not isinstance(loaded_data, list):
                        print(f"Error: Metadata file {metadata_file} is not in the expected list format. Metadata not loaded.")
                        return False
                    app_state.frame_metadata = loaded_data
                    print(f"Loaded metadata for {len(app_state.frame_metadata)} frames.")
                    if app_state.index and app_state.index.ntotal != len(app_state.frame_metadata):
                        print(f"Warning: FAISS index size ({app_state.index.ntotal}) != metadata length ({len(app_state.frame_metadata)}).")
                    
                    # Try to load transcript resources (optional - don't fail if missing)
                    transcript_config_file = os.path.join(index_dir, "transcript_index_config.json")
                    transcript_index_file = os.path.join(index_dir, f"transcript_index{index_suffix}.faiss")
                    transcript_metadata_file = os.path.join(index_dir, f"transcript_metadata{index_suffix}.json")
                    
                    if os.path.exists(transcript_config_file) and os.path.exists(transcript_index_file) and os.path.exists(transcript_metadata_file):
                        try:
                            print(f"Loading transcript configuration from {transcript_config_file}...")
                            with open(transcript_config_file, "r") as f:
                                transcript_config = json.load(f)
                            app_state.transcript_config = transcript_config
                            
                            # Load transcript model
                            from sentence_transformers import SentenceTransformer
                            text_model_name = transcript_config.get("text_model", "paraphrase-multilingual-mpnet-base-v2")
                            print(f"Loading transcript text model: {text_model_name}...")
                            app_state.transcript_model = SentenceTransformer(text_model_name)
                            
                            # Load transcript index
                            print(f"Loading transcript index from {transcript_index_file}...")
                            transcript_index = faiss.read_index(transcript_index_file)
                            app_state.transcript_index = transcript_index
                            
                            # Load transcript metadata
                            print(f"Loading transcript metadata from {transcript_metadata_file}...")
                            with open(transcript_metadata_file, "r", encoding='utf-8') as f:
                                transcript_metadata = json.load(f)
                            app_state.transcript_metadata = transcript_metadata
                            
                            print(f"Transcript resources loaded: {len(transcript_metadata)} segments indexed")
                        except Exception as e:
                            print(f"Warning: Failed to load transcript resources: {e}")
                            app_state.transcript_index = None
                            app_state.transcript_metadata = None
                            app_state.transcript_model = None
                            app_state.transcript_config = None
                    else:
                        print("Transcript index files not found - transcript search will not be available")
                    
                    # Build allowed_video_paths (realpaths) for secure video URLs - only these paths can be streamed
                    allowed = set()
                    for entry in app_state.frame_metadata or []:
                        if isinstance(entry, list) and len(entry) >= 2:
                            try:
                                allowed.add(os.path.realpath(entry[0]))
                            except (OSError, TypeError):
                                pass
                    for entry in (app_state.transcript_metadata or []):
                        if isinstance(entry, dict) and "video_path" in entry:
                            try:
                                allowed.add(os.path.realpath(entry["video_path"]))
                            except (OSError, TypeError):
                                pass
                    app_state.allowed_video_paths = allowed
                    print(f"Allowed video paths for streaming: {len(app_state.allowed_video_paths)} unique paths.")
                    
                    app_state.is_initialized = True # All critical resources loaded
                    print("--- All resources loaded successfully. Server is initialized. ---")
                    return True
                except Exception as e_meta:
                    print(f"Error loading or parsing metadata file {metadata_file}: {e_meta}. Metadata not loaded.")
                    return False
            except Exception as e_index:
                print(f"Error loading FAISS index file {index_file}: {e_index}. Index not loaded.")
                return False
        except Exception as e_model:
            print(f"Error loading model {model_name} from config: {e_model}. Model not loaded.")
            return False
    except Exception as e_config:
        print(f"Error loading or parsing index config file {config_file}: {e_config}. Config not loaded.")
        return False
    return False # Should not be reached if logic is correct, but as a fallback

# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === Startup ===
    print("--- Lifespan Startup: Initializing server state ---")
    # Initialize all potentially used app.state attributes to None or default
    app.state.is_initialized = False
    app.state.index_config = None
    app.state.model = None
    app.state.preprocess = None
    app.state.text_tokenizer = None
    app.state.model_family = None
    app.state.normalize_embeddings = False
    app.state.index = None
    app.state.frame_metadata = None
    app.state.transcript_index = None
    app.state.transcript_metadata = None
    app.state.transcript_model = None
    app.state.transcript_config = None
    app.state.device = None
    app.state.use_fp16 = server_args.fp16
    app.state.MAX_RESULT_DISTANCE = 150.0 # Default - more aggressive filtering
    app.state.video_tags = {} # path -> list of tags
    app.state.predefined_tags = [] # sorted list of predefined tag strings
    app.state.video_token_secret = os.environ.get("VIDEO_TOKEN_SECRET") or secrets.token_hex(32)

    # Load tags if they exist
    try:
        from app_paths import get_video_index_dir
        tags_file = os.path.join(get_video_index_dir(), "video_tags.json")
        if os.path.exists(tags_file):
            with open(tags_file, "r") as f:
                app.state.video_tags = json.load(f)
            print(f"Loaded tags for {len(app.state.video_tags)} videos")
    except Exception as e:
        print(f"Warning: Could not load tags: {e}")

    # Load or seed predefined tags
    try:
        from app_paths import get_video_index_dir
        predefined_tags_file = os.path.join(get_video_index_dir(), "predefined_tags.json")
        if os.path.exists(predefined_tags_file):
            with open(predefined_tags_file, "r") as f:
                app.state.predefined_tags = json.load(f)
            print(f"Loaded {len(app.state.predefined_tags)} predefined tags")
        else:
            app.state.predefined_tags = [
                "chokehold", "civil-disobedience", "drone", "excessive-force",
                "flash-bang", "handcuffing", "journalist-targeted", "kettling",
                "medic-targeted", "memorial", "pepper-spray", "police-misconduct",
                "police-violence", "protest", "rubber-bullets", "shooting",
                "taser", "tear-gas", "traffic-stop", "use-of-force"
            ]
            with open(predefined_tags_file, "w") as f:
                json.dump(app.state.predefined_tags, f, indent=2)
            print(f"Seeded {len(app.state.predefined_tags)} predefined tags")
    except Exception as e:
        print(f"Warning: Could not load/seed predefined tags: {e}")

    # 1. Setup Device (done once)
    if torch.backends.mps.is_available():
        app.state.device = torch.device("mps")
    elif torch.cuda.is_available():
        app.state.device = torch.device("cuda")
    else:
        app.state.device = torch.device("cpu")
    print(f"Using device: {app.state.device}")
    print(f"Using precision: {'fp16' if app.state.use_fp16 else 'fp32'}")

    # 2. Setup Max Result Distance (done once)
    DEFAULT_MAX_DISTANCE = 200.0 
    try:
        app.state.MAX_RESULT_DISTANCE = float(os.environ.get('MAX_RESULT_DISTANCE', DEFAULT_MAX_DISTANCE))
    except ValueError:
        print(f"Warning: Invalid MAX_RESULT_DISTANCE environment variable. Using default: {DEFAULT_MAX_DISTANCE}")
        # app.state.MAX_RESULT_DISTANCE is already defaulted
    print(f"Using max result distance threshold: {app.state.MAX_RESULT_DISTANCE:.2f}")
    
    # Attempt to load all resources using the helper
    if _load_all_resources(app.state, server_args): # server_args is global
        print("--- Lifespan Startup: Initial resource loading successful. ---")
    else:
        print("--- Lifespan Startup: Server started in an uninitialized or partially initialized state. ---")
        print("--- Please use the UI to perform initial video processing and index setup if required. ---")
    
    print(f"DEBUG SERVER: Lifespan complete. app.state.is_initialized = {app.state.is_initialized}")
    yield # Application runs here
    
    # === Shutdown ===
    print("--- Lifespan Shutdown: Cleaning up resources ---")
    app.state.model = None
    app.state.index = None
    app.state.frame_metadata = None
    app.state.index_config = None
    app.state.preprocess = None
    app.state.transcript_index = None
    app.state.transcript_metadata = None
    app.state.transcript_model = None
    app.state.transcript_config = None
    # app.state.device = None # Device itself isn't a loaded resource to clear in this way
    app.state.is_initialized = False # Reset on shutdown
    print("--- Lifespan Shutdown: Cleanup complete ---")
# --- End Lifespan ---

# --- Create FastAPI app WITH lifespan ---
app = FastAPI(lifespan=lifespan)
# --- End App Creation ---

# Mount static files (This happens AFTER app creation)
# Use proper Application Support paths for macOS app
try:
    from app_paths import get_video_thumbnails_dir, get_temp_uploads_dir
    thumbnail_static_dir = get_video_thumbnails_dir()
    temp_upload_dir = get_temp_uploads_dir()
except ImportError:
    thumbnail_static_dir = "video_thumbnails_output"
    temp_upload_dir = "temp_uploads"
if os.path.exists(thumbnail_static_dir):
    # Check if it's already an absolute path (e.g., if user provided full path)
    # For simplicity, assuming it's a relative path from script location
    full_thumbnail_path = os.path.abspath(thumbnail_static_dir)
    print(f"Attempting to mount thumbnail directory: {full_thumbnail_path} at /thumbnails")
    if os.path.isdir(full_thumbnail_path): # Double check it's a directory
        app.mount("/thumbnails", StaticFiles(directory=full_thumbnail_path), name="thumbnails")
        print(f"Successfully mounted thumbnail directory: {full_thumbnail_path} at /thumbnails")
    else:
        print(f"Warning: Resolved thumbnail path {full_thumbnail_path} is not a directory. Thumbnails will not be served.")
else:
    # This print might appear before lifespan startup logs, which is fine
    print(f"Warning: Thumbnail directory not found at {thumbnail_static_dir} (relative to script). Thumbnails will not be served.")

# Mount assets directory for logo and other assets
# Check both local 'assets' (bundled) and parent 'assets' (development)
assets_dir = os.path.abspath(os.path.join(script_dir, "assets"))
if not os.path.exists(assets_dir):
    assets_dir = os.path.abspath(os.path.join(script_dir, "..", "assets"))

if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    print(f"Successfully mounted assets directory: {assets_dir} at /assets")
else:
    print(f"Warning: Assets directory not found at {assets_dir}")

# Add a fallback route for missing thumbnails
@app.get("/thumbnails/{video_hash}/{timestamp}.jpg")
async def get_thumbnail_with_fallback(video_hash: str, timestamp: str):
    """Serve thumbnails with fallback to nearest available thumbnail."""
    import os
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    
    # Use Application Support directory if available, otherwise fallback to local
    try:
        from app_paths import get_video_thumbnails_dir
        thumbnail_dir = get_video_thumbnails_dir()
    except ImportError:
        thumbnail_dir = "video_thumbnails_output"
    
    if not os.path.exists(thumbnail_dir):
        raise HTTPException(status_code=404, detail="Thumbnail directory not found")
    
    video_dir = os.path.join(thumbnail_dir, video_hash)
    if not os.path.exists(video_dir):
        raise HTTPException(status_code=404, detail="Video thumbnails not found")
    
    # Try the exact timestamp first
    exact_file = os.path.join(video_dir, f"{timestamp}.jpg")
    if os.path.exists(exact_file):
        return FileResponse(exact_file)
    
    # Try to find the nearest available thumbnail
    try:
        target_ms = int(timestamp)
        rounded_ms = round(target_ms / 1000) * 1000
        
        # Check nearby timestamps
        candidates = [
            rounded_ms,
            rounded_ms - 1000,
            rounded_ms + 1000,
            rounded_ms - 2000,
            rounded_ms + 2000,
            rounded_ms - 3000,
            rounded_ms + 3000
        ]
        
        for candidate_ms in candidates:
            if candidate_ms >= 0:
                candidate_file = os.path.join(video_dir, f"{candidate_ms}.jpg")
                if os.path.exists(candidate_file):
                    return FileResponse(candidate_file)
        
        # If no nearby thumbnail found, list what's available and pick the closest
        available_files = [f for f in os.listdir(video_dir) if f.endswith('.jpg')]
        if available_files:
            # Find the closest timestamp
            available_timestamps = []
            for f in available_files:
                try:
                    ts = int(f.replace('.jpg', ''))
                    available_timestamps.append((abs(ts - target_ms), ts, f))
                except ValueError:
                    continue
            
            if available_timestamps:
                available_timestamps.sort()  # Sort by distance
                closest_file = os.path.join(video_dir, available_timestamps[0][2])
                return FileResponse(closest_file)
        
    except ValueError:
        pass  # timestamp wasn't a valid integer
    
    raise HTTPException(status_code=404, detail="No suitable thumbnail found")

# --- Templates (global is fine) ---
# Ensure templates are found relative to script location
templates_dir = os.path.join(script_dir, "video_templates")
os.makedirs(templates_dir, exist_ok=True) # Ensure it exists
print(f"Using templates from directory: {templates_dir}")
templates = Jinja2Templates(directory=templates_dir)


# --- Helper function to log search results for debugging ---
def log_search_debug(query: str, search_type: str, results: list):
    """Logs search results to a debug file for investigation."""
    try:
        from app_paths import get_video_index_dir
        log_dir = get_video_index_dir()
    except ImportError:
        log_dir = "video_index_output"
    
    os.makedirs(log_dir, exist_ok=True)
    debug_log_path = os.path.join(log_dir, "search_debug.log")
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Header for both file and console
    log_header = f"\n{'='*50}\nTimestamp: {timestamp}\nSearch Type: {search_type}\nQuery: {query}\nTotal Results: {len(results)}\n{'-'*50}\n"
    print(log_header)

    with open(debug_log_path, "a") as f:
        f.write(log_header)
        
        for i, res in enumerate(results[:20]):  # Log top 20 results
            video_path = res.get("display_name", res.get("video_path", "Unknown"))
            start_ms = res.get("start_ms", 0)
            score = res.get("score", 0)
            thumb_url = res.get("thumbnail_url", "No URL")
            
            # Check if thumbnail exists and its status
            thumb_status = "Unknown"
            is_black = "Unknown"
            
            # Try to find the actual file path for the thumbnail
            try:
                from app_paths import get_video_thumbnails_dir
                thumb_base = get_video_thumbnails_dir()
            except ImportError:
                thumb_base = "video_thumbnails_output"
            
            # Example thumb_url: /thumbnails/hash/timestamp.jpg
            if thumb_url.startswith("/thumbnails/"):
                parts = thumb_url.split("/")
                if len(parts) >= 4:
                    video_hash = parts[2]
                    timestamp_jpg = parts[3]
                    physical_thumb_path = os.path.join(thumb_base, video_hash, timestamp_jpg)
                    
                    if os.path.exists(physical_thumb_path):
                        file_size = os.path.getsize(physical_thumb_path)
                        thumb_status = f"Exists ({file_size} bytes)"
                        
                        # Check if mostly black
                        try:
                            from PIL import Image, ImageStat
                            with Image.open(physical_thumb_path) as img:
                                stat = ImageStat.Stat(img.convert("L"))
                                mean_brightness = stat.mean[0]
                                is_black = "Yes" if mean_brightness < 10 else "No"
                                thumb_status += f", Brightness: {mean_brightness:.1f}"
                        except Exception as e:
                            is_black = f"Error checking: {e}"
                    else:
                        thumb_status = "MISSING"
            
            result_line = (
                f"{i+1}. Video: {video_path}\n"
                f"   Time: {start_ms}ms, Score: {score:.4f}\n"
                f"   Thumb: {thumb_url} ({thumb_status})\n"
                f"   Is Black: {is_black}\n"
            )
            print(result_line)
            f.write(result_line)
        
        if len(results) > 20:
            footer = f"... and {len(results) - 20} more results.\n"
            print(footer)
            f.write(footer)
    
    print(f"DEBUG: Search results also logged to {debug_log_path}")

# Define constants for content types
# These can be moved to a config later if needed
WEB_FRIENDLY_CONTAINERS = {'video/webm', 'video/ogg'} # MP4 handled separately now
ALWAYS_TRANSCODE_TYPES = {'video/x-msvideo', 'video/avi', 'video/quicktime'} # AVI, MOV
UNSUPPORTED_VIDEO_CODECS = {'hevc', 'mpeg4', 'prores', 'dnxhd'} # Add more as needed
# Audio codecs are generally less problematic for browsers if in supported containers,
# but can add UNSUPPORTED_AUDIO_CODECS if specific issues arise.
# E.g. UNSUPPORTED_AUDIO_CODECS = {'flac', 'alac'} if browsers struggle with them in MP4/WebM.


def _create_video_token(path: str, app_state) -> Optional[str]:
    """Create a signed token for a video path. Only paths in allowed_video_paths get a token.
    Token is base64url-encoded (no dots) so nginx/proxies don't treat the URL as a static file."""
    allowed = getattr(app_state, "allowed_video_paths", None) or set()
    secret = getattr(app_state, "video_token_secret", "") or ""
    if not secret or not allowed:
        return None
    try:
        realpath = os.path.realpath(path)
        if realpath not in allowed:
            return None
        payload_b = realpath.encode("utf-8")
        payload = base64.urlsafe_b64encode(payload_b).decode("ascii").rstrip("=")
        sig = hmac_module.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        inner = f"{payload}.{sig}"
        token = base64.urlsafe_b64encode(inner.encode()).decode("ascii").rstrip("=")
        return token
    except (OSError, TypeError, ValueError):
        return None


def _resolve_video_token(token: str, app_state) -> Optional[str]:
    """Resolve a signed token to a video path. Returns None if token invalid or path not allowed."""
    allowed = getattr(app_state, "allowed_video_paths", None) or set()
    secret = getattr(app_state, "video_token_secret", "") or ""
    if not token or not secret or not allowed:
        return None
    try:
        pad = 4 - (len(token) % 4)
        if pad != 4:
            token += "=" * pad
        inner = base64.urlsafe_b64decode(token).decode("utf-8")
        payload, sig = inner.rsplit(".", 1)
        expected = hmac_module.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac_module.compare_digest(expected, sig):
            return None
        pad_p = 4 - (len(payload) % 4)
        if pad_p != 4:
            payload += "=" * pad_p
        path = base64.urlsafe_b64decode(payload).decode("utf-8")
        realpath = os.path.realpath(path)
        if realpath not in allowed:
            return None
        return realpath
    except (ValueError, OSError, TypeError):
        return None


# --- Define routes (Update to use app.state) ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Use the template from video_templates
    # Pass a status message if available (e.g., after initialization attempt)
    status_message = request.query_params.get("status_message", None)
    error_message = request.query_params.get("error_message", None)
    
    # Log the initialization state when home page is accessed
    print(f"DEBUG SERVER: Home route. request.app.state.is_initialized = {request.app.state.is_initialized}")
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "is_initialized": request.app.state.is_initialized,
        "status_message": status_message,
        "error_message": error_message,
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })

# New endpoint to render the video player page (uses secure video_token, not file path)
@app.get("/player", response_class=HTMLResponse)
async def render_player_page(request: Request, video_token: str = Query(..., alias="video_token"), video_start_milliseconds: int = Query(0, alias="video_start_milliseconds"), filename: Optional[str] = Query(None)):
    resolved_path = _resolve_video_token(video_token, request.app.state)
    if not resolved_path:
        raise HTTPException(status_code=403, detail="Invalid or expired video link.")
    display_name = filename if filename else os.path.basename(resolved_path)
    return templates.TemplateResponse("player.html", {
        "request": request,
        "video_token": video_token,
        "start_ms_for_player_js": video_start_milliseconds,
        "display_filename": display_name,
        "start_ms_for_display": video_start_milliseconds
    })

# Stream video by token only (token in query to avoid nginx/proxy path issues)
@app.get("/stream_video/{start_ms}")
async def stream_video(request: Request, start_ms: int, t: str = Query(..., alias="t")):
    token = t
    decoded_path = _resolve_video_token(token, request.app.state)
    if not decoded_path:
        raise HTTPException(status_code=403, detail="Invalid or expired video link.")
    start_milliseconds = start_ms

    print(f"Video stream request (token), start_ms: {start_milliseconds}")

    if not os.path.isfile(decoded_path):
        print(f"Error: Video path not found or not a file (resolved from token).")
        raise HTTPException(status_code=404, detail="Video file not found.")

    content_type, _ = mimetypes.guess_type(decoded_path)
    if content_type is None:
        content_type = 'application/octet-stream'
    print(f"Guessed Content-Type: {content_type} for {decoded_path}")

    # --- Transcoding Decision Logic ---
    needs_transcoding = False
    transcode_reason = ""

    if content_type in ALWAYS_TRANSCODE_TYPES:
        needs_transcoding = True
        transcode_reason = f"container type {content_type} always transcoded"
    elif content_type == 'video/mp4':
        codecs = await check_codecs(decoded_path)
        if codecs and codecs.get('video'):
            if codecs['video'] in UNSUPPORTED_VIDEO_CODECS:
                needs_transcoding = True
                transcode_reason = f"MP4 with unsupported video codec: {codecs['video']}"
            elif codecs['video'] == 'h264':
                # Optionally check audio codec here if needed.
                # For now, assume h264 video in mp4 is okay unless specific audio issue found.
                print(f"MP4 with H.264 video codec. Serving directly.")
            else: # Other MP4 video codecs (e.g. mjpeg, vp8 in mp4) - try direct serving
                print(f"MP4 with video codec '{codecs['video']}'. Attempting direct serving.")
        elif codecs is None: # ffprobe failed or couldn't determine codecs
            needs_transcoding = True
            transcode_reason = "ffprobe failed for MP4, forcing transcode as fallback"
        else: # No video stream found by ffprobe, or other issue
            print(f"Could not determine video codec for MP4: {decoded_path}. Serving directly by default.")
            # Default to direct serving if ffprobe gives unexpected (but not error) results for MP4 video stream
    elif content_type in WEB_FRIENDLY_CONTAINERS:
        print(f"Web-friendly container {content_type}. Serving directly.")
        # Potentially add codec check here too for webm/ogg if certain codecs are problematic
    else: # Unknown or other non-web-friendly types
        needs_transcoding = True
        transcode_reason = f"unknown or non-web-friendly container type: {content_type}"
    # --- End Transcoding Decision ---

    if needs_transcoding:
        print(f"Transcoding needed for {decoded_path} (start: {start_milliseconds}ms). Reason: {transcode_reason}")
        file_size = os.path.getsize(decoded_path) # Get original file size for progress if useful
        duration_seconds = await get_video_duration(decoded_path)

        async def stream_transcoded_video(start_milliseconds: int):
            # Check if ffmpeg command exists
            try:
                proc_test = await asyncio.create_subprocess_exec("ffmpeg", "-version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc_test.communicate()
                if proc_test.returncode != 0:
                    print("ffmpeg command test failed. It might not be installed or in PATH.")
                    # This error will likely be caught by the main FileNotFoundError if ffmpeg isn't there
            except FileNotFoundError:
                print("FATAL: ffmpeg command not found in PATH. Transcoding is not possible.")
                # Client will hang here. Better to raise HTTPException earlier if possible,
                # but it's hard to do from within a streaming response generator.
                # The request might time out or the client might close connection.
                # Consider a pre-check for ffmpeg availability at server startup.
                return # Stop the generator


            ffmpeg_cmd = [
                "ffmpeg",
                "-hide_banner", "-loglevel", "error", # Quieter output
            ]
            # Seeking: Use -ss before -i for fast seek (input seeking)
            if start_milliseconds > 0:
                # Convert ms to HH:MM:SS.mmm format or seconds
                start_seconds_float = start_milliseconds / 1000.0
                ffmpeg_cmd.extend(["-ss", str(start_seconds_float)])

            ffmpeg_cmd.extend([
                "-i", decoded_path,
                "-c:v", "libx264",    # Video codec: H.264
                "-preset", "ultrafast", # Encoding speed (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
                "-tune", "zerolatency",# Optimized for streaming
                "-crf", "23",          # Constant Rate Factor (quality, 18-28 is a good range, lower is better quality)
                "-c:a", "aac",         # Audio codec: AAC
                "-b:a", "128k",        # Audio bitrate
                "-movflags", "frag_keyframe+empty_moov+faststart", # Optimise for streaming, ensure faststart
                "-f", "mp4",           # Output format: MP4
                "-"                    # Output to stdout
            ])
            print(f"Executing ffmpeg: {' '.join(ffmpeg_cmd)}")

            try:
                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE # Capture stderr for logging
                )
                # Log stderr in a separate task to avoid blocking
                async def log_stderr():
                    while True:
                        line = await process.stderr.readline()
                        if not line:
                            break
                        print(f"ffmpeg stderr: {line.decode().strip()}")
                asyncio.create_task(log_stderr())

                # Stream stdout
                while True:
                    chunk = await process.stdout.read(65536) # Read in 64KB chunks
                    if not chunk:
                        break
                    yield chunk
                await process.wait() # Wait for ffmpeg to finish
                if process.returncode != 0:
                    print(f"ffmpeg process exited with error code {process.returncode}")
                else:
                    print("ffmpeg process finished successfully.")

            except FileNotFoundError:
                print("Error: 'ffmpeg' command not found. Please ensure it is installed and in your PATH.")
                # This ideally should be caught earlier or send a specific error response
                # For now, the stream will just end if ffmpeg is not found here.
            except Exception as e:
                print(f"Error during ffmpeg transcoding for {decoded_path}: {type(e).__name__}: {e}")
                # Stream will likely break.
            finally:
                if process and process.returncode is None: # Check if process exists and is still running
                    print(f"Transcoding for {decoded_path} ended; attempting to terminate ffmpeg process {process.pid}")
                    try:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                        print(f"ffmpeg process {process.pid} terminated.")
                    except asyncio.TimeoutError:
                        print(f"Timeout trying to terminate ffmpeg process {process.pid}, attempting to kill.")
                        process.kill()
                        await process.wait()
                        print(f"ffmpeg process {process.pid} killed.")
                    except Exception as e_term:
                        print(f"Error terminating/killing ffmpeg process {process.pid}: {e_term}")


        # StreamingResponse for transcoded video
        # Set Content-Disposition to force download with a filename (optional)
        # filename=os.path.basename(decoded_path)
        # headers = {
        # 'Content-Disposition': f'attachment; filename="{filename}"'
        # }
        # For inline playback, Content-Disposition is not strictly needed.
        # Browsers usually handle MP4 correctly with video/mp4.
        return StreamingResponse(stream_transcoded_video(start_milliseconds), media_type="video/mp4")

    else: # Serve directly
        print(f"Serving directly: {decoded_path} with Content-Type: {content_type}")
        # Get file size for Content-Length header (important for browsers)
        file_size = os.path.getsize(decoded_path)
        headers = {
            'Content-Length': str(file_size),
            'Accept-Ranges': 'bytes' # Indicate support for range requests
        }
        # For direct file serving, especially with seeking, FileResponse is generally better
        # and handles range requests properly.
        # However, if we implemented our own seeking logic with -ss for direct files,
        # we'd need to stream it similarly to transcoded files.
        # Since we are only using -ss for transcoding path currently:
        if start_milliseconds > 0:
            # This case should ideally not be hit if not transcoding,
            # as player.html is expected to handle seeking for direct play.
            # If it IS hit, it means client requested a start offset for a direct-play file.
            # The simple FileResponse won't respect this. We'd need to implement
            # ffmpeg streaming for direct play with -ss if that's a desired feature.
            # For now, warn and serve from beginning.
            print(f"Warning: start_ms ({start_milliseconds}) requested for direct play of {decoded_path}. FileResponse serves from start.")
            # To truly support this, we'd need to use ffmpeg to stream even non-transcoded files
            # if start_ms > 0, similar to the transcoding path but without codec changes.
            # E.g., ffmpeg -ss <time> -i <input> -c copy -f mp4 -

        # Ensure the Content-Disposition makes it an inline player, not a download.
        # Usually, this is default for video types if `attachment` is not specified.
        # Using a modified filename if it was transcoded and sought might be:
        # original_filename = os.path.basename(decoded_path)
        # if start_milliseconds > 0:
        #     base, ext = os.path.splitext(original_filename)
        #     filename = f"{base}_from_{start_milliseconds // 1000}s{ext}"
        # else:
        #     filename = original_filename
        # headers['Content-Disposition'] = f'inline; filename="{filename}"' # Ensure it's not treated as attachment
        
        # Add Content-Disposition only if filename is latin-1 compatible
        # Otherwise skip it entirely to avoid UnicodeEncodeError
        original_filename = os.path.basename(decoded_path)
        try:
            original_filename.encode('latin-1')
            headers['Content-Disposition'] = f'inline; filename="{original_filename}"'
            print(f"DEBUG: Added Content-Disposition header for latin-1 compatible filename")
        except UnicodeEncodeError:
            print(f"DEBUG: Skipping Content-Disposition header for non-latin-1 filename: {repr(original_filename)}")
            # Don't set Content-Disposition at all - browsers will handle video fine without it

        return FileResponse(decoded_path, media_type=content_type, headers=headers)


@app.get("/search_by_path", response_class=HTMLResponse)
async def search_by_path(request: Request, path: str = Query(...)):
    # Access resources via request.app.state
    if not request.app.state.is_initialized or not request.app.state.model or not request.app.state.index:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "results": [], 
            "query": path, 
            "error_message": "System not initialized. Please process videos first.",
            "is_initialized": request.app.state.is_initialized # Pass current state
        })
    local_model = request.app.state.model
    local_preprocess = request.app.state.preprocess
    local_device = request.app.state.device
    local_index = request.app.state.index
    local_frame_metadata = request.app.state.frame_metadata

    start_time = time.time()
    decoded_path = urllib.parse.unquote(path)
    print(f"Received search by path request: {decoded_path}")

    if not os.path.exists(decoded_path) or not os.path.isfile(decoded_path):
        print(f"Error: Image path does not exist or is not a file: {decoded_path}")
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "query": decoded_path,
            "error_message": "Cannot search by path: Image not found.",
            "is_initialized": request.app.state.is_initialized
        })

    try:
        img = Image.open(decoded_path).convert("RGB")
        img_tensor = local_preprocess(img).unsqueeze(0).to(local_device)
        
        # Convert to fp16 if model is in fp16
        if request.app.state.use_fp16:
            img_tensor = img_tensor.half()
        
        print(f"Query image tensor shape: {img_tensor.shape}, device: {img_tensor.device}")

        with torch.no_grad():
            model_start = time.time()
            if request.app.state.model_family == "open_clip":
                image_features = local_model.encode_image(img_tensor)
                if request.app.state.normalize_embeddings:
                    image_features = F.normalize(image_features, dim=-1)
            else:
                image_features, _, _ = local_model(img_tensor, None)
            model_end = time.time()
            print(f"Model inference (path query) took {model_end - model_start:.2f} seconds")
        query_features = image_features
    except Exception as e:
        print(f"Error processing image file {decoded_path}: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "query": decoded_path,
            "error_message": f"Error processing image for search: {e}",
            "is_initialized": request.app.state.is_initialized
        })

    query_features_np = query_features.cpu().numpy()
    print(f"DEBUG: About to perform FAISS search")
    print(f"DEBUG: query_features shape: {query_features.shape}")
    print(f"DEBUG: query_features type: {type(query_features)}")
    print(f"DEBUG: search_type: {search_type}")
    print(f"DEBUG: query_summary: {query_summary}")
    
    search_start = time.time()
    try:
        D, I = local_index.search(query_features_np, k=100)
    except Exception as e:
        print(f"Error during FAISS search: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "query": decoded_path,
            "error_message": "Error during search. Index might be incompatible or corrupted.",
            "is_initialized": request.app.state.is_initialized
        })

    search_end = time.time()
    print(f"FAISS search took {search_end - search_start:.4f} seconds for k=100")

    # Access metadata from state if needed, ensure it's loaded
    if not hasattr(request.app.state, 'frame_metadata') or not request.app.state.frame_metadata:
         print("Error: Frame metadata not loaded during search_by_path.")
         return templates.TemplateResponse("index.html", {
            "request": request, 
            "query": decoded_path,
            "error_message": "Frame metadata not loaded. Cannot process search results.",
            "is_initialized": request.app.state.is_initialized
        })

    results_for_template = []
    # Initialize with a default large distance if D is empty or invalid
    distances_for_results = D[0] if len(D) > 0 and len(D[0]) > 0 else [float('inf')] * len(I[0])

    for i, res_idx in enumerate(I[0]):
         if 0 <= res_idx < len(request.app.state.frame_metadata):
              entry = request.app.state.frame_metadata[res_idx]
              dist = distances_for_results[i] if i < len(distances_for_results) else float('inf')
              if isinstance(entry, list) and len(entry) == 2:
                   video_path, frame_num = entry
                   video_tok = _create_video_token(video_path, request.app.state)
                   if not video_tok:
                       continue
                   timestamp_str = f"{frame_num//60000:02d}:{(frame_num//1000)%60:02d}"
                   results_for_template.append({
                       "video_token": video_tok,
                       "display_name": os.path.basename(video_path),
                       "start_ms": frame_num, 
                       "end_ms": frame_num, # Placeholder, adjust if clip duration is known
                       "score": dist, # FAISS returns distances, lower is better. Template formats it.
                       "timestamp_str": timestamp_str,
                       "thumbnail_url": f"/thumbnails/{hashlib.sha256(video_path.encode()).hexdigest()}/{frame_num}.jpg",
                       "tags": request.app.state.video_tags.get(video_path, [])
                   })
              else:
                   print(f"Warning: Invalid metadata entry format at index {res_idx} in search_by_path. Skipping.")
         else:
              print(f"Warning: Invalid index {res_idx} in search_by_path. Skipping.")

    print(f"Top 10 matches (by path): {results_for_template[:10]}")
    log_search_debug(decoded_path, "path", results_for_template)
    total_time = time.time() - start_time
    print(f"Total search request time (by path): {total_time:.2f} seconds")

    # --- DEBUG URL_FOR ---
    if results_for_template:
        first_result_obj = results_for_template[0]
        test_tok = first_result_obj.get('video_token')
        test_ms = first_result_obj.get('start_ms')
        if test_tok is not None:
            test_player_url = f"/player?video_token={urllib.parse.quote(test_tok)}&video_start_milliseconds={test_ms}"
            print(f"DEBUG SERVER: Successfully generated test_player_url (token-based)")
    # --- END DEBUG URL_FOR ---

    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_initialized": request.app.state.is_initialized,
        "query": decoded_path, # Original query (image path)
        "results": results_for_template,
        "error_message": None, # Or any specific status
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })


def find_nearest_thumbnail(video_path: str, timestamp_ms: int) -> str:
    """Find the nearest available thumbnail for a given timestamp."""
    path_hash = hashlib.sha256(video_path.encode()).hexdigest()
    
    # Round to nearest second (1000ms intervals)
    # Frame extractor typically creates thumbnails every 1000ms
    rounded_ms = round(timestamp_ms / 1000) * 1000
    
    # Try a few nearby timestamps in case the exact one doesn't exist
    candidate_times = [
        rounded_ms,
        rounded_ms - 1000,
        rounded_ms + 1000,
        rounded_ms - 2000,
        rounded_ms + 2000
    ]
    
    for candidate_ms in candidate_times:
        if candidate_ms >= 0:  # Don't go negative
            thumbnail_path = f"/thumbnails/{path_hash}/{candidate_ms}.jpg"
            # Check if file exists (we'll assume it does for the first valid candidate)
            return thumbnail_path
    
    # Fallback to the original timestamp if nothing else works
    return f"/thumbnails/{path_hash}/{rounded_ms}.jpg"

def search_transcripts_semantic(query_text: str, transcript_index, transcript_metadata, transcript_model, max_results: int = 100) -> list:
    """Search transcripts using both semantic and exact matching, then merge results intelligently."""
    if not query_text.strip():
        return []
    
    try:
        # First do exact word matching
        import re
        query_words = set(re.findall(r'\b\w+\b', query_text.lower()))
        exact_results = []
        seen_texts = set()  # Track unique segments across both result sets
        
        # Process exact matches first - MUST find all exact matches
        for idx, segment_data in enumerate(transcript_metadata):
            text = segment_data["text"].strip()
            # Allow short filenames, but keep the limit for transcripts to avoid noise
            if len(text) < 10 and segment_data.get("segment_id") != "filename":
                continue
                
            text_lower = text.lower()
            # Use proper word boundary matching
            text_words = set(re.findall(r'\b\w+\b', text_lower))
            exact_matches = query_words.intersection(text_words)
            
            # Check for exact word matches
            if exact_matches:  # If any query words match exactly
                seen_texts.add(text_lower)
                exact_match_ratio = len(exact_matches) / len(query_words)
                # Exact matches get very high scores (0.95-1.0)
                score = 0.95 + (0.05 * exact_match_ratio)
                
                # Debug info for exact matches
                print(f"Found exact match: {text} (score: {score})")
                
                exact_results.append({
                    "video_path": segment_data["video_path"],
                    "start_ms": int(segment_data["start_time"] * 1000),
                    "end_ms": int(segment_data["end_time"] * 1000),
                    "score": score,
                    "text": text,
                    "language": segment_data.get("language", "unknown"),
                    "chunk_level": segment_data.get("chunk_level", "original"),
                    "thumbnail_url": find_nearest_thumbnail(segment_data["video_path"], int(segment_data["start_time"] * 1000))
                })
        
        # Then do semantic search
        query_embedding = transcript_model.encode([query_text], normalize_embeddings=True)
        # Search more results to ensure we don't miss semantically relevant content
        scores, indices = transcript_index.search(query_embedding.astype(np.float32), max_results * 4)
        
        semantic_results = []
        
        # Process semantic matches
        for score, idx in zip(scores[0], indices[0]):
            if idx >= len(transcript_metadata) or idx < 0:
                continue
                
            segment_data = transcript_metadata[idx]
            text = segment_data["text"].strip()
            text_lower = text.lower()
            
            if len(text) < 10 or text_lower in seen_texts:
                continue
            
            seen_texts.add(text_lower)
            similarity_score = float(score)
            
            # Include semantic matches with good scores
            if similarity_score >= 0.6:  # Threshold for semantic-only matches
                semantic_results.append({
                    "video_path": segment_data["video_path"],
                    "start_ms": int(segment_data["start_time"] * 1000),
                    "end_ms": int(segment_data["end_time"] * 1000),
                    "score": similarity_score,
                    "text": text,
                    "language": segment_data.get("language", "unknown"),
                    "chunk_level": segment_data.get("chunk_level", "original"),
                    "thumbnail_url": find_nearest_thumbnail(segment_data["video_path"], int(segment_data["start_time"] * 1000))
                })
        
        # Debug info
        print(f"Found {len(exact_results)} exact matches:")
        for r in exact_results:
            print(f"  - {r['text']} (score: {r['score']})")
        print(f"Found {len(semantic_results)} semantic matches")
        if semantic_results:
            print("Top semantic matches:")
            for r in semantic_results[:3]:
                print(f"  - {r['text']} (score: {r['score']})")
        
        # Combine results, ensuring exact matches are always included
        results = []
        
        # Add all exact matches first
        results.extend(exact_results)
        
        # Add semantic matches that aren't duplicates
        for r in semantic_results:
            if r["text"].lower() not in {er["text"].lower() for er in exact_results}:
                results.append(r)
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Return all exact matches plus top semantic matches, but at least max_results
        return results[:max(len(exact_results), max_results)]
        
    except Exception as e:
        print(f"Error during transcript search: {e}")
        traceback.print_exc()
        return []

def search_transcripts_text(query_text: str, transcript_metadata, max_results: int = 500) -> list:
    """Search transcripts using simple text matching."""
    if not query_text.strip():
        return []
    
    try:
        query_lower = query_text.lower().strip()
        results = []
        
        for segment_data in transcript_metadata:  # Fixed: removed enumerate
            text = segment_data["text"].strip()
            text_lower = text.lower()
            
            # Skip very short segments (unless it's a filename match)
            if len(text) < 10 and segment_data.get("segment_id") != "filename":
                continue
            
            # Calculate text match score using proper word boundaries
            import re
            score = 0.0
            
            # Split into words (remove punctuation)
            text_words = re.findall(r'\b\w+\b', text_lower)
            query_words = re.findall(r'\b\w+\b', query_lower)
            
            if not query_words:
                continue
            
            # Check for exact phrase match (consecutive words)
            # Look for the query words as a consecutive sequence in text_words
            phrase_found = False
            if len(query_words) == 1:
                # Single word - check if it exists as a complete word
                phrase_found = query_words[0] in text_words
            else:
                # Multi-word phrase - look for consecutive sequence
                for i in range(len(text_words) - len(query_words) + 1):
                    if text_words[i:i+len(query_words)] == query_words:
                        phrase_found = True
                        break
            
            if phrase_found:
                # Calculate how much of the text the phrase covers
                match_ratio = len(query_words) / len(text_words)
                score = 0.9 + (match_ratio * 0.1)  # 0.9 to 1.0
            
            # Individual word matches (must be whole words)
            else:
                text_word_set = set(text_words)
                matches = sum(1 for word in query_words if word in text_word_set)
                if matches > 0:
                    score = (matches / len(query_words)) * 0.8  # 0.0 to 0.8
            
            # Only include results with decent quality (at least 30% match)
            if score >= 0.3:
                start_ms = int(segment_data["start_time"] * 1000)
                
                results.append({
                    "video_path": segment_data["video_path"],
                    "start_ms": start_ms,
                    "end_ms": int(segment_data["end_time"] * 1000),
                    "score": float(score),
                    "text": text,
                    "language": segment_data.get("language", "unknown"),
                    "chunk_level": segment_data.get("chunk_level", "original"),
                    "thumbnail_url": find_nearest_thumbnail(segment_data["video_path"], start_ms)
                })
        
        # Sort by score (highest first), then by start time
        results.sort(key=lambda x: (-x["score"], x["start_ms"]))
        
        # Apply quality-based filtering instead of hard limit
        # Keep all high quality results (0.6+), then fill remaining slots with decent ones
        high_quality = [r for r in results if r["score"] >= 0.6]
        decent_quality = [r for r in results if 0.3 <= r["score"] < 0.6]
        
        # Start with all high quality results
        final_results = high_quality[:]
        
        # Add decent quality results if we have room
        remaining_slots = max_results - len(high_quality)
        if remaining_slots > 0:
            final_results.extend(decent_quality[:remaining_slots])
        
        return final_results
    except Exception as e:
        print(f"Error during text transcript search: {e}")
        traceback.print_exc()
        return []

@app.get("/search_transcripts", response_class=HTMLResponse)
async def search_transcripts_page(request: Request):
    """Render the search page for GET requests (no search performed)."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_initialized": request.app.state.is_initialized,
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })

@app.post("/search_transcripts", response_class=HTMLResponse)
async def search_transcripts_endpoint(request: Request, text: str = Form(""), search_mode: str = Form("text")):
    """Search transcripts by text."""
    if not request.app.state.is_initialized:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "results": [],
            "query": text,
            "error_message": "System not initialized. Please process videos first.",
            "is_initialized": request.app.state.is_initialized
        })
    
    if not request.app.state.transcript_index or not request.app.state.transcript_metadata:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "results": [],
            "query": text,
            "error_message": "Transcript search not available. Transcripts may not be indexed yet.",
            "is_initialized": request.app.state.is_initialized
        })
    
    if not text.strip():
        return templates.TemplateResponse("index.html", {
            "request": request,
            "results": [],
            "query": "",
            "error_message": "Please enter text to search transcripts.",
            "is_initialized": request.app.state.is_initialized
        })
    
    start_time = time.time()
    
    # Choose search method based on mode
    if search_mode == "semantic":
        results = search_transcripts_semantic(
            text,
            request.app.state.transcript_index,
            request.app.state.transcript_metadata,
            request.app.state.transcript_model,
            max_results=200
        )
        search_type_label = "Semantic"
    else:
        results = search_transcripts_text(
            text,
            request.app.state.transcript_metadata,
            max_results=500
        )
        search_type_label = "Text"
    
    search_time = time.time() - start_time
    print(f"{search_type_label} transcript search for '{text}' took {search_time:.2f} seconds, found {len(results)} results")
    
    # Format results for template (only include high-quality results)
    results_for_template = []
    for result in results:
        # No additional filtering for text search (already filtered by quality)
        # Keep semantic search filtering only
        if search_type_label == "Semantic" and result["score"] < 0.2:
            continue
        start_ms = result["start_ms"]
        end_ms = result["end_ms"]
        timestamp_str = f"{start_ms//60000:02d}:{(start_ms//1000)%60:02d}"
        
        # Create longer, more informative text snippets
        result_text = result["text"]  # Use different variable name to avoid overwriting 'text' parameter
        if len(result_text) > 400:
            # Find a good break point near the middle
            mid_point = 200
            # Look for sentence breaks near the middle
            for i in range(mid_point - 50, mid_point + 50):
                if i < len(result_text) and result_text[i] in '.!?':
                    text_snippet = result_text[:i+1] + "..."
                    break
            else:
                # No sentence break found, just truncate
                text_snippet = result_text[:400] + "..."
        else:
            text_snippet = result_text
        
        video_tok = _create_video_token(result["video_path"], request.app.state)
        if not video_tok:
            continue
        results_for_template.append({
            "video_token": video_tok,
            "display_name": os.path.basename(result["video_path"]),
            "start_ms": start_ms,
            "score": result["score"],
            "timestamp_str": timestamp_str,
            "thumbnail_url": result["thumbnail_url"],
            "text_snippet": text_snippet,
            "language": result["language"],
            "tags": request.app.state.video_tags.get(result["video_path"], [])
        })
    
    log_search_debug(text, f"transcript_{search_mode}", results_for_template)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_initialized": request.app.state.is_initialized,
        "query": text,
        "results": results_for_template,
        "search_type": "transcript",
        "search_mode": search_mode,
        "result_count": len(results_for_template),
        "total_time": f"{search_time:.3f}",
        "error_message": None,
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })

@app.get("/search_web", response_class=HTMLResponse)
async def search_web_page(request: Request):
    """Render the search page for GET requests (no search performed)."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_initialized": request.app.state.is_initialized,
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })

@app.post("/search_web", response_class=HTMLResponse)
async def search_web(request: Request, file: UploadFile = File(None), text: str = Form(""), search_type: str = Form("visual")):
    # Web interface search endpoint
    return await search(request, file, text, search_type)

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Render the search page for GET requests (no search performed)."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_initialized": request.app.state.is_initialized,
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, file: UploadFile = File(None), text: str = Form(""), search_type: str = Form("visual")):
    # Access resources via request.app.state
    if not request.app.state.is_initialized or not request.app.state.model or not request.app.state.index:
        search_type = "text" if text else "image" if file and file.filename else "unknown"
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "results": [], 
            "query": text or (file.filename if file else ""), 
            "error_message": f"System not initialized. Cannot perform {search_type} search. Please process videos first.",
            "is_initialized": request.app.state.is_initialized # Pass current state
        })
    local_model = request.app.state.model
    local_preprocess = request.app.state.preprocess
    local_device = request.app.state.device
    local_index = request.app.state.index
    local_frame_metadata = request.app.state.frame_metadata
    local_MAX_RESULT_DISTANCE = request.app.state.MAX_RESULT_DISTANCE
    # --- Get base URL (still needed for potential M3U) ---
    base_url = str(request.base_url) # Example: http://127.0.0.1:8002/
    # Remove trailing slash if present, to ensure consistent join for M3U
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    print(f"Base URL for M3U: {base_url}")


    # Ensure resources are loaded (check one)
    if local_model is None or local_index is None or local_frame_metadata is None:
         return templates.TemplateResponse("index.html", {
             "request": request, 
             "query": text or (file.filename if file else ""),
             "error_message": "Server resources not ready. Please ensure system is initialized.",
             "is_initialized": request.app.state.is_initialized
            })

    start_time = time.time()
    K_INITIAL_SEARCH = 1000 # Number of initial candidates from FAISS
    K_FINAL_RESULTS = 50   # Max number of unique videos to show
    query_features = None
    is_text_search = False # Flag to know if we should pass text to template
    search_type = ""
    query_summary = "" # For displaying in results

    # Debug: Log what we received
    print(f"DEBUG SEARCH REQUEST:")
    print(f"  - Text parameter: '{text}' (length: {len(text) if text else 0})")
    print(f"  - File parameter: {file.filename if file and file.filename else 'None'}")
    print(f"  - File size: {file.size if file and hasattr(file, 'size') else 'Unknown'}")

    if file and file.filename:
        print(f"Received file upload: {file.filename}")
        search_type = "image_upload"
        query_summary = file.filename
        # Save uploaded file temporarily to get a path for Image.open and for display
        os.makedirs(temp_upload_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_upload_dir, f"query_{int(time.time())}_{file.filename}")
        try:
            print(f"DEBUG: Writing uploaded file to {temp_file_path}")
            with open(temp_file_path, "wb") as buffer:
                buffer.write(await file.read())
            
            print(f"DEBUG: Loading image from {temp_file_path}")
            img = Image.open(temp_file_path).convert("RGB")
            print(f"DEBUG: Image loaded successfully, size: {img.size}")
            
            # Extract features from the uploaded image
            print(f"DEBUG: Starting feature extraction for {file.filename}")
            input_tensor = local_preprocess(img).unsqueeze(0).to(local_device)
            
            # Convert to fp16 if model is in fp16
            if request.app.state.use_fp16:
                input_tensor = input_tensor.half()
            
            print(f"DEBUG: Image preprocessed, tensor shape: {input_tensor.shape}")
            
            with torch.no_grad():
                if request.app.state.model_family == "open_clip":
                    image_features = local_model.encode_image(input_tensor)
                    if request.app.state.normalize_embeddings:
                        image_features = F.normalize(image_features, dim=-1)
                else:
                    image_features, _, _ = local_model(input_tensor, None)
            
            print(f"DEBUG: Features extracted, shape: {image_features.shape}")
            query_features = image_features
            print(f"DEBUG: query_features assigned for image search")
            
        except Exception as e:
            print(f"ERROR: Image processing failed for {file.filename}: {e}")
            if os.path.exists(temp_file_path): os.remove(temp_file_path)
            return templates.TemplateResponse("index.html", {
                "request": request, 
                "query": file.filename if file else "Uploaded image",
                "error_message": f"Invalid image file: {e}",
                "is_initialized": request.app.state.is_initialized
            })
        
        # Clean up temp file
        if os.path.exists(temp_file_path): 
            try: 
                os.remove(temp_file_path)
                print(f"DEBUG: Temporary file {temp_file_path} removed")
            except Exception as e_rem: 
                print(f"Warning: could not remove temp query file {temp_file_path}: {e_rem}")

    elif text.strip():
        print(f"Received text search: '{text}'")
        is_text_search = True # Set flag
        search_type = "text"
        query_summary = text
        tokenizer = request.app.state.text_tokenizer
        with torch.no_grad():
            if request.app.state.model_family == "open_clip":
                tokens = tokenizer([text])
                tokens = tokens.to(local_device)
                text_features = local_model.encode_text(tokens)
                if request.app.state.normalize_embeddings:
                    text_features = F.normalize(text_features, dim=-1)
            else:
                tokens = tokenizer([text]).to(local_device)
                _, text_features, _ = local_model(None, tokens)
        query_features = text_features
    else:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "query": "",
            "error_message": "No input provided (text or image).",
            "is_initialized": request.app.state.is_initialized
        })

    query_np = query_features.cpu().numpy()
    print(f"DEBUG: About to perform FAISS search")
    print(f"DEBUG: query_features shape: {query_features.shape}")
    print(f"DEBUG: query_features type: {type(query_features)}")
    print(f"DEBUG: search_type: {search_type}")
    print(f"DEBUG: query_summary: {query_summary}")
    
    search_start = time.time()
    try:
        distances, indices = local_index.search(query_np, K_INITIAL_SEARCH)
    except Exception as e:
        print(f"Error during FAISS search: {e}")
        if search_type == "image_upload" and 'temp_file_path' in locals() and os.path.exists(temp_file_path): 
            try: os.remove(temp_file_path) 
            except Exception as e_rem: print(f"Warning: could not remove temp query file {temp_file_path}: {e_rem}")
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "query": query_summary,
            "error_message": "Error during FAISS search execution.",
            "is_initialized": request.app.state.is_initialized
        })
    search_end = time.time()
    print(f"Initial FAISS search (k={K_INITIAL_SEARCH}) took {search_end - search_start:.4f} seconds")

    results_data_filtered_sorted = []
    seen_video_paths = set()
    processed_faiss_results = 0

    for i in range(len(indices[0])):
        res_idx = indices[0][i]
        dist = distances[0][i]
        processed_faiss_results += 1

        if dist > local_MAX_RESULT_DISTANCE:
            if len(results_data_filtered_sorted) >= K_FINAL_RESULTS:
                break
            continue

        if 0 <= res_idx < len(local_frame_metadata):
            entry = local_frame_metadata[res_idx]
            if isinstance(entry, list) and len(entry) == 2:
                video_path, frame_num = entry
                video_key = video_path

                if video_key not in seen_video_paths:
                    if len(results_data_filtered_sorted) < K_FINAL_RESULTS:
                        video_tok = _create_video_token(video_path, request.app.state)
                        if not video_tok:
                            continue
                        # Convert distance to similarity score (lower distance = higher similarity)
                        # CLIP cosine distances typically range from 0-2 (0=identical, 2=opposite)
                        # Use original formula which works well for the actual distance ranges
                        similarity_score = max(0.0, 1.0 - (dist / 2.0))
                        
                        # Debug: print actual distance ranges to understand the data better
                        if i < 5:  # Only print first few for debugging
                            print(f"DEBUG: Distance {dist:.2f} -> Similarity {similarity_score:.3f}")
                        
                        timestamp_str = f"{frame_num//60000:02d}:{(frame_num//1000)%60:02d}"
                        results_data_filtered_sorted.append({
                            "video_token": video_tok,
                            "display_name": os.path.basename(video_path),
                            "start_ms": frame_num,
                            "end_ms": frame_num,
                            "score": float(similarity_score),
                            "timestamp_str": timestamp_str,
                            "thumbnail_url": f"/thumbnails/{hashlib.sha256(video_path.encode()).hexdigest()}/{frame_num}.jpg",
                            "tags": request.app.state.video_tags.get(video_path, [])
                        })
                        seen_video_paths.add(video_key)
            else:
                print(f"Warning: Invalid metadata entry format at index {res_idx}. Skipping.")
        else:
            print(f"Warning: Invalid index {res_idx} from FAISS. Skipping.")
        
        if len(results_data_filtered_sorted) >= K_FINAL_RESULTS:
            break

    log_search_debug(query_summary, search_type, results_data_filtered_sorted)
    total_time = time.time() - start_time
    print(f"Total search request time: {total_time:.2f} seconds")
    print(f"Found {len(results_data_filtered_sorted)} unique videos matching query out of {processed_faiss_results} FAISS results processed.")

    if search_type == "image_upload" and 'temp_file_path' in locals() and os.path.exists(temp_file_path): 
        try: os.remove(temp_file_path) 
        except Exception as e_rem: print(f"Warning: could not remove temp query file {temp_file_path}: {e_rem}")

    # --- DEBUG URL_FOR ---
    if results_data_filtered_sorted:
        first_result_obj = results_data_filtered_sorted[0]
        test_tok = first_result_obj.get('video_token')
        test_ms = first_result_obj.get('start_ms')
        if test_tok is not None:
            print(f"DEBUG SERVER: Successfully generated test_player_url (token-based)")
    # --- END DEBUG URL_FOR ---

    # Normalize search_type for template (both text and image_upload are "visual")
    template_search_type = "visual" if search_type in ["text", "image_upload"] else "visual"
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_initialized": request.app.state.is_initialized,
        "query": query_summary,
        "results": results_data_filtered_sorted,
        "search_type": template_search_type,
        "result_count": len(results_data_filtered_sorted),
        "total_time": f"{total_time:.3f}",
        "error_message": None,
        "status_message": f"Found {len(results_data_filtered_sorted)} results.",
        "all_tags": sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags]))),
        "predefined_tags": request.app.state.predefined_tags
    })

@app.post("/add_tag")
async def add_tag(request: Request, video_token: str = Form(..., alias="video_token"), tag: str = Form(...)):
    if not tag.strip():
        return {"status": "error", "message": "Tag cannot be empty"}
    video_path = _resolve_video_token(video_token, request.app.state)
    if not video_path:
        return {"status": "error", "message": "Invalid or expired video link."}
    tag = tag.strip()
    if video_path not in request.app.state.video_tags:
        request.app.state.video_tags[video_path] = []
    
    if tag not in request.app.state.video_tags[video_path]:
        request.app.state.video_tags[video_path].append(tag)
        
        # Save to file
        try:
            from app_paths import get_video_index_dir
            tags_file = os.path.join(get_video_index_dir(), "video_tags.json")
            with open(tags_file, "w") as f:
                json.dump(request.app.state.video_tags, f)
        except Exception as e:
            print(f"Error saving tags: {e}")
            
    return {"status": "success", "tags": request.app.state.video_tags[video_path]}

@app.get("/get_all_tags")
async def get_all_tags(request: Request):
    all_tags = sorted(list(set([tag for tags in request.app.state.video_tags.values() for tag in tags])))
    return {"tags": all_tags, "predefined_tags": request.app.state.predefined_tags}

@app.post("/add_predefined_tag")
async def add_predefined_tag(request: Request, tag: str = Form(...)):
    tag = tag.strip()
    if not tag:
        return {"status": "error", "message": "Tag cannot be empty"}
    if tag not in request.app.state.predefined_tags:
        request.app.state.predefined_tags.append(tag)
        request.app.state.predefined_tags.sort()
        try:
            from app_paths import get_video_index_dir
            predefined_tags_file = os.path.join(get_video_index_dir(), "predefined_tags.json")
            with open(predefined_tags_file, "w") as f:
                json.dump(request.app.state.predefined_tags, f, indent=2)
        except Exception as e:
            print(f"Error saving predefined tags: {e}")
    return {"status": "success", "predefined_tags": request.app.state.predefined_tags}

# --- NEW: M3U Playlist Endpoint (Text Search Only) --- #
@app.get("/playlist.m3u")
async def get_playlist(request: Request, text: str = Query(..., title="Search query for playlist generation")):
    # Access resources via request.app.state
    if not request.app.state.is_initialized or not request.app.state.model or not request.app.state.index:
        raise HTTPException(status_code=503, detail="System not initialized. Cannot generate playlist.")
    local_model = request.app.state.model
    local_device = request.app.state.device
    local_index = request.app.state.index
    local_frame_metadata = request.app.state.frame_metadata
    local_MAX_RESULT_DISTANCE = request.app.state.MAX_RESULT_DISTANCE
    # base_url = str(request.base_url) # Get base URL, e.g., http://127.0.0.1:8002/
    # Correct base_url assembly for playlist items:
    # It should refer to the server's own /stream_video endpoint.
    # request.url.scheme, request.url.hostname, request.url.port
    port_str = f":{request.url.port}" if request.url.port else ""
    base_url_for_stream = f"{request.url.scheme}://{request.url.hostname}{port_str}"


    print(f"Playlist request for text: '{text}'")

    # --- Re-run Text Search Logic (Simplified from /search) ---
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text query cannot be empty for playlist generation.")

    # Ensure resources are loaded
    if local_model is None or local_index is None or local_frame_metadata is None:
        raise HTTPException(status_code=503, detail="Server resources not ready.")

    try:
        tokenizer = request.app.state.text_tokenizer
        with torch.no_grad():
            if request.app.state.model_family == "open_clip":
                tokens = tokenizer([text])
                tokens = tokens.to(local_device)
                text_features = local_model.encode_text(tokens)
                if request.app.state.normalize_embeddings:
                    text_features = F.normalize(text_features, dim=-1)
            else:
                tokens = tokenizer([text]).to(local_device)
                _, text_features, _ = local_model(None, tokens)
        query_features = text_features
        query_np = query_features.cpu().numpy()

        K_INITIAL_SEARCH = 1000 # Same as in /search
        K_FINAL_RESULTS = 100   # Max videos in playlist
        distances, indices = local_index.search(query_np, K_INITIAL_SEARCH)

        # --- Extract unique videos with their BEST start time (first occurrence) ---
        unique_videos = {} # Dict to store path -> frame_num (start_ms)
        print(f"Processing {len(indices[0])} initial frame results for playlist...")

        # Ensure distances are available
        if len(distances) == 0 or len(distances[0]) != len(indices[0]):
            print("Warning: Mismatch or empty distances for playlist. Using dummy distances.")
            actual_distances_playlist = [float('inf')] * len(indices[0])
        else:
            actual_distances_playlist = distances[0]


        for i in range(len(indices[0])):
            # Stop if we have enough unique videos for the playlist
            if len(unique_videos) >= K_FINAL_RESULTS: break
            idx = indices[0][i]
            dist = actual_distances_playlist[i]

            # Stop if distance exceeds threshold
            if dist > local_MAX_RESULT_DISTANCE:
                 print(f"Stopping playlist generation early: distance {dist:.2f} > {local_MAX_RESULT_DISTANCE:.2f}")
                 break

            if 0 <= idx < len(local_frame_metadata):
                entry = local_frame_metadata[idx]
                if isinstance(entry, list) and len(entry) == 2:
                    video_path, frame_num = entry
                    # Add if path is new (first time = best match due to sort order)
                    if video_path not in unique_videos:
                        print(f"  Adding to playlist: {os.path.basename(video_path)} starting at {frame_num}ms (Dist: {dist:.2f})")
                        unique_videos[video_path] = frame_num
                else:
                    print(f"Warning (playlist): Invalid metadata format at index {idx}. Skipping.")
                    continue # Skip malformed metadata
            else:
                 print(f"Warning (playlist): Invalid index {idx} from search. Skipping.")
                 continue # Skip invalid index

    except Exception as e:
        print(f"Error during playlist generation search for '{text}': {e}")
        raise HTTPException(status_code=500, detail=f"Error generating playlist: {e}")
    # --- End Search Logic ---

    # --- Generate M3U Content with VLC Start Time Option --- #
    m3u_content = "#EXTM3U\r\n" # CR LF for M3U
    if not unique_videos:
        print("No results found for playlist generation.")
        # m3u_content remains just header
    else:
        print(f"Generating M3U for {len(unique_videos)} videos with start times.")
        for video_path, frame_num in unique_videos.items():
            video_tok = _create_video_token(video_path, request.app.state)
            if not video_tok:
                continue
            # Token in query so path stays short for nginx/proxies
            stream_url = f"{base_url_for_stream}/stream_video/{frame_num}?t={urllib.parse.quote(video_tok)}"
            title = os.path.basename(video_path)
            start_seconds = int(frame_num / 1000)

            m3u_content += f"#EXTINF:-1,{title} (start at {start_seconds}s)\r\n"
            m3u_content += f"#EXTVLCOPT:start-time={start_seconds}\r\n"
            m3u_content += f"{stream_url}\r\n"
    # --- End M3U Generation ---

    # --- Return Response --- #
    return Response(
        content=m3u_content,
        media_type="audio/x-mpegurl", # Standard M3U MIME type
        headers={
            "Content-Disposition": "attachment; filename=\"results_with_start.m3u\""
        }
    )
# --- END M3U Endpoint --- #

# --- New endpoint for initializing the index ---
@app.post("/initialize_index")
async def initialize_index(request: Request, video_directory: str = Form(...)):
    print(f"Received request to initialize index with video directory: {video_directory}")

    if not os.path.isdir(video_directory):
        print(f"Error: Provided video directory '{video_directory}' does not exist or is not a directory.")
        # Redirect back to home with an error message
        return RedirectResponse(url="/?error_message=" + urllib.parse.quote(f"Video directory not found: {video_directory}"), status_code=303)

    # Use proper Application Support paths for macOS app
    try:
        from app_paths import get_video_index_dir
        output_dir = get_video_index_dir()
    except ImportError:
        output_dir = "video_index_output"
    # Ensure output directory exists for frame_extractor and frame_indexer
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Run frame_extractor.py
    cmd_extract = ["python", "frame_extractor.py", video_directory, "--output-dir", output_dir]
    print(f"Running frame extraction: {' '.join(cmd_extract)}")
    try:
        process_extract = subprocess.run(cmd_extract, capture_output=True, text=True, check=True)
        print("Frame extraction completed successfully.")
        print(f"Extractor STDOUT:\n{process_extract.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error during frame extraction: {e}")
        print(f"Extractor STDERR:\n{e.stderr}")
        return RedirectResponse(url="/?error_message=" + urllib.parse.quote(f"Frame extraction failed: {e.stderr[:200]}..."), status_code=303)
    except FileNotFoundError:
        print("Error: 'python' or 'frame_extractor.py' not found. Ensure they are in PATH or script directory.")
        return RedirectResponse(url="/?error_message=" + urllib.parse.quote("Execution error: python or frame_extractor.py not found."), status_code=303)

    # Step 2: Run frame_indexer.py
    cmd_index = ["python", "frame_indexer.py", "--input-dir", output_dir]
    print(f"Running frame indexing: {' '.join(cmd_index)}")
    try:
        process_index = subprocess.run(cmd_index, capture_output=True, text=True, check=True)
        print("Frame indexing completed successfully.")
        print(f"Indexer STDOUT:\n{process_index.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error during frame indexing: {e}")
        print(f"Indexer STDERR:\n{e.stderr}")
        return RedirectResponse(url="/?error_message=" + urllib.parse.quote(f"Frame indexing failed: {e.stderr[:200]}..."), status_code=303)
    except FileNotFoundError:
        print("Error: 'python' or 'frame_indexer.py' not found. Ensure they are in PATH or script directory.")
        return RedirectResponse(url="/?error_message=" + urllib.parse.quote("Execution error: python or frame_indexer.py not found."), status_code=303)

    # Step 3: Run transcript_extractor.py (with base quality for speed)
    cmd_transcript_extract = ["python", "transcript_extractor.py", video_directory, "--output-dir", output_dir, "--whisper-model", "base", "--workers", "1"]
    print(f"Running transcript extraction: {' '.join(cmd_transcript_extract)}")
    try:
        process_transcript_extract = subprocess.run(cmd_transcript_extract, capture_output=True, text=True, check=True)
        print("Transcript extraction completed successfully.")
        print(f"Transcript Extractor STDOUT:\n{process_transcript_extract.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error during transcript extraction: {e}")
        print(f"Transcript Extractor STDERR:\n{e.stderr}")
        # Continue even if transcript extraction fails
        print("Continuing without transcripts...")
    except FileNotFoundError:
        print("Warning: 'transcript_extractor.py' not found. Skipping transcript extraction.")

    # Step 4: Run transcript_indexer.py (Always run, at least for filenames)
    cmd_transcript_index = ["python", "transcript_indexer.py", "--input-dir", output_dir]
    if request.app.state.use_fp16:
        cmd_transcript_index.append("--fp16")
    print(f"Running text indexing: {' '.join(cmd_transcript_index)}")
    try:
        process_transcript_index = subprocess.run(cmd_transcript_index, capture_output=True, text=True, check=True)
        print("Text indexing completed successfully.")
        print(f"Text Indexer STDOUT:\n{process_transcript_index.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error during text indexing: {e}")
        print(f"Text Indexer STDERR:\n{e.stderr}")
        print("Continuing without text search...")
    except FileNotFoundError:
        print("Warning: 'transcript_indexer.py' not found. Skipping text indexing.")

    # Step 5: Reload resources into app.state
    print("Attempting to reload resources after successful processing...")
    if _load_all_resources(request.app.state, server_args):
        print("Resources reloaded successfully. System is now initialized.")
        return RedirectResponse(url="/?status_message=" + urllib.parse.quote("Initialization successful! System is ready."), status_code=303)
    else:
        print("Error: Failed to reload resources after processing. System may not be correctly initialized.")
        return RedirectResponse(url="/?error_message=" + urllib.parse.quote("Processing complete, but failed to load new index. Check server logs."), status_code=303)

# 6. Run the server (global scope is fine)
if __name__ == "__main__":
    # server_args are parsed globally already
    print("Starting Video Uvicorn server (transcoding enabled)...")
    # Reload=False should prevent the duplicate loading now with lifespan
    # When running from video-indexer/, the module path is video_search_server_transcode:app
    # However, if this file is run directly as `python video_search_server_transcode.py`,
    # then "video_search_server_transcode:app" or "__main__:app" can be used.
    # Uvicorn figures it out if module name is the filename.
    uvicorn.run("video_search_server_transcode:app", host=server_args.host, port=server_args.port, reload=False)

