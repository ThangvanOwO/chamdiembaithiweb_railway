"""
Generate PWA icons from gradeflow_logo.png
Run: python gen_pwa_icons.py
"""
from PIL import Image
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
SOURCE = STATIC_DIR / "img" / "gradeflow_logo.png"
ICON_DIR = STATIC_DIR / "img" / "icons"

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]


def main():
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(SOURCE).convert("RGBA")

    for size in SIZES:
        resized = img.resize((size, size), Image.LANCZOS)
        out = ICON_DIR / f"icon-{size}x{size}.png"
        resized.save(out, "PNG")
        print(f"  Created {out.name}")

    # Maskable icon: add padding (safe area = 80% center, 10% padding each side)
    maskable = img.resize((int(512 * 0.8), int(512 * 0.8)), Image.LANCZOS)
    maskable_canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = (512 - maskable.width) // 2
    maskable_canvas.paste(maskable, (offset, offset))
    maskable_out = ICON_DIR / "maskable-512x512.png"
    maskable_canvas.save(maskable_out, "PNG")
    print(f"  Created {maskable_out.name}")

    print(f"\nDone! {len(SIZES) + 1} icons generated in {ICON_DIR}")


if __name__ == "__main__":
    main()
