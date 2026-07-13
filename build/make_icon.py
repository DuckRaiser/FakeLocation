"""生成 FakeLocation 的 .icns 图标。构建期用,运行时不依赖。

用法:python build/make_icon.py <输出.icns 路径>
需要 Pillow(make_app.sh 会自动装)。若环境缺失则以非零退出,构建脚本会跳过图标。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024


def gradient() -> Image.Image:
    top, bottom = (0x25, 0x63, 0xEB), (0x4F, 0x46, 0xE5)   # 蓝 → 靛
    col = Image.new('RGB', (1, S))
    for y in range(S):
        t = y / (S - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return col.resize((S, S)).convert('RGBA')


def render() -> Image.Image:
    # 圆角背景
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=230, fill=255)
    bg = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    bg.paste(gradient(), (0, 0), mask)

    # 白色定位针
    pin = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(pin)
    cx, cy, r = S // 2, 430, 172
    white = (255, 255, 255, 255)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=white)
    d.polygon([(cx - r * 0.72, cy + r * 0.66), (cx + r * 0.72, cy + r * 0.66), (cx, 712)], fill=white)
    hr = 70                                                # 中间镂空,透出背景
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=(0, 0, 0, 0))

    return Image.alpha_composite(bg, pin)


def main() -> int:
    out = Path(sys.argv[1])
    master = render()
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / 'icon.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            master.resize((size, size), Image.LANCZOS).save(iconset / f'icon_{size}x{size}.png')
            master.resize((size * 2, size * 2), Image.LANCZOS).save(iconset / f'icon_{size}x{size}@2x.png')
        subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(out)], check=True)
    print(f'图标已生成 → {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
