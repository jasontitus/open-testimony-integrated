#!/usr/bin/env python3
"""Benchmark: single vs batched Qwen3-VL caption generation.

Usage (from bridge dir, with venv activated):
    python bench_caption.py [--model Qwen/Qwen3-VL-8B-Instruct] [--device mps] [--frames 16] [--batch-sizes 1,2,4,8]

Pulls real frames from the most recently indexed video in the database,
or generates synthetic test images if no video is available.
"""
import argparse
import os
import sys
import time

import torch
from PIL import Image

# Add bridge dir to path for config imports
sys.path.insert(0, os.path.dirname(__file__))
from config import settings


def get_test_frames(num_frames: int) -> list[Image.Image]:
    """Try to pull real frames from MinIO via a recently indexed video.
    Falls back to synthetic test images.
    """
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT video_id, object_name FROM video_index_status "
                "WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1"
            )).fetchone()

        if row:
            from minio_utils import download_video
            from indexing.pipeline import extract_frames

            video_id, object_name = str(row[0]), row[1]
            print(f"Using video {video_id} ({object_name})")
            local_path = download_video(object_name, video_id)
            try:
                frames = [img for _, _, img in extract_frames(local_path, settings.FRAME_INTERVAL_SEC)]
                if len(frames) >= num_frames:
                    return frames[:num_frames]
                print(f"  Video only has {len(frames)} frames, padding with duplicates")
                while len(frames) < num_frames:
                    frames.append(frames[len(frames) % len(frames)])
                return frames[:num_frames]
            finally:
                os.remove(local_path)
    except Exception as e:
        print(f"Could not load real frames: {e}")

    print("Generating synthetic test images")
    import numpy as np
    frames = []
    for i in range(num_frames):
        arr = np.random.randint(50, 220, (384, 384, 3), dtype=np.uint8)
        frames.append(Image.fromarray(arr))
    return frames


def load_model(model_name: str, device: str):
    """Load Qwen3-VL model and processor."""
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

    print(f"Loading {model_name} on {device}...")
    processor = AutoProcessor.from_pretrained(model_name)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype="auto",
        device_map=device if device != "cpu" else None,
    )
    if device == "cpu":
        model = model.float()
    model.eval()
    print("Model loaded")
    return model, processor


def caption_single(frames: list[Image.Image], prompt: str, model, processor,
                   device: str, max_tokens: int) -> tuple[list[str], float]:
    """Caption frames one at a time (current approach). Returns (captions, total_seconds)."""
    captions = []
    start = time.perf_counter()

    for img in frames:
        messages = [{"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": prompt},
        ]}]
        text_input = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(text=[text_input], images=[img], padding=True, return_tensors="pt")
        if device != "cpu":
            inputs = inputs.to(device)

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=max_tokens)
        generated = output_ids[0][inputs.input_ids.shape[1]:]
        caption = processor.decode(generated, skip_special_tokens=True).strip()
        captions.append(caption)

    elapsed = time.perf_counter() - start
    return captions, elapsed


def caption_batched(frames: list[Image.Image], prompt: str, model, processor,
                    device: str, max_tokens: int, batch_size: int) -> tuple[list[str], float]:
    """Caption frames in batches. Returns (captions, total_seconds)."""
    captions = []
    start = time.perf_counter()

    for i in range(0, len(frames), batch_size):
        batch_imgs = frames[i:i + batch_size]

        # Build per-image messages
        batch_messages = []
        for img in batch_imgs:
            batch_messages.append([{"role": "user", "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": prompt},
            ]}])

        texts = [
            processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            for msgs in batch_messages
        ]
        inputs = processor(
            text=texts, images=batch_imgs, padding=True, return_tensors="pt"
        )
        if device != "cpu":
            inputs = inputs.to(device)

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=max_tokens)

        # Decode each sequence in the batch
        for j in range(len(batch_imgs)):
            # Find where input ends for this sequence (first non-pad from the left)
            input_len = (inputs.input_ids[j] != processor.tokenizer.pad_token_id).sum().item()
            generated = output_ids[j][input_len:]
            caption = processor.decode(generated, skip_special_tokens=True).strip()
            captions.append(caption)

    elapsed = time.perf_counter() - start
    return captions, elapsed


def main():
    parser = argparse.ArgumentParser(description="Benchmark single vs batched Qwen3-VL captioning")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct", help="Model name")
    parser.add_argument("--device", default=settings.DEVICE, help="Device (mps, cuda, cpu)")
    parser.add_argument("--frames", type=int, default=16, help="Number of frames to caption")
    parser.add_argument("--max-tokens", type=int, default=settings.CAPTION_MAX_TOKENS)
    parser.add_argument("--batch-sizes", default="1,2,4,8",
                        help="Comma-separated batch sizes to test")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations (single frame)")
    args = parser.parse_args()

    batch_sizes = [int(x) for x in args.batch_sizes.split(",")]
    prompt = settings.CAPTION_PROMPT

    # Load frames and model
    frames = get_test_frames(args.frames)
    model, processor = load_model(args.model, args.device)

    # Warmup
    if args.warmup > 0:
        print(f"\nWarming up ({args.warmup} frame(s))...")
        caption_single(frames[:args.warmup], prompt, model, processor, args.device, args.max_tokens)
        if args.device == "mps":
            torch.mps.synchronize()
        elif args.device.startswith("cuda"):
            torch.cuda.synchronize()

    # Benchmark each batch size
    print(f"\nBenchmarking {args.frames} frames, max_tokens={args.max_tokens}")
    print(f"{'Batch Size':>12} {'Total (s)':>12} {'Per Frame (s)':>14} {'Speedup':>10}")
    print("-" * 52)

    baseline_time = None
    for bs in batch_sizes:
        if bs == 1:
            captions, elapsed = caption_single(
                frames, prompt, model, processor, args.device, args.max_tokens
            )
        else:
            captions, elapsed = caption_batched(
                frames, prompt, model, processor, args.device, args.max_tokens, bs
            )

        if args.device == "mps":
            torch.mps.synchronize()
        elif args.device.startswith("cuda"):
            torch.cuda.synchronize()

        per_frame = elapsed / len(frames)
        if baseline_time is None:
            baseline_time = elapsed
        speedup = baseline_time / elapsed

        print(f"{bs:>12} {elapsed:>12.2f} {per_frame:>14.3f} {speedup:>9.2f}x")

    # Show sample caption
    print(f"\nSample caption (batch_size={batch_sizes[-1]}, frame 0):")
    print(captions[0][:300] + "..." if len(captions[0]) > 300 else captions[0])


if __name__ == "__main__":
    main()
