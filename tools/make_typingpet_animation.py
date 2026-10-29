from __future__ import annotations

from pathlib import Path
import struct
import zlib

import cv2
import numpy as np
from PIL import Image


INPUTS = [
    Path("/tmp/codex-clipboard-b9fbe0d2-a3a2-4764-9686-09df8c8f20c7.png"),
    Path("/tmp/codex-clipboard-20160b56-0b87-4719-93a8-b58cce6841a2.png"),
    Path("/tmp/codex-clipboard-e233966d-f9d3-45fc-9a23-0689c78d2328.png"),
    Path("/tmp/codex-clipboard-b0c51b08-320b-4a07-bbf2-f1d49e1ce661.png"),
]
OUT = Path("assets/typingpet")
BG = np.array([252.0, 249.0, 250.0], dtype=np.float32)


def remove_edge_background(image: Image.Image) -> Image.Image:
    rgba = np.array(image.convert("RGBA"))
    rgb = rgba[:, :, :3].astype(np.float32)

    # The pale paper and blue decoration are removable only when connected to
    # the canvas edge, so pink hair and the desk are not confused with them.
    distance = np.linalg.norm(rgb - BG, axis=2)
    near_paper = distance < 36.0
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    pale_blue = (blue > red + 3.0) & (green >= red) & (blue > 150.0)
    removable = (near_paper | pale_blue).astype(np.uint8)

    border = np.zeros(removable.shape, dtype=np.uint8)
    border[0, :] = border[-1, :] = 1
    border[:, 0] = border[:, -1] = 1
    seeds = (removable & border).astype(np.uint8)
    count, labels, _, _ = cv2.connectedComponentsWithStats(removable, 8)
    edge_labels = np.unique(labels[seeds.astype(bool)])
    bg_mask = np.isin(labels, edge_labels[edge_labels != 0])

    # Remove the pink sparkle on the left as a separate edge-connected object,
    # while retaining the similarly colored hair in the interior.
    pink = (red > 175.0) & (red > green + 18.0) & (red > blue + 8.0)
    pink_count, pink_labels, pink_stats, _ = cv2.connectedComponentsWithStats(pink.astype(np.uint8), 8)
    pink_edge = np.unique(pink_labels[border.astype(bool)])
    bg_mask |= np.isin(pink_labels, pink_edge[pink_edge != 0])
    # The sparkle has a tiny white gap from the border in the source image,
    # so remove the large pink component in the left margin explicitly.
    for label in range(1, pink_count):
        x, y, width, height, area = pink_stats[label]
        if x < 50 and 100 < y < 300 and area > 1000:
            bg_mask |= pink_labels == label

    alpha = np.where(bg_mask, 0, 255).astype(np.uint8)
    # Preserve a small amount of anti-aliased edge rather than leaving a hard
    # one-pixel cut around the character and desk.
    soft = cv2.GaussianBlur(alpha, (3, 3), 0)
    alpha = np.where((soft > 0) & (soft < 255), soft, alpha).astype(np.uint8)
    rgba[:, :, 3] = alpha
    return Image.fromarray(rgba, "RGBA")


def png_chunks(path: Path) -> list[tuple[bytes, bytes]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    chunks = []
    offset = 8
    while offset < len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        chunks.append((kind, payload))
        offset += 12 + size
    return chunks


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_apng(
    paths: list[Path],
    destination: Path,
    duration_ms: int | list[int] = 180,
    num_plays: int = 0,
) -> None:
    parsed = [png_chunks(path) for path in paths]
    durations = [duration_ms] * len(paths) if isinstance(duration_ms, int) else duration_ms
    if len(durations) != len(paths):
        raise ValueError("duration list must match the number of APNG frames")
    ihdr = next(payload for kind, payload in parsed[0] if kind == b"IHDR")
    width, height = struct.unpack(">II", ihdr[:8])
    output = bytearray(b"\x89PNG\r\n\x1a\n")
    output += png_chunk(b"IHDR", ihdr)
    output += png_chunk(b"acTL", struct.pack(">II", len(paths), num_plays))
    for kind, payload in parsed[0]:
        if kind not in {b"IHDR", b"IDAT", b"IEND"}:
            output += png_chunk(kind, payload)
    sequence = 0
    delay_den = 1000
    for frame_index, chunks in enumerate(parsed):
        control = struct.pack(">IIIIIHHBB", sequence, width, height, 0, 0, int(durations[frame_index]), delay_den, 1, 0)
        output += png_chunk(b"fcTL", control)
        sequence += 1
        for kind, payload in chunks:
            if kind == b"IDAT" and frame_index == 0:
                output += png_chunk(b"IDAT", payload)
            elif kind == b"IDAT":
                output += png_chunk(b"fdAT", struct.pack(">I", sequence) + payload)
                sequence += 1
    output += png_chunk(b"IEND", b"")
    destination.write_bytes(output)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, path in enumerate(INPUTS, 1):
        if not path.exists():
            raise FileNotFoundError(path)
        frame = remove_edge_background(Image.open(path))
        frame_path = OUT / f"typingpet-frame-{index}.png"
        frame.save(frame_path, optimize=True)
        frames.append(frame)

    frame_paths = [OUT / f"typingpet-frame-{index}.png" for index in range(1, len(frames) + 1)]
    write_apng(frame_paths, OUT / "typingpet-cycle.apng")
    frames[0].save(
        OUT / "typingpet-cycle.webp",
        save_all=True,
        append_images=frames[1:],
        duration=180,
        loop=0,
        lossless=True,
        method=6,
    )
    # GIF has binary transparency, so keep it as a compatibility fallback.
    gif_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=255) for frame in frames]
    gif_frames[0].save(
        OUT / "typingpet-cycle.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=180,
        loop=0,
        disposal=2,
        transparency=0,
        optimize=True,
    )


if __name__ == "__main__":
    main()
