"""Caption provider dispatch: routes to Gemini API or local Qwen3-VL."""
import logging
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from config import settings

logger = logging.getLogger(__name__)


def caption_frame(pil_image: Image.Image, prompt: str, caption_model=None,
                  caption_processor=None, device=None) -> str:
    """Generate a caption for a single frame using the configured provider."""
    if settings.CAPTION_PROVIDER == "gemini":
        return _caption_gemini(pil_image, prompt)
    else:
        return _caption_local(pil_image, prompt, caption_model, caption_processor, device)


def _caption_gemini(pil_image: Image.Image, prompt: str) -> str:
    """Caption a frame using the Gemini API."""
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.CAPTION_MODEL_NAME,
        contents=[prompt, pil_image],
    )
    return response.text.strip()


def _caption_local(pil_image: Image.Image, prompt: str, caption_model,
                   caption_processor, device) -> str:
    """Caption a single frame using local Qwen3-VL model."""
    import torch

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text_input = caption_processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = caption_processor(
        text=[text_input],
        images=[pil_image],
        padding=True,
        return_tensors="pt",
    )
    if device != "cpu":
        inputs = inputs.to(device)

    with torch.no_grad():
        output_ids = caption_model.generate(
            **inputs,
            max_new_tokens=settings.CAPTION_MAX_TOKENS,
        )
    generated = output_ids[0][inputs.input_ids.shape[1]:]
    caption = caption_processor.decode(generated, skip_special_tokens=True).strip()
    return caption


def _caption_local_batch(images: list[Image.Image], prompt: str, caption_model,
                         caption_processor, device) -> list[str]:
    """Caption multiple frames in a single forward pass using local Qwen3-VL.

    Returns a list of caption strings (same order as input images).
    """
    import torch

    batch_messages = []
    for img in images:
        batch_messages.append([{
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": prompt},
            ],
        }])

    texts = [
        caption_processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        for msgs in batch_messages
    ]
    inputs = caption_processor(
        text=texts, images=images, padding=True, return_tensors="pt"
    )
    if device != "cpu":
        inputs = inputs.to(device)

    with torch.no_grad():
        output_ids = caption_model.generate(
            **inputs,
            max_new_tokens=settings.CAPTION_MAX_TOKENS,
        )

    pad_token_id = caption_processor.tokenizer.pad_token_id
    captions = []
    for j in range(len(images)):
        input_len = (inputs.input_ids[j] != pad_token_id).sum().item()
        generated = output_ids[j][input_len:]
        caption = caption_processor.decode(generated, skip_special_tokens=True).strip()
        captions.append(caption)

    return captions


def caption_frames_batch(all_frames, caption_model=None, caption_processor=None,
                         device=None) -> list:
    """Caption a list of (frame_num, timestamp_ms, pil_image) tuples.

    Returns list of (frame_num, timestamp_ms, caption_text) tuples.
    For Gemini provider, uses ThreadPoolExecutor for parallel API calls.
    For local provider, uses batched inference (CAPTION_BATCH_SIZE).
    """
    prompt = settings.CAPTION_PROMPT
    results = []

    if settings.CAPTION_PROVIDER == "gemini":
        def _caption_one(item):
            frame_num, timestamp_ms, pil_img = item
            try:
                caption = caption_frame(pil_img, prompt)
                return (frame_num, timestamp_ms, caption)
            except Exception as e:
                logger.warning(f"Gemini caption failed for frame {frame_num}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = list(executor.map(_caption_one, all_frames))
        results = [r for r in futures if r is not None]
    else:
        batch_size = settings.CAPTION_BATCH_SIZE
        for i in range(0, len(all_frames), batch_size):
            chunk = all_frames[i:i + batch_size]
            chunk_imgs = [img for _, _, img in chunk]
            chunk_meta = [(fn, ts) for fn, ts, _ in chunk]

            try:
                if batch_size == 1:
                    captions = [_caption_local(
                        chunk_imgs[0], prompt, caption_model, caption_processor, device
                    )]
                else:
                    captions = _caption_local_batch(
                        chunk_imgs, prompt, caption_model, caption_processor, device
                    )
                for (fn, ts), cap in zip(chunk_meta, captions):
                    results.append((fn, ts, cap))
            except Exception as e:
                logger.warning(f"Caption batch failed at frame {chunk_meta[0][0]}: {e}")
                # Fall back to one-at-a-time for this chunk
                for (fn, ts), img in zip(chunk_meta, chunk_imgs):
                    try:
                        cap = _caption_local(
                            img, prompt, caption_model, caption_processor, device
                        )
                        results.append((fn, ts, cap))
                    except Exception as e2:
                        logger.warning(f"Caption failed for frame {fn}: {e2}")

    return results
