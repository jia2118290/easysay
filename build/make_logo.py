"""
生成 EasySay 软件 Logo
运行一次即可在 app/resources/icons/ 下生成：
  - app.png   (通用 PNG，1024x1024，用于 About 窗口 / 任务栏)
  - app.ico   (Windows 图标，多尺寸)
  - app.icns  (macOS 图标，多尺寸)
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw

ICON_DIR = Path(__file__).resolve().parent.parent / "app" / "resources" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)

SIZE = 1024


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_logo() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 圆角矩形背景，蓝色渐变（左上深蓝 -> 右下亮蓝），呼应软件深色主题
    radius = int(SIZE * 0.22)
    top_color = (22, 90, 210)
    bottom_color = (37, 116, 237)

    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    for y in range(SIZE):
        t = y / SIZE
        color = lerp_color(top_color, bottom_color, t)
        bg_draw.line([(0, y), (SIZE, y)], fill=color + (255,))

    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (SIZE, SIZE)], radius=radius, fill=255)
    img.paste(bg, (0, 0), mask)

    # 2. 中心画声波条（代表语音/TTS），白色，居中对称，高低错落
    bar_count = 7
    bar_width = int(SIZE * 0.052)
    gap = int(SIZE * 0.034)
    total_width = bar_count * bar_width + (bar_count - 1) * gap
    start_x = (SIZE - total_width) // 2
    center_y = SIZE // 2

    # 每根条的相对高度比例（中间最高，两侧渐低，模拟声波）
    heights_ratio = [0.28, 0.48, 0.72, 1.0, 0.72, 0.48, 0.28]
    max_bar_height = int(SIZE * 0.42)

    for i in range(bar_count):
        h = int(max_bar_height * heights_ratio[i])
        x0 = start_x + i * (bar_width + gap)
        x1 = x0 + bar_width
        y0 = center_y - h // 2
        y1 = center_y + h // 2
        r = bar_width // 2
        draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=(255, 255, 255, 255))

    # 3. 底部小字标：字母 "S" 弧形高光，增加质感（简单加一层顶部斜光）
    highlight = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(highlight)
    hl_draw.rounded_rectangle(
        [(0, 0), (SIZE, int(SIZE * 0.5))],
        radius=radius,
        fill=(255, 255, 255, 22),
    )
    hl_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(hl_mask).rounded_rectangle([(0, 0), (SIZE, SIZE)], radius=radius, fill=255)
    img = Image.alpha_composite(img, Image.composite(highlight, Image.new("RGBA", (SIZE, SIZE), (0,0,0,0)), hl_mask))

    return img


def main():
    logo = draw_logo()

    png_path = ICON_DIR / "app.png"
    logo.save(png_path)
    print(f"[OK] {png_path}")

    ico_path = ICON_DIR / "app.ico"
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    logo.save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes])
    print(f"[OK] {ico_path}")

    icns_path = ICON_DIR / "app.icns"
    try:
        icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
        imgs = [logo.resize((s, s), Image.LANCZOS) for s in icns_sizes]
        imgs[-1].save(icns_path, format="ICNS", append_images=imgs[:-1])
        print(f"[OK] {icns_path}")
    except Exception as e:
        print(f"[WARN] 未生成 icns（不影响 Windows 打包）: {e}")


if __name__ == "__main__":
    main()
