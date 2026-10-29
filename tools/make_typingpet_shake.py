from __future__ import annotations

from pathlib import Path

from PIL import Image

from make_typingpet_animation import remove_edge_background, write_apng


INPUTS = [
    Path("/tmp/codex-clipboard-1b58eed3-a14c-4f33-bf8d-5f3299115915.png"),
    Path("/tmp/codex-clipboard-7fd626e2-a2cd-4d22-97b4-41412dfd76b2.png"),
]
OUT = Path("assets/typingpet-shake")
FRAME_MS = 70
Y_OFFSETS = (0, -5, 0, 5)


def shifted(frame: Image.Image, y: int) -> Image.Image:
    # Keep a transparent margin around the source so the desk and hair do not
    # clip while the whole cutout moves up and down.
    canvas = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    canvas.alpha_composite(frame, (0, 6 + y))
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_frames = []
    for index, path in enumerate(INPUTS, 1):
        if not path.exists():
            raise FileNotFoundError(path)
        frame = remove_edge_background(Image.open(path))
        frame.save(OUT / f"typingpet-shake-source-{index}.png", optimize=True)
        source_frames.append(frame)

    frames = []
    frame_paths = []
    frame_index = 1
    for source in source_frames:
        for y in Y_OFFSETS:
            frame = shifted(source, y)
            path = OUT / f"typingpet-shake-frame-{frame_index}.png"
            frame.save(path, optimize=True)
            frames.append(frame)
            frame_paths.append(path)
            frame_index += 1

    write_apng(frame_paths, OUT / "typingpet-shake.apng", duration_ms=FRAME_MS)
    frames[0].save(
        OUT / "typingpet-shake.webp",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        lossless=True,
        method=6,
    )
    gif_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=255) for frame in frames]
    gif_frames[0].save(
        OUT / "typingpet-shake.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=FRAME_MS,
        loop=0,
        disposal=2,
        transparency=0,
        optimize=True,
    )


if __name__ == "__main__":
    main()
