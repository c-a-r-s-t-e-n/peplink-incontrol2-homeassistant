"""Build original community branding; Pillow is only needed to regenerate assets."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components/peplink_incontrol2/brand"
ASSETS = ROOT / "docs/assets"
NAVY = "#10283D"
ORANGE = "#FF782D"
TEAL = "#32D6C5"


def emblem(size):
    scale = 4
    im = Image.new("RGBA", (size * scale, size * scale))
    d = ImageDraw.Draw(im)

    def box(coords):
        return tuple(round(v * size * scale / 256) for v in coords)

    d.rounded_rectangle(box((8, 8, 248, 248)), radius=size * scale * 0.22, fill=NAVY)
    # Original router, twin WAN antennas and a connected telemetry node.
    width = max(1, round(size * scale * 0.032))
    d.line([box((70, 142)), box((70, 73))], fill=TEAL, width=width)
    d.line([box((186, 142)), box((186, 73))], fill=TEAL, width=width)
    d.arc(box((43, 37, 213, 185)), 214, 326, fill=TEAL, width=width)
    d.arc(box((77, 66, 179, 156)), 214, 326, fill=ORANGE, width=width)
    d.rounded_rectangle(box((45, 135, 211, 200)), radius=round(size * scale * 0.04), fill="white")
    for x in (68, 91, 114):
        d.ellipse(box((x, 161, x + 10, 171)), fill=TEAL if x == 68 else NAVY)
    d.rounded_rectangle(box((161, 155, 191, 178)), radius=round(size * scale * 0.008), fill=ORANGE)
    return im.resize((size, size), Image.Resampling.LANCZOS)


def font(size, bold=False):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans" + ("-Bold" if bold else "") + ".ttf", size)


def main():
    BRAND.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for factor in (1, 2):
        suffix = "@2x" if factor == 2 else ""
        icon = emblem(256 * factor)
        for prefix in ("", "dark_"):
            icon.save(BRAND / f"{prefix}icon{suffix}.png", optimize=True)
        for dark in (False, True):
            logo = Image.new("RGBA", (1000 * factor, 256 * factor))
            logo.alpha_composite(icon, (0, 0))
            d = ImageDraw.Draw(logo)
            d.text(
                (286 * factor, 52 * factor),
                "Peplink InControl 2",
                font=font(48 * factor, True),
                fill="white" if dark else NAVY,
            )
            d.text(
                (289 * factor, 124 * factor),
                "HOME ASSISTANT  /  COMMUNITY",
                font=font(24 * factor),
                fill=TEAL if dark else "#35546B",
            )
            logo.save(BRAND / f"{'dark_' if dark else ''}logo{suffix}.png", optimize=True)
    banner = Image.new("RGB", (1600, 480), NAVY)
    d = ImageDraw.Draw(banner)
    d.rounded_rectangle((1130, -170, 1690, 390), radius=150, outline="#1B3A50", width=3)
    d.rounded_rectangle((1240, 140, 1790, 690), radius=150, outline="#1B3A50", width=3)
    banner.paste(emblem(290), (70, 80), emblem(290))
    d.text((405, 89), "PEPLINK INCONTROL 2", font=font(52, True), fill="white")
    d.text((408, 169), "Your networks. Clearly connected.", font=font(32), fill="#C8DAE5")
    d.text((409, 235), "WAN health  ·  Cellular insight  ·  GPS tracking", font=font(23), fill=TEAL)
    d.rounded_rectangle((410, 315, 890, 365), radius=25, fill="#213F53")
    d.text((433, 325), "HOME ASSISTANT  /  COMMUNITY", font=font(21, True), fill="white")
    banner.save(ASSETS / "header.png", optimize=True)


if __name__ == "__main__":
    main()
