from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from make_typingpet_animation import remove_edge_background, write_apng


INPUTS = [
    Path("/tmp/codex-clipboard-743b9246-72d8-4349-a7b6-a0ffc796d3a3.png"),
    Path("/tmp/codex-clipboard-9ae78254-6bca-46b1-8b2a-7625d3b59c71.png"),
    Path("/tmp/codex-clipboard-ff66586c-0f16-4c98-834c-ca8fd44ed8cb.png"),
    Path("/tmp/codex-clipboard-946077c4-b151-4930-a909-388f43b17283.png"),
    Path("/tmp/codex-clipboard-e3efc914-76f0-454a-946b-626cba4c05e8.png"),
    Path("/tmp/codex-clipboard-5b954ee6-f483-4fd3-91a7-cbf372643e70.png"),
    Path("/tmp/codex-clipboard-5424bb90-12d1-444c-ad27-e42c80c7723b.png"),
    Path("/tmp/codex-clipboard-e991868d-a67d-4439-9542-d1eed712e75f.png"),
    Path("/tmp/codex-clipboard-b6d1e174-6ac5-4d6e-b9e9-406d1810dfbb.png"),
]
OUT = Path("assets/typingpet-groups")
FRAME_MS = 70
Y_OFFSETS = (0, -5, 0, 5)


def shifted(frame: Image.Image, y: int) -> Image.Image:
    canvas = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    canvas.alpha_composite(frame, (0, 6 + y))
    return canvas


def save_animation(name: str, sources: list[Image.Image]) -> None:
    with TemporaryDirectory(prefix="typingpet-frames-") as temporary:
        temp = Path(temporary)
        frames = []
        frame_paths = []
        index = 1
        for source in sources:
            for y in Y_OFFSETS:
                frame = shifted(source, y)
                frame_path = temp / f"frame-{index}.png"
                frame.save(frame_path, optimize=True)
                frames.append(frame)
                frame_paths.append(frame_path)
                index += 1

        write_apng(frame_paths, OUT / f"{name}.apng", duration_ms=FRAME_MS)
        frames[0].save(
            OUT / f"{name}.webp",
            save_all=True,
            append_images=frames[1:],
            duration=FRAME_MS,
            loop=0,
            lossless=True,
            method=6,
        )
        gif_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=255) for frame in frames]
        gif_frames[0].save(
            OUT / f"{name}.gif",
            save_all=True,
            append_images=gif_frames[1:],
            duration=FRAME_MS,
            loop=0,
            disposal=2,
            transparency=0,
            optimize=True,
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = []
    for index, path in enumerate(INPUTS, 1):
        if not path.exists():
            raise FileNotFoundError(path)
        source = remove_edge_background(Image.open(path))
        source.save(OUT / f"typingpet-source-{index}.png", optimize=True)
        sources.append(source)

    # Last image first, then the six images at the beginning of the batch.
    save_animation("typingpet-last-then-first-six", [sources[8], *sources[:6]])
    # Explicit reverse order of the final three: last, second-last, third-last.
    save_animation("typingpet-last-three-reverse", [sources[8], sources[7], sources[6]])


if __name__ == "__main__":
    main()
