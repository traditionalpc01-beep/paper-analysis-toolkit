from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / 'desktop' / 'assets'


def load_font(size: int):
    candidates = [
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        '/System/Library/Fonts/SFNS.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_icon() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    size = 1024
    image = Image.new('RGBA', (size, size), (243, 239, 228, 255))
    draw = ImageDraw.Draw(image)

    for y in range(size):
        red = int(244 - (y / size) * 52)
        green = int(239 - (y / size) * 88)
        blue = int(228 - (y / size) * 116)
        draw.line([(0, y), (size, y)], fill=(red, green, blue, 255))

    draw.ellipse((70, 60, 510, 500), fill=(230, 199, 168, 130))
    draw.ellipse((540, 520, 980, 960), fill=(47, 127, 116, 95))
    draw.rounded_rectangle(
        (176, 176, 848, 848),
        radius=180,
        fill=(250, 245, 237, 235),
        outline=(122, 57, 20, 40),
        width=6,
    )
    draw.rounded_rectangle((226, 226, 798, 798), radius=150, fill=(171, 91, 42, 255))
    draw.polygon([(744, 236), (798, 236), (798, 290)], fill=(234, 205, 168, 255))
    draw.polygon([(226, 744), (226, 798), (280, 798)], fill=(197, 232, 224, 255))

    title_font = load_font(330)
    subtitle_font = load_font(72)

    title = 'PI'
    title_box = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_box[2] - title_box[0]
    draw.text(((size - title_width) / 2, 275), title, font=title_font, fill=(247, 242, 232, 255))

    subtitle = 'PaperInsight'
    subtitle_box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_box[2] - subtitle_box[0]
    draw.text(((size - subtitle_width) / 2, 675), subtitle, font=subtitle_font, fill=(247, 232, 214, 220))

    image.save(ASSETS_DIR / 'icon.png')
    image.resize((256, 256), Image.Resampling.LANCZOS).save(
        ASSETS_DIR / 'icon.ico',
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )

    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" fill="none">
  <defs>
    <linearGradient id="bg" x1="120" y1="120" x2="904" y2="904" gradientUnits="userSpaceOnUse">
      <stop stop-color="#d07a45"/>
      <stop offset="1" stop-color="#7a3914"/>
    </linearGradient>
  </defs>
  <rect width="1024" height="1024" rx="220" fill="#f3efe4"/>
  <circle cx="290" cy="250" r="220" fill="#e6c7a8" fill-opacity="0.55"/>
  <circle cx="760" cy="770" r="230" fill="#2f7f74" fill-opacity="0.3"/>
  <rect x="176" y="176" width="672" height="672" rx="170" fill="#faf5ed" fill-opacity="0.96"/>
  <rect x="226" y="226" width="572" height="572" rx="150" fill="url(#bg)"/>
  <path d="M798 236h-54v54" fill="#e6c7a8"/>
  <path d="M226 798h54v-54" fill="#c5e8e0"/>
  <text x="512" y="520" text-anchor="middle" font-size="320" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="#f7f2e8">PI</text>
  <text x="512" y="718" text-anchor="middle" font-size="72" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="#f1dfcc">PaperInsight</text>
</svg>
'''
    (ASSETS_DIR / 'icon.svg').write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    generate_icon()
    print(f'Generated assets in {ASSETS_DIR}')
