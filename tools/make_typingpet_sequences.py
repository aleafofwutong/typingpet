from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from make_typingpet_animation import write_apng


SOURCE_DIR = Path("assets/typingpet-groups")
OUT = Path("assets/typingpet-sequences")
# Slower loop cadence for the desktop pet's two/three-state sequences.
STATE_MS = 250
SHAKE_MS = 80
SHAKE_OFFSETS = (-5, 5, 0)


def shifted(frame: Image.Image, y: int) -> Image.Image:
    # Leave a small transparent buffer so the cutout can move without a hard
    # edge appearing during the shake.
    canvas = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    canvas.alpha_composite(frame, (0, 6 + y))
    return canvas


def gif_frame(frame: Image.Image) -> Image.Image:
    """Reserve palette index 255 exclusively for transparent pixels."""
    rgba = frame.convert("RGBA")
    alpha = np.asarray(rgba.getchannel("A"))
    opaque = Image.new("RGB", rgba.size, (255, 255, 255))
    opaque.paste(rgba, mask=rgba.getchannel("A"))
    indexed = opaque.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    pixels = np.asarray(indexed).copy()
    pixels[alpha < 128] = 255
    result = Image.fromarray(pixels.astype(np.uint8), "P")
    palette = indexed.getpalette()[: 255 * 3] + [0, 0, 0]
    result.putpalette(palette)
    return result


def save_sequence(
    name: str,
    source_indexes: list[int],
    shake: bool,
    *,
    state_ms: int = STATE_MS,
    frame_durations: list[int] | None = None,
    play_once: bool = False,
) -> None:
    sources = [
        Image.open(SOURCE_DIR / f"typingpet-source-{index}.png").convert("RGBA")
        for index in source_indexes
    ]
    if shake and len(sources) == 2:
        base, target = sources
        frames = [base]
        durations = [state_ms]
        for offset in SHAKE_OFFSETS:
            frames.append(shifted(target, offset))
            durations.append(SHAKE_MS if offset != 0 else state_ms)
        for offset in SHAKE_OFFSETS:
            frames.append(shifted(base, offset))
            durations.append(SHAKE_MS if offset != 0 else state_ms)
    else:
        frames = sources
        durations = [state_ms] * len(frames)
    if frame_durations is not None:
        if len(frame_durations) != len(frames):
            raise ValueError("frame durations must match the number of frames")
        durations = frame_durations
    frame_paths = []
    for frame_index, frame in enumerate(frames, 1):
        frame_path = OUT / f"{name}-frame-{frame_index}.png"
        frame.save(frame_path, optimize=True)
        frame_paths.append(frame_path)

    write_apng(
        frame_paths,
        OUT / f"{name}.apng",
        duration_ms=durations,
        num_plays=1 if play_once else 0,
    )
    webp_options = {
        "save_all": True,
        "append_images": frames[1:],
        "duration": durations,
        "lossless": True,
        "method": 6,
    }
    if not play_once:
        webp_options["loop"] = 0
    frames[0].save(
        OUT / f"{name}.webp",
        **webp_options,
    )
    gif_frames = [gif_frame(frame) for frame in frames]
    gif_options = {
        "save_all": True,
        "append_images": gif_frames[1:],
        "duration": durations,
        "disposal": 2,
        "transparency": 255,
        "optimize": False,
    }
    if not play_once:
        gif_options["loop"] = 0
    gif_frames[0].save(
        OUT / f"{name}.gif",
        **gif_options,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Requested order: last image first, then each of the first six images.
    for index in range(1, 7):
        save_sequence(f"typingpet-9-to-{index}", [9, index], shake=True)
    # Requested reverse order of the final three images.
    save_sequence(
        "typingpet-9-to-8-to-7",
        [9, 8, 7],
        shake=False,
        frame_durations=[3330, 3330, 3340],
        play_once=True,
    )


if __name__ == "__main__":
    main()
