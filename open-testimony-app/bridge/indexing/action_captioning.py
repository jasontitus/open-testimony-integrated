"""Temporal action captioning: sends multi-frame clip windows to Gemini
for motion/action understanding (chokeholds, pushing, use of force, etc.)."""
import logging
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from config import settings

logger = logging.getLogger(__name__)

# Cached Gemini client (reused across all API calls)
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def _sample_frames_for_caption(images, max_frames=8):
    """Sample frames evenly from a clip window for captioning.

    Gemini handles multiple images well, but sending all 16 frames is expensive.
    Sample up to max_frames evenly spaced frames to capture the motion arc.
    """
    if len(images) <= max_frames:
        return images
    # Evenly space the indices
    indices = [int(i * (len(images) - 1) / (max_frames - 1)) for i in range(max_frames)]
    return [images[i] for i in indices]


def caption_clip_action(images, prompt):
    """Generate an action caption for a multi-frame clip window using Gemini.

    Sends sampled frames from the window along with the action-focused prompt.
    Returns the caption text.
    """
    sampled = _sample_frames_for_caption(images)

    if settings.CAPTION_PROVIDER == "gemini":
        return _caption_action_gemini(sampled, prompt)
    else:
        # For local models, concatenate frames into a grid and caption that
        return _caption_action_grid(sampled, prompt)


def _caption_action_gemini(images, prompt):
    """Send multiple frames to Gemini API for temporal action captioning."""
    client = _get_gemini_client()
    # Build content: prompt text + all frame images
    contents = [prompt] + list(images)
    response = client.models.generate_content(
        model=settings.CAPTION_MODEL_NAME,
        contents=contents,
    )
    return response.text.strip()


def _caption_action_grid(images, prompt):
    """Fallback: stitch frames into a temporal grid image for local captioning.

    Creates a 2-row grid showing the temporal sequence left-to-right.
    """
    # Resize all frames to a common size
    target_w, target_h = 224, 224
    resized = [img.resize((target_w, target_h)) for img in images]

    cols = min(4, len(resized))
    rows = (len(resized) + cols - 1) // cols
    grid = Image.new("RGB", (target_w * cols, target_h * rows))
    for i, img in enumerate(resized):
        r, c = divmod(i, cols)
        grid.paste(img, (c * target_w, r * target_h))

    # Use the single-frame captioning path with the grid image
    from indexing.captioning import caption_frame
    enhanced_prompt = (
        "This image is a grid of consecutive video frames arranged left-to-right, "
        "top-to-bottom in chronological order. " + prompt
    )
    return caption_frame(grid, enhanced_prompt)


def caption_clip_batch(windows):
    """Caption a batch of clip windows for action/motion description.

    Takes list of (window_idx, start_ms, end_ms, start_frame, end_frame, [images]).
    Returns list of (window_idx, start_ms, end_ms, start_frame, end_frame, action_text).

    Uses ThreadPoolExecutor for parallel Gemini API calls.
    """
    prompt = settings.CLIP_ACTION_PROMPT
    results = []

    def _caption_one(window):
        win_idx, start_ms, end_ms, start_frame, end_frame, images = window
        try:
            action_text = caption_clip_action(images, prompt)
            # Filter out windows where Gemini says nothing significant happened
            if action_text and "no significant action" not in action_text.lower():
                return (win_idx, start_ms, end_ms, start_frame, end_frame, action_text)
            return None
        except Exception as e:
            logger.warning(f"Action caption failed for window {win_idx} "
                           f"({start_ms}-{end_ms}ms): {e}")
            return None

    if settings.CAPTION_PROVIDER == "gemini":
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = list(executor.map(_caption_one, windows))
        results = [r for r in futures if r is not None]
    else:
        for window in windows:
            result = _caption_one(window)
            if result is not None:
                results.append(result)

    return results
